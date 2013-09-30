# Written by Niels Zeilemaker

import os
import sha
import sys
import time
import re
from copy import deepcopy
from shutil import copyfile
from Tribler.Core.TorrentDef import TorrentDef
from traceback import print_exc
from threading import Thread, RLock, Event

from Tribler.Core.Utilities.timeouturlopen import urlOpenTimeout
from Tribler.Core.Utilities.bencode import bencode, bdecode
from Tribler.Core.RemoteTorrentHandler import RemoteTorrentHandler
from urlparse import urlparse

try:
    from Tribler.Main.Utility.Feeds import feedparser
except:
    import feedparser #Feedparser is installed as a package in ubuntu

URLHIST_TIMEOUT = 7 * 24 * 3600.0  # Don't revisit links for this time
RSS_RELOAD_FREQUENCY = 30 * 60  # reload a rss source every n seconds
RSS_CHECK_FREQUENCY = 2  # test a potential .torrent in a rss source every n seconds

DEBUG = False


class RssParser(Thread):
    __single = None

    def __init__(self):
        if RssParser.__single:
            raise RuntimeError("RssParser is singleton")
        RssParser.__single = self

        Thread.__init__(self)
        self.setName("RssParser" + self.getName())
        self.setDaemon(True)

        self.key_url_lock = RLock()
        self.key_url = {}

        self.key_callbacks = {}

        self.urls_changed = Event()
        self.isRegistered = False

    def getInstance(*args, **kw):
        if RssParser.__single is None:
            RssParser(*args, **kw)
        return RssParser.__single
    getInstance = staticmethod(getInstance)

    def delInstance(*args, **kw):
        RssParser.__single = None
    delInstance = staticmethod(delInstance)

    def register(self, session, defaultkey):
        if not self.isRegistered:
            self.session = session
            self.defaultkey = defaultkey
            self.remote_th = RemoteTorrentHandler.getInstance()

            dirname = self.getdir()
            if not os.path.exists(dirname):
                os.makedirs(dirname)

            # read any rss feeds that are currently outstanding
            self.readfile()

            self.isRegistered = True
        elif DEBUG:
            print >> sys.stderr, "RssParser is already registered, ignoring"

    def getdir(self):
        return os.path.join(self.session.get_state_dir(), "subscriptions")

    def getfilename(self):
        return os.path.join(self.getdir(), "subscriptions.txt")

    def gethistfilename(self, url, key):
        h = sha.sha(url).hexdigest()

        histfile = os.path.join(self.getdir(), "%s-%s.txt" % (h, key))
        oldhistfile = os.path.join(self.getdir(), h + '.txt')

        if not os.path.exists(histfile):
            # upgrade...
            if os.path.exists(oldhistfile):
                copyfile(oldhistfile, histfile)

        return histfile

    def readfile(self):
        try:
            filename = self.getfilename()
            f = open(filename, "rb")
            for line in f.readlines():

                parts = line.split()
                if len(parts) > 1:
                    state = parts[0]
                    url = parts[1]

                    if len(parts) > 2:
                        key = int(parts[2])
                    else:
                        key = self.defaultkey

                    if state == 'active':
                        self.addURL(url, key, dowrite=False)
                else:
                    print >> sys.stderr, "RssParser: Ignoring line", line
            f.close()
        except:
            if DEBUG:
                print >> sys.stderr, "RssParser: subscriptions.txt does not yet exist"

    def writefile(self):
        filename = self.getfilename()
        f = open(filename, "wb")

        for channel_id, urls in self.key_url.iteritems():
            for url in urls:
                f.write('active %s %d\r\n' % (url, channel_id))
        f.close()

    def addURL(self, url, key, dowrite=True):
        try:
            self.key_url_lock.acquire()

            channel_feeds = self.key_url.setdefault(key, set())

            if url not in channel_feeds:
                channel_feeds.add(url)
                self.urls_changed.set()

            if dowrite:
                self.writefile()

            self.doStart()
        finally:
            self.key_url_lock.release()

    def deleteURL(self, url, key):
        try:
            self.key_url_lock.acquire()

            channel_feeds = self.key_url.setdefault(key, set())

            if url in channel_feeds:
                channel_feeds.remove(url)
                self.urls_changed.set()

            self.writefile()
        except:
            pass
        finally:
            self.key_url_lock.release()

    def addCallback(self, key, callback):
        self.key_callbacks.setdefault(key, set()).add(callback)

        self.doStart()

    def getUrls(self, key):
        return list(self.key_url.get(key, set()))

    def doRefresh(self):
        if DEBUG:
            print >> sys.stderr, "RssParser: refresh"

        self.doStart()

    def doStart(self):
        if not self.isAlive():
            if len(self.key_url) and len(self.key_callbacks):
                self.start()
        else:
            self.urls_changed.set()

    def run(self):
        self.urls_changed.wait(60)  # Let other Tribler components, in particular, Session startup

        while self.isRegistered and len(self.key_url) and len(self.key_callbacks):
            if DEBUG:
                print >> sys.stderr, "RssParser: running"

            self._refresh()
            self.urls_changed.clear()

            if DEBUG:
                print >> sys.stderr, "RssParser: finished, waiting", RSS_RELOAD_FREQUENCY
            self.urls_changed.wait(RSS_RELOAD_FREQUENCY)
        else:
            if DEBUG:
                print >> sys.stderr, "RssParser: not registered unable to run or exiting"

    def shutdown(self):
        self.isRegistered = False
        self.urls_changed.set()

    def _refresh(self):
        channel_url = None
        try:
            self.key_url_lock.acquire()
            channel_url = deepcopy(self.key_url)
        finally:
            self.key_url_lock.release()

        if channel_url:
            for key, urls in channel_url.iteritems():
                if key in self.key_callbacks:
                    for url in urls:
                        if DEBUG:
                            print >> sys.stderr, "RssParser: getting rss", url, len(urls)

                        historyfile = self.gethistfilename(url, key)
                        urls_already_seen = URLHistory(historyfile)
                        urls_already_seen.read()

                        newItems = self.readUrl(url, urls_already_seen)
                        for title, new_urls, description, thumbnail in newItems:
                            for new_url in new_urls:
                                urls_already_seen.add(new_url)
                                urls_already_seen.write()

                                try:
                                    if DEBUG:
                                        print >> sys.stderr, "RssParser: trying", new_url

                                    referer = urlparse(new_url)
                                    referer = referer.scheme + "://" + referer.netloc + "/"
                                    stream = urlOpenTimeout(new_url, referer=referer)
                                    bdata = stream.read()
                                    stream.close()

                                    bddata = bdecode(bdata, 1)
                                    torrent = TorrentDef._create(bddata)

                                    def processCallbacks(key):
                                        for callback in self.key_callbacks[key]:
                                            try:
                                                callback(key, torrent, extraInfo={'title': title, 'description': description, 'thumbnail': thumbnail})
                                            except:
                                                print_exc()

                                    if self.remote_th.is_registered():
                                        callback = lambda key = key: processCallbacks(key)
                                        self.remote_th.save_torrent(torrent, callback)
                                    else:
                                        processCallbacks(key)

                                except:
                                    if DEBUG:
                                        print >> sys.stderr, "RssParser: could not download", new_url
                                    pass

                                time.sleep(RSS_CHECK_FREQUENCY)

    def readUrl(self, url, urls_already_seen):
        if DEBUG:
            print >> sys.stderr, "RssParser: reading url", url

        newItems = []

        feedparser._HTMLSanitizer.acceptable_elements = ['p', 'br']
        d = feedparser.parse(url)
        for entry in d.entries:
            title = entry.title

            discovered_links = set()
            for link in entry.links:
                discovered_links.add(link['href'])

            for enclosure in entry.enclosures:
                discovered_links.add(enclosure['href'])

            try:
                for content in entry.media_content:
                    discovered_links.add(content['url'])
            except:
                pass

            description = ''
            if getattr(entry, 'summary', False):
                description = entry.summary
                if description:
                    description = re.sub("<.*?>", "\n", description)
                    description = re.sub("\n+", "\n", description)

            try:
                thumbnail = entry.media_thumbnail[0]['url']
            except:
                thumbnail = None

            new_urls = [discovered_url for discovered_url in discovered_links if not urls_already_seen.contains(discovered_url)]

            if len(new_urls) > 0:
                newItems.append((title, new_urls, description, thumbnail))

        return newItems

# Written by Freek Zindel, Arno Bakker
class URLHistory:

    read_history_expression = re.compile("(\d+(?:[.]\d+)?)\s+(\w+)", re.IGNORECASE)

    def __init__(self, filename):
        self.urls = {}
        self.filename = filename
        self.readed = False

    def add(self, dirtyurl):
        url = self.clean_link(dirtyurl)
        self.urls[url] = time.time()

    def contains(self, dirtyurl):
        url = self.clean_link(dirtyurl)

        # Poor man's filter
        if url.endswith(".jpg") or url.endswith(".JPG"):
            return True

        t = self.urls.get(url, None)
        if t is None:
            return False
        else:
            now = time.time()
            return not self.timedout(t, now)  # no need to delete

    def timedout(self, t, now):
        return (t + URLHIST_TIMEOUT) < now

    def read(self):
        if DEBUG:
            print >> sys.stderr, "subscrip: Reading cached", self.filename
        try:
            file_handle = open(self.filename, "rb")
        except IOError:
            # file not found...
            # there is no cache available
            pass
        else:
            re_line = re.compile("^\s*(\d+(?:[.]\d+)?)\s+(.+?)\s*$")
            now = time.time()
            for line in file_handle.readlines():
                match = re_line.match(line)
                if match:
                    timestamp, url = match.groups()
                    timestamp = float(timestamp)
                    if not self.timedout(timestamp, now):
                        if DEBUG:
                            print >> sys.stderr, "subscrip: Cached url is", url
                        self.urls[url] = timestamp
                    elif DEBUG:
                        print >> sys.stderr, "subscrip: Timed out cached url is %s" % url

            file_handle.close()

    def write(self):
        try:
            file_handle = open(self.filename, "wb")
        except IOError:
            # can't write file
            print_exc()
        else:
            for url, timestamp in self.urls.iteritems():
                file_handle.write("%f %s\r\n" % (timestamp, url))
            file_handle.close()

    def copy(self):
        return self.urls.copy()

    def clean_link(self, link):
        """ Special vuze case """
        idx = link.find(';jsessionid')
        if idx == -1:
            return link
        else:
            return link[:idx]


if __name__ == '__main__':
    DEBUG = True

    def callback(key, torrent, extraInfo):
        print >> sys.stderr, "RssParser: Found torrent", key, torrent, extraInfo

    class FakeSession:

        def get_state_dir(self):
            return os.path.dirname(__file__)

        def get_torrent_collecting_dir(self):
            return self.get_state_dir()

    r = RssParser.getInstance()
    r.register(FakeSession(), 'test')
    r.addCallback('test', callback)
    r.addURL('http://www.vodo.net/feeds/public', 'test', dowrite=False)

    r.join()

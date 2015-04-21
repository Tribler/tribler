# Written by Niels Zeilemaker
import imghdr
import logging
import os
import re
from hashlib import sha1
import tempfile
import time
from copy import deepcopy
from shutil import copyfile, move
from threading import Thread, RLock, Event
from traceback import print_exc
from libtorrent import bdecode

import requests

from Tribler.Core.TorrentDef import TorrentDef

import feedparser

URLHIST_TIMEOUT = 7 * 24 * 3600.0  # Don't revisit links for this time
RSS_RELOAD_FREQUENCY = 30 * 60  # reload a rss source every n seconds
RSS_CHECK_FREQUENCY = 2  # test a potential .torrent in a rss source every n seconds


class RssParser(Thread):
    __single = None

    def __init__(self):
        if RssParser.__single:
            raise RuntimeError("RssParser is singleton")
        RssParser.__single = self

        self._logger = logging.getLogger(self.__class__.__name__)

        Thread.__init__(self)
        name = "RssParser" + self.getName()
        self.setName(name)
        self.setDaemon(True)

        self.key_url_lock = RLock()
        self.key_url = {}

        self.key_callbacks = {}

        self.urls_changed = Event()
        self.rss_parser = RSSFeedParser()
        self.url_resourceretriever = URLResourceRetriever()
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
            self.remote_th = session.lm.rtorrent_handler

            dirname = self.getdir()
            if not os.path.exists(dirname):
                os.makedirs(dirname)

            # read any rss feeds that are currently outstanding
            self.readfile()

            self.isRegistered = True
        else:
            self._logger.debug("RssParser is already registered, ignoring")

    def getdir(self):
        return os.path.join(self.session.get_state_dir(), "subscriptions")

    def getfilename(self):
        return os.path.join(self.getdir(), "subscriptions.txt")

    def gethistfilename(self, url, key):
        h = sha1(url).hexdigest()

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
                    self._logger.info("RssParser: Ignoring line %s", line)
            f.close()
        except:
            self._logger.debug("RssParser: subscriptions.txt does not yet exist")

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
        self._logger.debug("RssParser: refresh")

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
            self._logger.debug("RssParser: running")

            self._refresh()
            if not self.isRegistered:
                break

            self.urls_changed.clear()
            self._logger.debug("RssParser: finished, waiting %s", RSS_RELOAD_FREQUENCY)
            self.urls_changed.wait(RSS_RELOAD_FREQUENCY)
        else:
            self._logger.debug("RssParser: not registered unable to run or exiting")

    def shutdown(self):
        self.isRegistered = False
        self.urls_changed.set()

    def _refresh(self):
        channel_url = None
        with self.key_url_lock:
            channel_url = deepcopy(self.key_url)

        if channel_url:
            for key, urls in channel_url.iteritems():
                if key in self.key_callbacks:
                    for url in urls:
                        self._logger.debug(u"Getting rss %s", url)

                        historyfile = self.gethistfilename(url, key)
                        urls_already_seen = URLHistory(historyfile)
                        urls_already_seen.read()

                        for title, description, url_list in self.rss_parser.parse(url):
                            if not self.isRegistered:
                                return

                            tempdir = tempfile.mkdtemp()
                            try:
                                torrent_list, image_list, useless_url_list = \
                                    self.url_resourceretriever.retrieve(url_list, tempdir, urls_already_seen)
                            except:
                                self._logger.exception(u"Failed to retrieve data.")
                                continue

                            for useless_url in useless_url_list:
                                urls_already_seen.add(useless_url)
                            urls_already_seen.write()

                            # call callback for everything valid torrent
                            for torrent_url, torrent in torrent_list:
                                urls_already_seen.add(torrent_url)
                                urls_already_seen.write()

                                thumbnail_file = os.path.join(tempdir, image_list[0][1]) if image_list else None

                                def processCallbacks(key, torrent, extra_info):
                                    for callback in self.key_callbacks[key]:
                                        try:
                                            callback(key, torrent, extraInfo=extra_info)
                                        except:
                                            self._logger.exception(u"Failed to process torrent callback.")

                                extra_info = {'title': title,
                                              'description': description}
                                if thumbnail_file:
                                    extra_info['thumbnail-file'] = thumbnail_file
                                callback = lambda k = key, t=torrent, ei=extra_info: processCallbacks(k, t, ei)
                                self.remote_th.save_torrent(torrent, callback)

                                time.sleep(RSS_CHECK_FREQUENCY)

                                # Should we stop?
                                if not self.isRegistered:
                                    return


class URLResourceRetriever(object):

    def __init__(self):
        super(URLResourceRetriever, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

    def retrieve(self, url_list, work_dir, urls_already_seen):
        """Retrieves and identifies resources from a list of URLs.
        It returns a list of identified URL and file pair, including:
          (1) .torrent (URL, torrent object)
          (2) pictures (URL, picture-file-path)
        """
        torrent_list = []
        image_list = []
        useless_url_list = []
        image_count = 1
        for url in url_list:
            if urls_already_seen.contains(url):
                self._logger.debug(u"Skip, URL already seen [%s]", url)
                continue

            # download the thing
            stream = None
            self._logger.debug(u"Trying to download [%s]", url)
            try:
                stream = requests.get(url, timeout=30)
                if not stream.ok:
                    continue
                data = stream.content
            except:
                self._logger.exception(u"Could not download %s", url)
                useless_url_list.append(url)
                continue
            finally:
                if stream:
                    stream.close()

            self._logger.debug(u"Trying to save [%s]", url)
            tmp_file = None
            tmp_path = None
            try:
                tmp_file_no, tmp_path = tempfile.mkstemp(dir=work_dir)
                tmp_file = os.fdopen(tmp_file_no, 'wb')
                tmp_file.write(data)
            except:
                self._logger.exception(u"Could not save %s -> %s", url, tmp_path)
                continue
            finally:
                if tmp_file:
                    tmp_file.close()

            # check if it is an image
            self._logger.debug(u"Trying to do image check [%s] [%s]", url, tmp_path)
            image_result = self.__try_image(tmp_path, work_dir, image_count)
            if image_result:
                self._logger.debug(u"Got image %s -> %s", url, image_result)
                image_list.append((url, image_result))
                image_count += 1
                continue

            # check if it is a torrent file
            self._logger.debug(u"Trying to do torrent check [%s] [%s]", url, tmp_path)
            torrent_result = self.__try_torrent(tmp_path)
            if torrent_result:
                self._logger.debug(u"Got torrent %s", url)
                torrent_list.append((url, torrent_result))
                os.remove(tmp_path)
                continue

            # useless URL
            self._logger.debug(u"Useless URL %s", url)
            useless_url_list.append(url)
            if tmp_path:
                self._logger.debug(u"Remove file %s", tmp_path)
                os.remove(tmp_path)

        return torrent_list, image_list, useless_url_list

    def __try_image(self, filepath, work_dir, image_count):
        """Checks if a file is an image. If it is an image, the file will be
           renamed with extension and the new file path will be returned.
           Otherwise, the file will be removed.
        """
        image_type = imghdr.what(filepath)
        if image_type:
            # rename the file
            old_filepath = filepath
            new_filename = u"thumbnail-%d.%s" % (image_count, image_type)
            new_filepath = os.path.join(work_dir, new_filename)
            move(old_filepath, new_filepath)

            return new_filepath
        else:
            return None

    def __try_torrent(self, filepath):
        """Checks if a file is a torrent. If it is a torrent, returns the
           parsed torrent.
        """
        filestream = None
        try:
            filestream = open(filepath, 'rb')
            data = filestream.read()
            bddata = bdecode(data)
            if bddata is not None:
                return TorrentDef._create(bddata)
        except:
            return None
        finally:
            if filestream:
                filestream.close()


class RSSFeedParser(object):

    def __init__(self):
        super(RSSFeedParser, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

    def __parse_html(self, content):
        """Parses an HTML content and find links.
        """
        if content is None:
            return None
        url_set = set()

        a_list = re.findall(r'<a.+href=[\'"]?([^\'" >]+)', content)
        for a_href in a_list:
            url_set.add(a_href)

        img_list = re.findall(r'<img.+src=[\'"]?([^\'" >]+)', content)
        for img_src in img_list:
            url_set.add(img_src)

        return url_set

    def __html2plaintext(self, html_content):
        """Converts an HTML document to plain text.
        """
        content = html_content.replace('\r\n', '\n')

        content = re.sub('<br[ \t\r\n\v\f]*.*/>', '\n', content)
        content = re.sub('<p[ \t\r\n\v\f]*.*/>', '\n', content)

        content = re.sub('<p>', '', content)
        content = re.sub('</p>', '\n', content)

        content = re.sub('<.+/>', '', content)
        content = re.sub('<.+>', '', content)
        content = re.sub('</.+>', '', content)

        content = re.sub('[\n]+', '\n', content)
        content = re.sub('[ \t\v\f]+', ' ', content)

        parsed_html_content = u''
        for line in content.split('\n'):
            trimed_line = line.strip()
            if trimed_line:
                parsed_html_content += trimed_line + u'\n'

        return parsed_html_content

    def parse(self, url):
        """Parses a RSS feed. This methods supports RSS 2.0 and Media RSS.
        """
        feed = feedparser.parse(url)

        parsed_item_list = []
        for item in feed.entries:
            all_url_set = set()

            # ordinary RSS elements
            title = item.get(u'title', None)
            link = item.get(u'link', None)
            description = item.get(u'description', None)
            # <description> can be an HTML document
            description_url_set = self.__parse_html(description)
            if description_url_set:
                all_url_set.update(description_url_set)

            if link:
                all_url_set.add(link)

            # get urls from enclosures
            for enclosure in item.enclosures:
                enclosure_url = enclosure.get(u'url', None)
                if enclosure_url:
                    all_url_set.add(enclosure_url)

            # media RSS elements
            media_title = item.get(u'media:title', None)
            media_description = item.get(u'media:description', None)
            # <media:description> can be an HTML document
            media_description_url_set = self.__parse_html(media_description)
            if media_description_url_set:
                all_url_set.update(media_description_url_set)

            media_thumbnail_list = item.get(u'media:thumbnail', None)
            if media_thumbnail_list:
                for media_thumbnail in media_thumbnail_list:
                    url = media_thumbnail.get(u'url', None)
                    if url:
                        all_url_set.add(url)

            # assemble the information, including:
            # use media:title, and media:description as default information
            the_title = media_title if media_title else title
            the_title = the_title if the_title is not None else u''
            the_description = media_description if media_description else description
            the_description = the_description if the_description is not None else u''
            if the_description:
                the_description = self.__html2plaintext(the_description)

            parsed_item = (the_title, the_description, all_url_set)
            parsed_item_list.append(parsed_item)

        return parsed_item_list


# Written by Freek Zindel, Arno Bakker
class URLHistory:

    read_history_expression = re.compile("(\d+(?:[.]\d+)?)\s+(\w+)", re.IGNORECASE)

    def __init__(self, filename):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.urls = {}
        self.filename = filename
        self.readed = False

    def add(self, dirtyurl):
        url = self.clean_link(dirtyurl)
        self.urls[url] = time.time()

    def contains(self, dirtyurl):
        url = self.clean_link(dirtyurl)

        t = self.urls.get(url, None)
        if t is None:
            return False
        else:
            now = time.time()
            return not self.timedout(t, now)  # no need to delete

    def timedout(self, t, now):
        return (t + URLHIST_TIMEOUT) < now

    def read(self):
        self._logger.debug("subscrip: Reading cached %s", self.filename)
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
                        self._logger.debug("subscrip: Cached url is %s", url)
                        self.urls[url] = timestamp
                    else:
                        self._logger.debug("subscrip: Timed out cached url is %s", url)

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

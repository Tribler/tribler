#Written by Niels Zeilemaker

from threading import Thread, RLock, Event
import os
import sha
import sys
from copy import deepcopy
from shutil import copyfile
from Tribler.Subscriptions.rss_client import URLHistory
from Tribler.Main.Utility.Rss import feedparser
from Tribler.Core.TorrentDef import TorrentDef
from traceback import print_exc
import time
from Tribler.Core.Utilities.utilities import get_collected_torrent_filename

URLHIST_TIMEOUT = 7*24*3600.0   # Don't revisit links for this time
RSS_RELOAD_FREQUENCY = 30*60    # reload a rss source every n seconds
RSS_CHECK_FREQUENCY = 2         # test a potential .torrent in a rss source every n seconds

DEBUG = False

class RssParser(Thread):
    __single = None
    
    def __init__(self):
        if RssParser.__single:
            raise RuntimeError, "RssParser is singleton"
        RssParser.__single = self
        
        Thread.__init__(self)
        self.setName( "RssParser"+self.getName())
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
    
    def register(self, session, defaultkey):
        if not self.isRegistered:
            self.session = session
            self.defaultkey = defaultkey
            
            dirname = self.getdir()
            if not os.path.exists(dirname):
                os.makedirs(dirname)
    
            # read any rss feeds that are currently outstanding
            self.readfile()
            
            self.isRegistered = True
        else:
            print >> sys.stderr, "RssParser is already registered, ignoring"
        
    def getdir(self):
        return os.path.join(self.session.get_state_dir(),"subscriptions")

    def getfilename(self):
        return os.path.join(self.getdir(),"subscriptions.txt")

    def gethistfilename(self, url, key):
        h = sha.sha(url).hexdigest()
        
        histfile = os.path.join(self.getdir(),"%s-%s.txt"%(h, key))
        oldhistfile = os.path.join(self.getdir(),h+'.txt')
        
        if not os.path.exists(histfile):
            #upgrade...
            if os.path.exists(oldhistfile):
                copyfile(oldhistfile, histfile)
        
        return histfile
    
    def gettorrentfilename(self, tdef):
        tor_dir = self.session.get_torrent_collecting_dir()
        tor_filename = get_collected_torrent_filename(tdef.get_infohash())
        return os.path.join(tor_dir, tor_filename)
    
    def readfile(self):
        try:
            filename = self.getfilename()
            f = open(filename,"rb")
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
                    print >> sys.stderr,"RssParser: Ignoring line", line
            f.close()
        except:
            if DEBUG:
                print >>sys.stderr, "RssParser: subscriptions.txt does not yet exist"
                
    def writefile(self):
        filename = self.getfilename()
        f = open(filename,"wb")
        
        for channel_id, urls in self.key_url.iteritems():
            for url in urls:
                f.write('active %s %d\r\n'%(url, channel_id))
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
        
        if not self.isAlive():
            self.start()
            
    def getUrls(self, key):
        return list(self.key_url.get(key, []))

    def doRefresh(self):
        if not self.isAlive():
            self.start()
        else:
            self.urls_changed.set()
            
    def run(self):
        self.urls_changed.wait(60) # Let other Tribler components, in particular, Session startup
        
        while self.isRegistered:
            self._refresh()
            
            self.urls_changed.wait(RSS_RELOAD_FREQUENCY)
            
        else:
            print >> sys.stderr, "RssParser, not registered unable to run"
        
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
                        historyfile = self.gethistfilename(url, key)
                        urls_already_seen = URLHistory(historyfile)
                        urls_already_seen.read()
                        
                        newItems = self.readUrl(url, urls_already_seen)
                        for title, new_urls, description, thumbnail in newItems:
                            for new_url in new_urls:
                                urls_already_seen.add(new_url)
                                urls_already_seen.write()
                                
                                try:
                                    torrent = TorrentDef.load_from_url(new_url)
                                    torrent.save(self.gettorrentfilename(torrent))
                                    
                                    for callback in self.key_callbacks[key]:
                                        try:
                                            callback(key, torrent, extraInfo = {'title':title, 'description': description, 'thumbnail': thumbnail})
                                        except:
                                            print_exc()
                                except:
                                    pass
                                
                                
                                time.sleep(RSS_CHECK_FREQUENCY)
                                
    def readUrl(self, url, urls_already_seen):
        newItems = []
        
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
            
            description = entry.summary
            try:
                thumbnail = entry.media_thumbnail[0]['url']
            except:
                thumbnail = None
            
            new_urls = [discovered_url for discovered_url in discovered_links if not urls_already_seen.contains(discovered_url)]
            
            if len(new_urls) > 0:
                newItems.append((title, new_urls, description, thumbnail))
        
        return newItems
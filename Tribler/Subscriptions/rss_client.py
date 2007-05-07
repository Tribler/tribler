# Written by Freek Zindel
# see LICENSE.txt for license information
#
#this is a very limited torrent rss reader. 
#works on some sites, but not on others due to captchas or username/password requirements for downloads.

#usage: make a torrentfeedreader instance and call refresh whenevey you would like to check that feed for new torrents. e.g. every 15 minutes.

import os
import sys
import traceback
from Tribler.timeouturlopen import urlOpenTimeout
import re
import urlparse
from xml.dom.minidom import parseString
from threading import Thread,RLock
from time import sleep
from sha import sha

from BitTornado.bencode import bdecode,bencode
from Tribler.Overlay.MetadataHandler import MetadataHandler
from Tribler.CacheDB.CacheDBHandler import TorrentDBHandler


class TorrentFeedThread(Thread):
    
    __single = None
    
    def __init__(self):
        if TorrentFeedThread.__single:
            raise RuntimeError, "TorrentFeedThread is singleton"
        TorrentFeedThread.__single = self
        Thread.__init__(self)
        self.setDaemon(True)

        self.urls = {}
        self.feeds = []
        self.lock = RLock()

    def getInstance(*args, **kw):
        if TorrentFeedThread.__single is None:
            TorrentFeedThread(*args, **kw)
        return TorrentFeedThread.__single
    getInstance = staticmethod(getInstance)
        
    def register(self,utility):
        self.metahandler = MetadataHandler.getInstance()
        self.torrent_db = TorrentDBHandler()
    
        self.utility = utility
        filename = self.getfilename()
        try:
            f = open(filename,"rb")
            for line in f.readlines():
                for key in ['active','inactive']:
                    if line.startswith(key):
                        url = line[len(key)+1:-2] # remove \r\n
                        print "subscrip: Add from file URL",url,"EOU"
                        self.addURL(url,dowrite=False,status=key)
            f.close()        
        except:
            traceback.print_exc()
    
        #self.addURL('http://www.vuze.com/syndication/browse/AZHOT/ALL/X/X/26/X/_/_/X/X/feed.xml')
        
    def addURL(self,url,dowrite=True,status="active"):
        self.lock.acquire()
        if url not in self.urls:
            self.urls[url] = status
            if status == "active":
                feed = TorrentFeedReader(url)
                self.feeds.append(feed)
            if dowrite:
                self.writefile()
        self.lock.release()

    def writefile(self):
        filename = self.getfilename()
        f = open(filename,"wb")
        for url in self.urls:
            val = self.urls[url]
            f.write(val+' '+url+'\r\n')
        f.close()
        
    def getfilename(self):
        return os.path.join(self.utility.getConfigPath(),"subscriptions.txt")
        
    def getURLs(self):
        return self.urls # doesn't need to be locked
        
    def setURLStatus(self,url,newstatus):
        self.lock.acquire()
        print >>sys.stderr,"subscrip: setURLStatus",url,newstatus
        newtxt = "active"
        if newstatus == False:
            newtxt = "inactive"
        print >>sys.stderr,"subscrip: setURLStatus: newstatus set to",url,newtxt
        if url in self.urls:
            self.urls[url] = newtxt
            self.writefile()
        else:
            print >>sys.stderr,"subscrip: setURLStatus: unknown URL?",url
        self.lock.release()
    
    def deleteURL(self,url):
        self.lock.acquire()
        if url in self.urls:
            del self.urls[url]
            for i in range(len(self.feeds)):
                feed = self.feeds[i]
                if feed.feed_url == url:
                    del self.feeds[i]
                    break
            self.writefile()
        self.lock.release()
        
    def run(self):
        while True:
            self.lock.acquire()
            cfeeds = self.feeds[:]
            self.lock.release()
            
            for feed in cfeeds:
                rssurl = feed.feed_url
                print >>sys.stderr,"suscrip: Opening RSS feed",rssurl
                pairs = feed.refresh()
                for title,urlopenobj in pairs:
                    print >>sys.stderr,"$$$$$ subscrip: Retrieving",`title`,"from",rssurl
                    try:
                        if urlopenobj is not None:
                            bdata = urlopenobj.read()
                            urlopenobj.close()
    
                            data = bdecode(bdata)
                            torrent_hash = sha(bencode(data['info'])).digest()
                            if not self.torrent_db.hasTorrent(torrent_hash):
                                print >>sys.stderr,"subscript: Storing",`title`
                                self.metahandler.save_torrent(torrent_hash,bdata)
                            else:
                                print >>sys.stderr,"subscript: Not storing",`title`,"already have it"
                                
                    except:
                        traceback.print_exc()
                        
                    sleep(15) # TODO: make user configable
        sleep(15*60)


class TorrentFeedReader:
    def __init__(self,feed_url):
        self.feed_url = feed_url
        self.urls_already_seen = set()
        self.href_re = re.compile('href="(.*?)"')
        self.torrent_types = ['application/x-bittorrent','application/x-download']

    def isTorrentType(self,type):
        return type in self.torrent_types

    def refresh(self):
        """Returns a generator for a list of (title,urllib2openedurl_to_torrent)
        pairs for this feed. TorrentFeedReader instances keep a list of
        torrent urls in memory and will yield a torrent only once.
        If the feed points to a torrent url with webserver problems,
        that url will not be retried.
        urllib2openedurl_to_torrent may be None if there is a webserver problem.
        """
        feed_socket = urlOpenTimeout(self.feed_url,timeout=5)
        feed_xml = feed_socket.read()
        
        feed_dom = parseString(feed_xml)

        entries = [(title,link) for title,link in
                   [(item.getElementsByTagName("title")[0].childNodes[0].data,
                     item.getElementsByTagName("link")[0].childNodes[0].data) for
                    item in feed_dom.getElementsByTagName("item")]
                   if not link in self.urls_already_seen]
        for title,link in entries:
            # print title,link
            try:
                self.urls_already_seen.add(link)
                html_or_tor = urlOpenTimeout(link,timeout=5)
                found_torrent = False
                tor_type = html_or_tor.headers.gettype()
                if self.isTorrentType(tor_type):
                    torrent = html_or_tor
                    found_torrent = True
                    yield title,torrent
                elif 'html' in tor_type:
                    html = html_or_tor.read()
                    hrefs = [match.group(1) for match in self.href_re.finditer(html)]
                          
                    urls = []
                    for url in hrefs:
                        if not url in self.urls_already_seen:
                            self.urls_already_seen.add(url)
                            urls.append(urlparse.urljoin(link,url))
                    for url in urls:
                        #print url
                        try:
                            torrent = urlOpenTimeout(url)
                            url_type = torrent.headers.gettype()
                            #print url_type
                            if self.isTorrentType(url_type):
                                #print "torrent found:",url
                                found_torrent = True
                                yield title,torrent
                                break
                            else:
                                #its not a torrent after all, but just some html link
                                pass
                        except:
                            #url didn't open
                            pass
                if not found_torrent:
                    yield title,None
            except:
                traceback.print_exc()
                yield title,None


                        
                    
                
                
                

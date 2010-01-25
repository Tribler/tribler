# Written by Freek Zindel, Arno Bakker
# see LICENSE.txt for license information
#
#this is a very limited torrent rss reader. 
#works on some sites, but not on others due to captchas or username/password requirements for downloads.

#usage: make a torrentfeedreader instance and call refresh whenevey you would like to check that feed for new torrents. e.g. every 15 minutes.
#
# Arno, 2007-05-7: We now store the urls visited on disk and don't recontact them for a certain period
#       I've added special support for vuze torrents that have the links to the .torrent in the RSS XML
#       but not as an <link> tag.
#
#       In addition, I've set the reader to be conservative for now, it only looks at .torrent files
#       directly mentioned in the RSS XML, no recursive parsing, that, in case of vuze, visits a lot
#       of sites unnecessarily and uses Java session IDs (";jsessionid") in the URLs, which renders
#       our do-not-visit-if-recently-visited useless.
#
# 2007-05-08: vuze appears to have added a ;jsessionid to the <enclosure> tag. I now strip that for
# the URLHistory, but use it in requests. So don't be alarmed by the ;jsessionid in the debug messages.
#
# 2008-04-04: vuze appears to have changed format altogether: It no longer
# adheres to RSS. <item> is called <entry> and <enclosure> is called <content>
#

import os
import sys
import binascii
import traceback
from Tribler.Core.Utilities.timeouturlopen import urlOpenTimeout
#from BitTornado.zurllib import urlopen
import re
import urlparse
from xml.dom.minidom import parseString
from xml.parsers.expat import ExpatError
from threading import Thread,RLock,Event
import time

from Tribler.Core.API import *

import sha

from Tribler.Core.BitTornado.bencode import bdecode,bencode
from Tribler.Core.Overlay.permid import permid_for_user,sign_data,verify_data
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB, bin2str, str2bin, NULL
from Tribler.Core.CacheDB.SqliteCacheDBHandler import ChannelCastDBHandler
from Tribler.Core.SocialNetwork.RemoteTorrentHandler import RemoteTorrentHandler

from urllib2 import Request, urlopen, URLError, HTTPError

URLHIST_TIMEOUT = 7*24*3600.0 # Don't revisit links for this time
RSS_RELOAD_FREQUENCY = 30*60      # reload a rss source every n seconds
RSS_CHECK_FREQUENCY = 1  # test a potential .torrent in a rss source every n seconds

DEBUG = False

class TorrentFeedThread(Thread):
    
    __single = None
    
    def __init__(self):
        if TorrentFeedThread.__single:
            raise RuntimeError, "TorrentFeedThread is singleton"
        TorrentFeedThread.__single = self
        Thread.__init__(self)
        self.setName( "TorrentFeed"+self.getName())
        self.setDaemon(True)

        self.urls = {}
        self.feeds = []
        self.lock = RLock()
        self.done = Event()

        # main url used for rc1
        self.mainURL = None

        

        # when rss feeds change, we have to restart the checking
        self.feeds_changed = Event()

    def getInstance(*args, **kw):
        if TorrentFeedThread.__single is None:
            TorrentFeedThread(*args, **kw)
        return TorrentFeedThread.__single
    getInstance = staticmethod(getInstance)
    
    def register(self,session):
        self.session = session
        self.reloadfrequency = RSS_RELOAD_FREQUENCY
        self.checkfrequency = RSS_CHECK_FREQUENCY
        
        self.torrent_dir = self.session.get_torrent_collecting_dir()
        self.torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        self.channelcast_db = self.session.open_dbhandler(NTFY_CHANNELCAST)
        
        self.rtorrent_handler = RemoteTorrentHandler.getInstance()
        
        filename = self.getfilename()
        dirname = os.path.dirname(filename)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        try:
            f = open(filename,"rb")
            for line in f.readlines():
                for key in ['active','inactive']:
                    if line.startswith(key):
                        url = line[len(key)+1:-2] # remove \r\n
                        self.mainURL = url
                        if DEBUG:
                            print >>sys.stderr,"subscrip: Add from file URL",url,"EOU"
                        self.addURL(url,dowrite=False,status=key)
            f.close()        
        except:
            pass
            #traceback.print_exc()
    
        #self.addURL('http://www.legaltorrents.com/feeds/cat/netlabel-music.rss')
        #self.addFile('ubuntu-9.04-desktop-i386.iso.torrent')
    
    def addFile(self, filename):
        """ This function enables to add individual torrents, instead of a collection of torrents through RSS """
        try:
            data = open(filename, 'rb').read()
            torrent_data = bdecode(data)
            infohash = sha.sha(bencode(torrent_data['info'])).digest()
            if DEBUG: print >>sys.stderr, "Adding a torrent in my channel: %s" % torrent_data["info"]["name"]
            self.save_torrent(infohash, data)
            self.channelcast_db.addOwnTorrent(infohash, torrent_data)
            return infohash
        except:
            print >> sys.stderr, "Could not add torrent:", filename
            traceback.print_exc()
            return None

#    def setURLCallback(self, url, callback):
#        self.lock.acquire()
#	for tup in self.feeds:
#            if tup[0].feed_url == url:
#               tup[2] = callback
#        self.lock.release()
    
    def addURL(self, url, dowrite=True, status="active", callback=None):
        # reinitialize feeds
        self.feeds = []
        print >> sys.stderr , "callback", url, callback
        def on_torrent_callback(rss_url, infohash, torrent_data):
            print >> sys.stderr , "rss_url" , rss_url
            if DEBUG: print >>sys.stderr, "Adding a torrent in my channel: %s" % torrent_data["info"]["name"]
            self.channelcast_db.addOwnTorrent(infohash, torrent_data)

        self.lock.acquire()
        if url not in self.urls:
            self.urls[url] = status
            if status == "active":
                feed = TorrentFeedReader(url,self.gethistfilename(url))
                self.feeds.append([feed, on_torrent_callback, callback])
                self.feeds_changed.set()
            if dowrite:
                self.writefile()
        if callback:
            for tup in self.feeds:
                if tup[0].feed_url == url:
                   tup[2] = callback
        self.lock.release()

    def writefile(self):
        filename = self.getfilename()
        f = open(filename,"wb")
        for url in self.urls:
            val = self.urls[url]
            f.write(val+' '+url+'\r\n')
        f.close()
        
    def getfilename(self):
        return os.path.join(self.getdir(),"subscriptions.txt")

    def gethistfilename(self,url):
        # TODO: url2pathname or something that gives a readable filename
        h = sha.sha(url).hexdigest()
        return os.path.join(self.getdir(),h+'.txt')
    
    """    
    def getdir(self):
        return os.path.join(self.utility.getConfigPath(),"subscriptions")
    """
    
    def getdir(self):
        return os.path.join(self.session.get_state_dir(),"subscriptions")
        
    def getURLs(self):
        return self.urls # doesn't need to be locked
        
    def setURLStatus(self,url,newstatus):
        self.lock.acquire()
        if DEBUG:
            print >>sys.stderr,"subscrip: setURLStatus",url,newstatus
        newtxt = "active"
        if newstatus == False:
            newtxt = "inactive"
        if DEBUG:
            print >>sys.stderr,"subscrip: setURLStatus: newstatus set to",url,newtxt
        if url in self.urls:
            self.urls[url] = newtxt
            self.writefile()
        elif DEBUG:
            print >>sys.stderr,"subscrip: setURLStatus: unknown URL?",url
        self.lock.release()
    
    def deleteURL(self,url):
        self.lock.acquire()
        if url in self.urls:
            print >> sys.stderr , "DELETE URL"
            del self.urls[url]
            for i in range(len(self.feeds)):
                feed = self.feeds[i]
                print >> sys.stderr , "feed : " , feed[0]
                if feed[0] == url:
                    del self.feeds[i]
                    print >> sys.stderr , "DELETE FEED"
                    self.feeds_changed.set()
                    break
            self.writefile()
        self.lock.release()
    
       
        
    def run(self):
        time.sleep(10) # Let other Tribler components, in particular, Session startup
        while not self.done.isSet():
            self.lock.acquire()
            cfeeds = self.feeds[:]
            self.feeds_changed.clear()
            self.lock.release()
            
            # feeds contains (rss_url, generator) pairs
            feeds = {}
            for feed, on_torrent_callback, user_callback in cfeeds:
                try:
                    sugestion_generator = feed.refresh()
                except:
                    pass
                else:
                    feeds[feed.feed_url] = sugestion_generator

            # loop through the feeds and try one from each feed at a time
            while feeds:
                for (rss_url, generator) in feeds.items():
                    if rss_url is None or generator is None:
                        break

                    # are there items left in this generator
                    try:
                        title, urlopenobj = generator.next()
                        if not urlopenobj:
                            if DEBUG:
                                print >>sys.stderr, "urlopenobj NONE: torrent not found", title
                            continue
                        else:
                            if DEBUG:
                                print >>sys.stderr, "urlopenobj : torrent found", title 

                        bdata = urlopenobj.read()
                        urlopenobj.close()
                        data = bdecode(bdata)
                        
                        #tdef = TorrentDef.load_from_dict(data)
                        
                        if 'info' in data:
                            infohash = sha.sha(bencode(data['info'])).digest()
                            if not self.torrent_db.hasTorrent(infohash):
                                if DEBUG:
                                    if "name" in data["info"]:
                                        print >>sys.stderr, "Injecting", data["info"]["name"]
                                    else:
                                        print >>sys.stderr, "Injecting", title
                                self.save_torrent(infohash, bdata, source=rss_url)
                                if on_torrent_callback:
                                    if DEBUG:
                                        print >> sys.stderr , "ON TORRENT CALLBACK"
                                    on_torrent_callback(rss_url, infohash, data)
                                if user_callback:
                                    if DEBUG:
                                        print >> sys.stderr , "USER CALLBACK"
                                    user_callback(rss_url, infohash, data)


                    except StopIteration:
                        # there are no more items in generator
                        del(feeds[rss_url])

                    except ValueError:
                        # the bdecode failed
                        print >>sys.stderr, "Bdecode failed: ", rss_url
                    
                    except (ExpatError, HTTPError):
                        print >>sys.stderr, "Invalid RSS: ", rss_url 

                    # sleep in between torrent retrievals
                    #time.sleep(self.intertorrentinterval)
                    time.sleep(self.checkfrequency)

                    self.lock.acquire()
                    try:
                        if self.feeds_changed.isSet():
                            feeds = None
                            break
                    finally:
                        self.lock.release()

            # sleep for a relatively long time before downloading the
            # rss feeds again
            self.feeds_changed.wait(self.reloadfrequency)

    def save_torrent(self,infohash,bdata,source=''):
        hexinfohash = binascii.hexlify(infohash)
        if DEBUG:
            print >>sys.stderr,"subscript: Writing",hexinfohash

        filename = os.path.join(self.torrent_dir, hexinfohash+'.torrent' )
        f = open(filename,"wb")
        f.write(bdata)
        f.close()

        # Arno: hack, make sure these torrents are always good so they show up
        # in Torrent DBHandler.getTorrents()
        extra_info = {'status':'good'}
        self.torrent_db.addExternalTorrent(filename,source=source,extra_info=extra_info)

        # ARNOCOMMENT: remove later
        #self.torrent_db.commit()


    def shutdown(self):
        if DEBUG:
            print >>sys.stderr,"subscrip: Shutting down subscriptions module"
        self.done.set()
        self.lock.acquire()
        cfeeds = self.feeds[:]
        self.lock.release()
        for feed in cfeeds:
            feed.shutdown()
            
        self.utility.session.close_dbhandler(self.torrent_db)

"""
    def process_statscopy(self,statscopy):
        today = []
        yesterday = []
        now = int(time())
        sotoday = math.floor(now / (24*3600.0))*24*3600.0
        soyester = sotday - (24*3600.0)
        for rss in statscopy:
            for url,t in statscopy[rss]:
                if t > sotoday:
                    today.append(url)
"""        

class TorrentFeedReader:
    def __init__(self,feed_url,histfilename):
        self.feed_url = feed_url
        self.urls_already_seen = URLHistory(histfilename)
        # todo: the self.href_re expression does not take into account that single quotes, escaped quotes, etz. can be used
        self.href_re = re.compile('href="(.*?)"', re.IGNORECASE) 
        # the following filter is applied on the xml data because other characters crash the parser
        self.filter_xml_expression = re.compile("(&\w+;)|([^\w\d\s~`!@#$%^&*()-_=+{}[\]\\|:;\"'<,>.?/])", re.IGNORECASE)

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
        
        # Load history from disk
        if not self.urls_already_seen.readed:
            self.urls_already_seen.read()
            self.urls_already_seen.readed = True

        while True:
            try:
                feed_socket = urlOpenTimeout(self.feed_url,timeout=20)
                feed_xml = feed_socket.read()
                feed_socket.close()
                break
            except:
                yield None, None

        # 14/07/08 boudewijn: some special characters and html code is
        # raises a parser exception. We filter out these character
        # sequenses using a regular expression in the filter_xml
        # function
        dom = parseString(self._filter_xml(feed_xml))
        entries = []

        # The following XML will result in three links with the same title.
        #
        # <item>
        # <title>The title</title>
        # <link>http:/frayja.com/torrent/1</link>
        # <foobar src="frayja.com/torrent/2">Unused title</foobar>
        # <moomilk url="frayja.com/torrent/3">Unused title</moomilk>
        # </items>
        for item in dom.getElementsByTagName("item"): #+ dom.getElementsByTagName("entry"):
            title = None
            links = []
            child = item.firstChild
            while child:
                if child.nodeType == 1: # ELEMENT_NODE (according to the DOM standard)
                    if child.nodeName == "title" and child.firstChild:
                        title = child.firstChild.data

                    if child.nodeName == "link" and child.firstChild:
                        links.append(child.firstChild.data)

                    if child.hasAttribute("src"):
                        links.append(child.getAttribute("src"))

                    if child.hasAttribute("url"):
                        links.append(child.getAttribute("url"))

                child = child.nextSibling

            if title and links:
                entries.extend([(title, link) for link in links])

        if DEBUG:
            print >>sys.stderr,"subscrip: Parse of RSS returned",len(entries),"previously unseen torrents"

        for title,link in entries:
            # print title,link
            try:
                self.urls_already_seen.add(link)
                if DEBUG:
                    print >>sys.stderr,"subscrip: Opening",title,link
                html_or_tor = urlOpenTimeout(link,timeout=20)
                found_torrent = False
                tor_type = html_or_tor.headers.gettype()
                if self.isTorrentType(tor_type):
                    torrent = html_or_tor
                    found_torrent = True
                    if DEBUG:
                        print >>sys.stderr,"subscrip: torrent1: Yielding",link
                    yield title,torrent
                elif False: # 'html' in tor_type:
                    html = html_or_tor.read()
                    hrefs = [match.group(1) for match in self.href_re.finditer(html)]
                          
                    urls = []
                    for url in hrefs:
                        if not self.urls_already_seen.contains(url):
                            self.urls_already_seen.add(url)
                            urls.append(urlparse.urljoin(link,url))
                    for url in urls:
                        #print url
                        try:
                            if DEBUG:
                                print >>sys.stderr,"subscrip: torrent2: Opening",url
                            torrent = urlOpenTimeout(url)
                            url_type = torrent.headers.gettype()
                            #print url_type
                            if self.isTorrentType(url_type):
                                #print "torrent found:",url
                                found_torrent = True
                                if DEBUG:
                                    print >>sys.stderr,"subscrip: torrent2: Yielding",url
                                yield title,torrent
                                break
                            else:
                                #its not a torrent after all, but just some html link
                                if DEBUG:
                                    print >>sys.stderr, "%s not a torrent" % url
                        except:
                            #url didn't open
                            if DEBUG:
                                print >>sys.stderr, "%s did not open" % url
                if not found_torrent:
                    yield title,None
            except GeneratorExit:
                if DEBUG:
                    print >>sys.stderr, "GENERATOREXIT"
                # the generator is destroyed. we accept this by returning
                return
            except Exception, e:
                print >> sys.stderr, "rss_client:", e
                yield title,None

    def shutdown(self):
        self.urls_already_seen.write()

    def _filter_xml_helper(self, match):
        """helper function to filter invalid xml"""
        one = match.group(1)
        if one in ("&gt;", "&lt;", "&quot;", "&amp;"):
            return one
        return "?"

    def _filter_xml(self, xml):
        """filters out characters and tags that crash xml.dom.minidom.parseString"""
        return self.filter_xml_expression.sub(self._filter_xml_helper, xml)

class URLHistory:

    read_history_expression = re.compile("(\d+(?:[.]\d+)?)\s+(\w+)", re.IGNORECASE)
    
    def __init__(self,filename):
        self.urls = {}
        self.filename = filename
        self.readed = False
        
    def add(self,dirtyurl):
        url = self.clean_link(dirtyurl)
        self.urls[url] = time.time()
                    
    def contains(self,dirtyurl):
        url = self.clean_link(dirtyurl)
        
        # Poor man's filter
        if url.endswith(".jpg") or url.endswith(".JPG"):
            return True
        
        t = self.urls.get(url,None)
        if t is None:
            return False
        else:
            now = time.time()
            return not self.timedout(t,now) # no need to delete
    
    def timedout(self,t,now):
        return (t+URLHIST_TIMEOUT) < now
    
    def read(self):
        if DEBUG:
            print >>sys.stderr,"subscrip: Reading cached",self.filename
        try:
            file_handle = open(self.filename, "rb")
        except IOError:
            # file not found...
            # there is no cache available
            pass
        else:
            data = file_handle.read()
            file_handle.close()

            now = time.time()
            for timestamp, url in self.read_history_expression.findall(data):
                timestamp = float(timestamp)
                if not self.timedout(timestamp, now):
                    if DEBUG:
                        print >>sys.stderr,"subscrip: Cached url is",url
                    self.urls[url] = timestamp
                elif DEBUG:
                    print >>sys.stderr,"subscrip: Timed out cached url is %s" % url
        
    def write(self):
        try:
            file_handle = open(self.filename, "wb")
        except IOError:
            # can't write file
            traceback.print_exc()
        else:
            for url, timestamp in self.urls.iteritems():
                file_handle.write("%f %s\r\n" % (timestamp, url))
            file_handle.close()        

    def copy(self):
        return self.urls.copy()

    def clean_link(self,link):
        """ Special vuze case """
        idx = link.find(';jsessionid')
        if idx == -1:
            return link
        else:
            return link[:idx]
    
def usercallback(infohash,metadata,filename):
    pass

#!/usr/bin/python

# injector.py is used to 'inject' .torrent files into the overlay
# network.
# Currently supported sources:
#  * rss feed;
#  * watched directory.

# modify the sys.stderr and sys.stdout for safe output
import Tribler.Debug.console

from traceback import print_exc
import optparse
import os
import random
import shutil
import sys
import tempfile
import time

from Tribler.Core.API import *
from Tribler.Core.CacheDB.sqlitecachedb import bin2str
from Tribler.Subscriptions.rss_client import TorrentFeedThread
from Tribler.Core.BuddyCast.buddycast import BuddyCastFactory
from Tribler.Core.Overlay.OverlayApps import OverlayApps

from Tribler.Core.Overlay.permid import permid_for_user

def main():
    command_line_parser = optparse.OptionParser()
    command_line_parser.add_option("--statedir", action="store", type="string", help="Use an alternate statedir")
    command_line_parser.add_option("--port", action="store", type="int", help="Listen at this port")
    command_line_parser.add_option("--rss", action="store", type="string", help="Url where to fetch rss feed, or several seperated with ';'")
    command_line_parser.add_option("--dir", action="store", type="string", help="Directory to watch for .torrent files, or several seperated with ';'")
    command_line_parser.add_option("--nickname", action="store", type="string", help="The moderator name")

    # parse command-line arguments
    opt, args = command_line_parser.parse_args()

    if not (opt.rss or opt.dir):
        command_line_parser.print_help()
        print "\nExample: python Tribler/Main/metadata-injector.py --rss http://frayja.com/rss.php --nickname frayja"
        sys.exit()
    
    print "Press Ctrl-C to stop the metadata-injector"

    sscfg = SessionStartupConfig()
    if opt.statedir: sscfg.set_state_dir(os.path.realpath(opt.statedir))
    if opt.port: sscfg.set_listen_port(opt.port)
    if opt.nickname: sscfg.set_nickname(opt.nickname)
    

    sscfg.set_megacache(True)
    sscfg.set_overlay(True)
    # turn torrent collecting on. this will cause torrents to be distributed
    sscfg.set_torrent_collecting(True)
    sscfg.set_dialback(False)
    sscfg.set_internal_tracker(False)

    session = Session(sscfg)
    
    print >>sys.stderr, "permid: ", permid_for_user(session.get_permid())    
    
    
    torrent_feed_thread = TorrentFeedThread.getInstance()
    torrent_feed_thread.register(session)
    dir_feed_thread = DirectoryFeedThread(torrent_feed_thread)
    
    if opt.rss:
        def on_torrent_callback(rss_url, infohash, torrent_data):
            """
            A torrent file is discovered through rss. Add it to our channel.
            """
            torrentdef = TorrentDef.load_from_dict(torrent_data)
            print >>sys.stderr,"*** Added a torrent to channel: %s" % torrentdef.get_name_as_unicode()
            
        for rss in opt.rss.split(";"):
            print >>sys.stderr, "Adding RSS: %s" % rss
            torrent_feed_thread.addURL(rss, callback=on_torrent_callback)
    
    if opt.dir:
        def on_torrent_callback(dirpath, infohash, torrent_data):
            torrentdef = TorrentDef.load_from_dict(torrent_data)
            print '*** Added a torrent to channel: %s' % torrentdef.get_name_as_unicode()
            
        for dirpath in opt.dir.split(";"):
            print >>sys.stderr, "Adding DIR: %s" % dirpath
            dir_feed_thread.addDir(dirpath, callback=on_torrent_callback)
    
    torrent_feed_thread.start()
    dir_feed_thread.start()

    # 22/10/08. Boudewijn: connect to a specific peer
    # connect to a specific peer using the overlay
    # def after_connect(*args):
    #     print "CONNECTED", args
    # from Tribler.Core.Overlay.SecureOverlay import SecureOverlay
    # overlay = SecureOverlay.getInstance()
    # overlay.connect_dns(("130.161.158.24", 7762), after_connect)

    # condition variable would be prettier, but that don't listen to 
    # KeyboardInterrupt
    #time.sleep(sys.maxint/2048)
    try:
        while True:
            x = sys.stdin.read()
    except:
        print_exc()
    
    torrent_feed_thread.shutdown()
    dir_feed_thread.shutdown()
    session.shutdown()
    print "Shutting down..."
    time.sleep(5)    


#vliegendhart: This should probably be moved to some Tribler package:
from threading import Thread, Event
import shutil
DIR_CHECK_FREQUENCY = 10 # Check directories every 10 seconds
class DirectoryFeedThread(Thread):
    def __init__(self, torrent_feed_thread):
        Thread.__init__(self)
        self.setName("DirectoryFeed"+self.getName())
        self.setDaemon(True)
        
        self.paths = {}
        self.feeds = []
        
        self.torrent_feed_thread = torrent_feed_thread
        self.done = Event()
        
    
    def _on_torrent_found(self, dirpath, torrentpath, infohash, torrent_data):
        print >>sys.stderr, 'DirectoryFeedThread: Adding', torrentpath
        self.torrent_feed_thread.addFile(torrentpath)
        
        imported_dir = os.path.join(dirpath, 'imported')
        if not os.path.exists(imported_dir):
            os.makedirs(imported_dir)
        shutil.move(torrentpath, os.path.join(imported_dir, os.path.basename(torrentpath)))
    
    def addDir(self, dirpath, callback = None):
        # callback(dirpath, infohash, torrent_data)
        
        if dirpath not in self.paths:
            self.paths[dirpath] = 'active'
            feed = DirectoryFeedReader(dirpath)
            self.feeds.append([feed, callback])
        
        elif callback: #replace callback
            for tup in self.feeds:
                if tup[0].path == dirpath:
                    tup[2] = callback
        
    
    def deleteDir(self, path):
        raise NotImplementedError('TODO')
    
    def refresh(self):
        for (feed, callback) in self.feeds:
            if self.paths[feed.path] == 'active':
                for torrentpath, infohash, torrent_data in feed.read_torrents():
                    self._on_torrent_found(feed.path, torrentpath, infohash, torrent_data)
                    if callback:
                        callback(feed.path, infohash, torrent_data)
    
    def run(self):
        time.sleep(60) # Let other Tribler components, in particular, Session startup
        
        print >>sys.stderr, '*** DirectoryFeedThread: Starting first refresh round'
        while not self.done.isSet():
            self.refresh()
            time.sleep(DIR_CHECK_FREQUENCY)
        
    
    def shutdown(self):
        self.done.set()

class DirectoryFeedReader:
    def __init__(self, path):
        self.path = path
    
    def read_torrents(self):
        files = os.listdir(self.path)
        for file in files:
            full_path = os.path.join(self.path, file)
            
            tdef = None
            try:
                tdef = TorrentDef.load(full_path)
            except:
                pass
            
            if tdef is not None:
                yield full_path, tdef.infohash, tdef.get_metainfo()
        

if __name__ == "__main__":
    main()

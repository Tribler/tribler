# written by Yuan Yuan
# see LICENSE.txt for license information

from threading import Thread
from traceback import print_exc
from time import sleep, time
import os
from Tribler.TrackerChecking.TrackerChecking import trackerChecking
from Tribler.CacheDB.SynDBHandler import SynTorrentDBHandler
from Tribler.DecentralizedTracking.mainlineDHTChecker import mainlineDHTChecker
from Tribler.unicode import metainfoname2unicode

class ManualChecking(Thread):
    
    def __init__(self, check_list):
        self.check_list = check_list
        Thread.__init__(self)
        self.setName('ManualChecking-'+self.getName())
        self.setDaemon(True)
        
    def run(self):
        for torrent in self.check_list:
            t = SingleManualChecking(torrent)
            t.setDaemon(True)
            t.start()
            sleep(1)
            
class SingleManualChecking(Thread):
    
    def __init__(self,torrent):
        Thread.__init__(self)
        self.setDaemon(True)
        self.setName('SingleManualChecking-'+self.getName())
        
        self.torrent = torrent
        self.torrent_db = SynTorrentDBHandler.getInstance()
        self.mldhtchecker = mainlineDHTChecker.getInstance()
        

    def run(self):        
        try:
            self.readExtraTorrentInfo(self.torrent)
            trackerChecking(self.torrent)
            # Must come after tracker check, such that if tracker dead and DHT still alive, the
            # status is still set to good
            self.mldhtchecker.lookup(self.torrent['infohash'])
        except:
            print_exc()
        ##print 'torrent: %d %d' % (self.torrent['seeder'], self.torrent['leecher'])
        kw = {
            'last_check_time': int(time()),
            'seeder': self.torrent['seeder'],
            'leecher': self.torrent['leecher'],
            'status': self.torrent['status'],
            #'info': self.torrent['info']
            }
        self.torrent_db.updateTorrent(self.torrent['infohash'], updateFlag=True, **kw)
        self.deleteExtraTorrentInfo(self.torrent)
        
    def readExtraTorrentInfo(self, torrent):
        if not torrent.has_key('info'):
            from Tribler.Overlay.MetadataHandler import MetadataHandler
            from Utility.utility import getMetainfo, printTorrent
            
            metadatahandler = MetadataHandler.getInstance()
            (torrent_dir,torrent_name) = metadatahandler.get_std_torrent_dir_name(torrent)
            torrent_filename = os.path.join(torrent_dir, torrent_name)
            metadata = getMetainfo(torrent_filename)
            if not metadata:
                raise Exception('No torrent metadata found')
#
            #print 'Metainfo'
            #printTorrent(metadata)
            
            namekey = metainfoname2unicode(metadata)
            torrent['info'] = {}
            torrent['info']['name'] = metadata['info'][namekey]
            if metadata.get('announce'):
                torrent['info']['announce'] = metadata.get('announce')
            if metadata.get('announce-list'):
                torrent['info']['announce-list'] = metadata.get('announce-list')
            if metadata['info'].get('length') != None:
                torrent['info']['length'] = metadata['info']['length']
        
    def deleteExtraTorrentInfo(self, torrent):
        if torrent.has_key('info'):
            del torrent['info']
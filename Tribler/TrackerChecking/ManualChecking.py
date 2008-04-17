# written by Yuan Yuan
# see LICENSE.txt for license information

import os
import sys
import threading
from threading import Thread
from traceback import print_exc
from time import sleep, time
from Tribler.TrackerChecking.TrackerChecking import trackerChecking
from Tribler.Core.BitTornado.bencode import bdecode
from Tribler.Core.DecentralizedTracking.mainlineDHTChecker import mainlineDHTChecker
from Tribler.Core.Utilities.unicode import metainfoname2unicode
from Tribler.Core.CacheDB.CacheDBHandler import TorrentDBHandler

class ManualChecking(Thread):
    
    def __init__(self, check_list, session):
        self.session = session
        self.check_list = check_list
        Thread.__init__(self)
        self.setName('ManualChecking-'+self.getName())
        self.setDaemon(True)
        
    def run(self):
        for torrent in self.check_list:
            t = SingleManualChecking(torrent,self.session)
            t.setDaemon(True)
            t.start()
            sleep(1)
            
class SingleManualChecking(Thread):
    
    def __init__(self,torrent,session):
        Thread.__init__(self)
        self.setDaemon(True)
        self.setName('SingleManualChecking-'+self.getName())
        
        self.torrent = torrent
        self.session = session
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
        ##print 'torrent: %d %d' % (self.torrent['num_seeders'], self.torrent['num_leechers'])
        kw = {
            'last_check_time': int(time()),
            'num_seeders': self.torrent['num_seeders'],
            'num_leechers': self.torrent['num_leechers'],
            'status': self.torrent['status'],
            #'info': self.torrent['info']
            }
        self.torrent_db = TorrentDBHandler.getInstance()
        self.torrent_db.updateTorrent(self.torrent['infohash'], updateFlag=True, **kw)
        self.torrent_db.close()
        self.deleteExtraTorrentInfo(self.torrent)
        
    def readExtraTorrentInfo(self, torrent):
        if not torrent.has_key('info'):
            from Tribler.Core.Overlay.MetadataHandler import MetadataHandler
            
            torrent_dir = self.session.get_torrent_collecting_dir()
            torrent_filename = os.path.join(torrent_dir, torrent['torrent_file_name'])

            f = open(torrent_filename,"rb")
            bdata = f.read()
            f.close()
            metadata = None
            try:
                metadata = bdecode(bdata)
            except:
                print_exc()
            if not metadata:
                raise Exception('No torrent metadata found')
            
            namekey = metainfoname2unicode(metadata)
            torrent['info'] = {}
            torrent['info']['name'] = namekey[1]
            if metadata.get('announce'):
                torrent['info']['announce'] = metadata.get('announce')
            if metadata.get('announce-list'):
                torrent['info']['announce-list'] = metadata.get('announce-list')
            if metadata['info'].get('length') != None:
                torrent['info']['length'] = metadata['info']['length']
        
    def deleteExtraTorrentInfo(self, torrent):
        if torrent.has_key('info'):
            del torrent['info']

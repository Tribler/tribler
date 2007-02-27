# written by Yuan Yuan
# see LICENSE.txt for license information

from threading import Thread, Lock
from Tribler.TrackerChecking.TrackerChecking import trackerChecking
from time import sleep, time
from Tribler.CacheDB.SynDBHandler import SynTorrentDBHandler

class ManualChecking(Thread):
    
    def __init__(self, check_list):
        self.check_list = check_list
        Thread.__init__(self)
        
    def run(self):
        for torrent in self.check_list:
            t = SingleManualChecking(torrent)
#            t.setDaemon(True)
            t.start()
            sleep(1)
            
class SingleManualChecking(Thread):
    
    def __init__(self,torrent):
        self.torrent = torrent
        self.torrent_db = SynTorrentDBHandler()
        Thread.__init__(self)
        
    def run(self):        
        try:
            trackerChecking(self.torrent)
        except:
            pass
        kw = {
            'last_check_time': int(time()),
            'seeder': self.torrent['seeder'],
            'leecher': self.torrent['leecher'],
            'status': self.torrent['status'],
            'info': self.torrent['info']
            }
        self.torrent_db.updateTorrent(self.torrent['infohash'], updateFlag=True, **kw)

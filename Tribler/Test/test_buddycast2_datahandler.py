# Written by Jie Yang
# see LICENSE.txt for license information

# Arno, pychecker-ing: the addTarget and getTarget methods of JobQueue are
# no longer there, this code needs to be updated.

# 17/02/10 Boudewijn: this test reads a superpeer log to get actual
# buddycast messages.  However, these messages were wrtten to the log
# using readableBuddyCastMsg(...) and are NOT made back into normal
# buddycast messages.  This causes some buddycast messages to be
# silently dropped.

import os
import sys
import unittest
from traceback import print_exc
from shutil import copy as copyFile, move
from time import sleep
import base64
import math

from Tribler.Core.defaults import *
from Tribler.Core.BuddyCast.buddycast import DataHandler, BuddyCastFactory
from Tribler.Core.CacheDB.CacheDBHandler import *
from Tribler.Category.Category import Category
from Tribler.Utilities.TimedTaskQueue import TimedTaskQueue
from Tribler.Core.Statistics.Crawler import Crawler
from bak_tribler_sdb import *


STATE_FILE_NAME_PATH = os.path.join(FILES_DIR, 'tribler.sdb-journal')
S_TORRENT_PATH_BACKUP = os.path.join(FILES_DIR, 'bak_single.torrent')
S_TORRENT_PATH = os.path.join(FILES_DIR, 'single.torrent')

M_TORRENT_PATH_BACKUP = os.path.join(FILES_DIR, 'bak_multiple.torrent')    
M_TORRENT_PATH = os.path.join(FILES_DIR, 'multiple.torrent')    
BUSYTIMEOUT = 5000


def init():
    init_bak_tribler_sdb()

    db = SQLiteCacheDB.getInstance()
    db.initDB(TRIBLER_DB_PATH, busytimeout=BUSYTIMEOUT)
    
    print >>sys.stderr,"OPENING DB",TRIBLER_DB_PATH
    
    #db.execute_write('drop index Torrent_relevance_idx')
    TorrentDBHandler.getInstance().register(Category.getInstance('..'),'.')


class FakeSession:
    sessconfig = {}
    def get_permid(self, *args, **kargs):
        return base64.decodestring('MG0CAQEEHR/bQNvwga7Ury5+8vg/DTGgmMpGCz35Zs/2iz7coAcGBSuBBAAaoUADPgAEAL2I5yVc1+dWVEx3nbriRKJmOSlQePZ9LU7yYQoGABMvU1uGHvqnT9t+53eaCGziV12MZ1g2p0GLmZP9\n' )

    def get_moderationcast_moderations_per_have(self, *args, **kargs):
        return 100

    def add_observer(self, *args, **kargs):
        pass

    def get_votecast_recent_votes(self):
        return sessdefaults['votecast_recent_votes']
    
    def get_votecast_random_votes(self):
        return sessdefaults['votecast_random_votes']


class FakeLauchMany:
    
    def __init__(self):
        self.session = FakeSession()
        self.crawler = Crawler.get_instance(self.session)
        
        self.my_db          = MyDBHandler.getInstance()
        self.peer_db        = PeerDBHandler.getInstance()
        self.torrent_db     = TorrentDBHandler.getInstance()
        self.torrent_db.register(Category.getInstance(),'.')
        self.mypref_db      = MyPreferenceDBHandler.getInstance()
        self.pref_db        = PreferenceDBHandler.getInstance()
        self.superpeer_db   = SuperPeerDBHandler.getInstance()
        self.friend_db      = FriendDBHandler.getInstance()
        self.bartercast_db  = BarterCastDBHandler.getInstance()
        self.bartercast_db.registerSession(self.session)
        self.secure_overlay = FakeSecureOverlay()
#        torrent_collecting_dir = os.path.abspath(config['torrent_collecting_dir'])
        self.listen_port = 1234

        self.channelcast_db = ChannelCastDBHandler.getInstance()
        self.channelcast_db.registerSession(self.session)

        self.votecast_db = VoteCastDBHandler.getInstance()
        self.votecast_db.registerSession(self.session)
        self.simi_db        = SimilarityDBHandler.getInstance()
        self.pops_db = PopularityDBHandler.getInstance()

    def get_ext_ip(self):
        return None
    
    def set_activity(self, NTFY_ACT_RECOMMEND, buf):
        pass
    
class FakeThread:
    def join(self):
        pass
    
class FakeSecureOverlay:
    def get_dns_from_peerdb(self, permid):
        return None    
    
class FakeOverlayBridge:
    
    def __init__(self):
        self.thread = FakeThread()
                    
    def add_task(self, task, time=0, id=None):
        if task == 'stop':
            return
        task()


class TestBuddyCastDataHandler(unittest.TestCase):
    
    def setUp(self):
        # prepare database

        launchmany = FakeLauchMany()
        self.overlay_bridge = TimedTaskQueue(isDaemon=False) 
        #self.overlay_bridge = FakeOverlayBridge()
        self.data_handler = DataHandler(launchmany, self.overlay_bridge, max_num_peers=2500)

    def tearDown(self):
        self.overlay_bridge.add_task('quit')
        
    def test_postInit(self):
        #self.data_handler.postInit()
        self.data_handler.postInit(1,50,0, 50)
        #from time import sleep
        
class TestBuddyCast(unittest.TestCase):
    
    def setUp(self):
        # prepare database

        launchmany = FakeLauchMany()
        self.overlay_bridge = TimedTaskQueue(isDaemon=False) 
        #self.overlay_bridge = FakeOverlayBridge()
        superpeer=False # enable it to test superpeer
        self.bc = BuddyCastFactory.getInstance(superpeer=superpeer)
        self.bc.register(self.overlay_bridge, launchmany, None, 
                 None, None, True)

    def tearDown(self):
        self.overlay_bridge.add_task('quit')
        print "Before join"

    def remove_t_index(self):
        indices = [
        'Torrent_length_idx',
        'Torrent_creation_date_idx',
        'Torrent_relevance_idx',
        'Torrent_num_seeders_idx',
        'Torrent_num_leechers_idx',
        #'Torrent_name_idx',
        ]
        for index in indices:
            sql = 'drop index ' + index
            self.data_handler.torrent_db._db.execute_write(sql)
            
    def remove_p_index(self):
        indices = [
        'Peer_name_idx',
        'Peer_ip_idx',
        'Peer_similarity_idx',
        'Peer_last_seen_idx',
        'Peer_last_connected_idx',
        'Peer_num_peers_idx',
        'Peer_num_torrents_idx'
        ]
        for index in indices:
            sql = 'drop index ' + index
            self.data_handler.peer_db._db.execute_write(sql)

    def local_test(self):
                
        self.remove_t_index()
        self.remove_p_index()
                
        from Tribler.Test.log_parser import get_buddycast_data
        
        #start_time = time()
        #print >> sys.stderr, "buddycast: ******************* start local test"
        costs = []
        self.data_handler.postInit(updatesim=False)
        for permid, selversion, msg in get_buddycast_data(os.path.join(FILES_DIR,'superpeer120070902sp7001.log')):
            message = bencode(msg)
            #print 'got msg:', permid, selversion, message

            try:
                s = time()
                self.bc.gotBuddyCastMessage(message, permid, selversion)
                cost = time()-s
                costs.append(cost)
            except:
                print_exc()
                break

            print 'got msg: %d %.2f %.2f %.2f %.2f' %(len(costs), cost, min(costs), sum(costs)/len(costs), max(costs))
        # with all indices, min/avg/max:  0.00 1.78 4.57 seconds
        # without index, min/avg/max:  0.00 1.38 3.43 seconds  (58)
        print "Done"
       
    def test_start(self):
        try:
            self.bc.olthread_register(start=False)
            self.data_handler = self.bc.data_handler
            self.local_test()
            print "Sleeping for 10 secs"
            sleep(10)
            print "Done2"
            
        except:
            print_exc()
            self.assert_(False)
    
def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestBuddyCastDataHandler))
    suite.addTest(unittest.makeSuite(TestBuddyCast))
    
    return suite

    
def main():
    init()
    unittest.main(defaultTest='test_suite')

if __name__ == '__main__':
    main()
    
    

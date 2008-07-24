# Written by Jie Yang
# see LICENSE.txt for license information

# Arno, pychecker-ing: the addTarget and getTarget methods of JobQueue are
# no longer there, this code needs to be updated.

import os
import sys
import unittest
from tempfile import mkdtemp
from distutils.dir_util import copy_tree, remove_tree
from sets import Set
from traceback import print_exc

if os.path.exists(__file__):
    BASE_DIR = '..'
    sys.path.insert(1, os.path.abspath('..'))
elif os.path.exists('LICENSE.txt'):
    BASE_DIR = '.'
    
from Core.BuddyCast.buddycast import DataHandler
from Core.CacheDB.CacheDBHandler import *
from Category.Category import Category
from Utilities.TimedTaskQueue import TimedTaskQueue
from shutil import copy as copyFile, move

import hotshot, hotshot.stats
import math
from random import random, shuffle

def extract_db_files(file_dir, file_name):
    try:
        import tarfile
        tar=tarfile.open(os.path.join(file_dir, file_name), 'r|gz')
        for member in tar:
            print "extract file", member
            tar.extract(member)
            dest = os.path.join(file_dir,member.name)
            dest_dir = os.path.dirname(dest)
            if not os.path.isdir(dest_dir):
                os.makedirs(dest_dir)
            move(member.name, dest)
        tar.close()
        return True
    except:
        print_exc()
        return False
    

DB_FILE_NAME = 'tribler.sdb'
DB_DIR_NAME = None
FILES_DIR = os.path.abspath(os.path.join(BASE_DIR, 'Test/extend_db_dir/'))
TRIBLER_DB_PATH = os.path.join(FILES_DIR, 'tribler.sdb')
STATE_FILE_NAME_PATH = os.path.join(FILES_DIR, 'tribler.sdb-journal')
TRIBLER_DB_PATH_BACKUP = os.path.join(FILES_DIR, 'bak_tribler.sdb')

S_TORRENT_PATH_BACKUP = os.path.join(FILES_DIR, 'bak_single.torrent')
S_TORRENT_PATH = os.path.join(FILES_DIR, 'single.torrent')

M_TORRENT_PATH_BACKUP = os.path.join(FILES_DIR, 'bak_multiple.torrent')    
M_TORRENT_PATH = os.path.join(FILES_DIR, 'multiple.torrent')    
BUSYTIMEOUT = 5000


def init():
    if not os.path.isfile(TRIBLER_DB_PATH_BACKUP):
        got = extract_db_files(FILES_DIR, 'bak_tribler.tar.gz')
        if not got:
            print >> sys.stderr, "Please download bak_tribler.sdb from http://www.st.ewi.tudelft.nl/~jyang/donotremove/bak_tribler.sdb and save it as", os.path.abspath(TRIBLER_DB_PATH_BACKUP)
            sys.exit(1)
    if os.path.isfile(TRIBLER_DB_PATH_BACKUP):
        copyFile(TRIBLER_DB_PATH_BACKUP, TRIBLER_DB_PATH)
        print "refresh sqlite db", TRIBLER_DB_PATH
        if os.path.exists(STATE_FILE_NAME_PATH):
            os.remove(STATE_FILE_NAME_PATH)
            print "remove journal file"
    db = SQLiteCacheDB.getInstance()
    db.initDB(TRIBLER_DB_PATH, busytimeout=BUSYTIMEOUT)
    #db.execute_write('drop index Torrent_relevance_idx')
    TorrentDBHandler.getInstance().registerCategory(Category.getInstance(os.path.join(BASE_DIR, '..')))

class FakeSession:
    sessconfig = None
    def get_permid(self):
        return None

class FakeLauchMany:
    
    def __init__(self):
        self.my_db          = MyDBHandler.getInstance()
        self.peer_db        = PeerDBHandler.getInstance()
        self.torrent_db     = TorrentDBHandler.getInstance()
        self.torrent_db.registerCategory(Category.getInstance())
        self.mypref_db      = MyPreferenceDBHandler.getInstance()
        self.pref_db        = PreferenceDBHandler.getInstance()
        self.superpeer_db   = SuperPeerDBHandler.getInstance()
        self.friend_db      = FriendDBHandler.getInstance()
        self.session = FakeSession()
        self.bartercast_db  = BarterCastDBHandler.getInstance(self.session)
#        torrent_collecting_dir = os.path.abspath(config['torrent_collecting_dir'])
#        self.my_db.put('torrent_dir', torrent_collecting_dir)
        
class FakeThread:
    def join(self):
        pass
    
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
#        if sys.platform == 'win32':
#            realhomevar = '${APPDATA}'
#        else:
#            realhomevar = '${HOME}'
#        realhome = os.path.expandvars(realhomevar)
#        testdbpath = os.path.join(realhome,'.Tribler', 'bsddb')
#        self.homepath = mkdtemp()
#        print "\ntest: create tmp dir", self.homepath, testdbpath
#        self.dbpath = os.path.join(self.homepath, 'bsddb')
#        copy_tree(testdbpath, self.dbpath)
#        
#        self.install_path = '..'
        launchmany = FakeLauchMany()
        self.overlay_bridge = TimedTaskQueue(isDaemon=False) 
        #self.overlay_bridge = FakeOverlayBridge()
        self.data_handler = DataHandler(launchmany, self.overlay_bridge, max_num_peers=2500)

    def tearDown(self):
        #del self.data_handler
        #self.data_handler.close()
        self.overlay_bridge.add_task('quit')
        self.overlay_bridge.thread.join()
        del self.data_handler
        
#    def test_getAllPeers(self):
#        # testing to get a number of recently seen peers
#        num_peers = 64    #TODO: remove dir problem, right test
#        self.data_handler.loadAllPeers(num_peers)
#        peers = self.data_handler.peers
#        values = peers.values()
#        values.sort()
#        oldvls = 0
#        for v in values:
#            vls = v[0]
#            assert vls >= oldvls, (vls, oldvls)
#            oldvls = vls
#        assert len(peers) == num_peers, (len(peers), num_peers)
#        
#    def test_updateMyPreferences(self):
#        self.data_handler.updateMyPreferences()
#        assert len(self.data_handler.getMyLivePreferences())>0, len(self.data_handler.getMyLivePreferences())
#        
#    def test_updateAllSim(self):
#        num_peers = 64
#        self.data_handler.loadAllPeers(num_peers)
#        self.data_handler.updateAllSim()
#        
    def test_postInit(self):
        #self.data_handler.postInit()
        self.data_handler.postInit(1,50,0)
        #from time import sleep
        #sleep(50)
        
    def xxtest_profile(self):
        def foo(n = 10000):
            def bar(n):
                for i in range(n):
                    math.pow(i,2)
            def baz(n):
                for i in range(n):
                    math.sqrt(i)
            bar(n)
            baz(n)
        
        self.preload2(136, 30)
        print "profile starts"
        prof = hotshot.Profile("test.prof")
        prof.runcall(self.buddycast.buddycast_core.getBuddyCastData)
        prof.close()
        stats = hotshot.stats.load("test.prof")
        stats.strip_dirs()
        stats.sort_stats('cumulative', 'time', 'calls')
        stats.print_stats(100)
        

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestBuddyCastDataHandler))
    
    return suite

    
def main():
    init()
    unittest.main(defaultTest='test_suite')

if __name__ == '__main__':
    main()
    
    
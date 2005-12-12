import sys, os, string
import tempfile, random
from pprint import pprint
from types import *
import unittest

from cachedb2 import *

class BaiscDBTestCase(unittest.TestCase):
    def setUp(self):
        homeDir = os.path.join(os.path.dirname(sys.argv[0]), 'test_db')
        self.homeDir = homeDir
        try: 
            os.mkdir(homeDir)
        except os.error: 
            pass
        global home_dir
        home_dir = self.homeDir
        self.do_open()

    def tearDown(self):
        self.do_close()
        import glob
        files = glob.glob(os.path.join(self.homeDir, '*'))
        try:
            for file in files:
                os.remove(file)
            os.rmdir(self.homeDir)
        except:
            pass
        
    def do_open(self):
        pass
    
    def do_close(self):
        pass
    
class MyDBTestCase(BaiscDBTestCase):
    
    def do_open(self):
        self.mydb = MyDB.getInstance(self.homeDir)
        
    def do_close(self):
        pass
        
    def test_01(self):
        print "test 01", self.mydb._data
        myinfo = {'permid':'12345', 'ip':'12.34.56.78', 'port':1234, 'name':'jie'}
        self.mydb.initData(myinfo)
        assert self.mydb.getMyDB('permid') == '12345'
        assert self.mydb.getMyDB('ip') == '12.34.56.78'
        assert self.mydb.getMyDB('port') == 1234
        assert self.mydb.getMyDB('name') == 'jie'
        assert self.mydb.getMyDB('version') == 1
        
    def test_02(self):
        print "test 02", self.mydb._data
           
    
class PeerDBTestCase(BaiscDBTestCase):
    pass

class FriendDBTestCase(BaiscDBTestCase):
    pass

class TorrentDBTestCase(BaiscDBTestCase):
    pass

class PreferenceDBTestCase(BaiscDBTestCase):
    pass

class MyPreferenceDBTestCase(BaiscDBTestCase):
    pass

class OwnerDBTestCase(BaiscDBTestCase):
    pass

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(MyDBTestCase))
    return suite

def testMyDB():
    print "test MyDB"
    print os.path.abspath('.')

unittest.main(defaultTest='test_suite')

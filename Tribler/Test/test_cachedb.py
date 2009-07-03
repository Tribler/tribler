# Written by Jie Yang
# see LICENSE.txt for license information
#
# ARNOCOMMENT: outdated?

import os
import tempfile
import unittest
import shutil

from copy import deepcopy

import Tribler.Core.CacheDB.cachedb as cachedb

class TestBasicDB(unittest.TestCase):
    
    def setUp(self):
        self.dirname = tempfile.mkdtemp()
        self.d = cachedb.BasicDB(self.dirname)

    def tearDown(self):
        self.d.close()
        try:
            shutil.rmtree(self.dirname)
        except Exception, msg:
            print "tearDown problem:",Exception, msg, self.dirname, "not removed"
        
    def test_basic(self):
        
        # test _put, _get, _has_key, _size
        self.d._put('a', 123)
        assert self.d._has_key('a')
        assert not self.d._has_key('b')
        assert self.d._get('a') == 123
        self.d._put('c', {'1':1,'2':2})
        assert self.d._size() == 2
        
        # test _delete
        self.d._put('b', 222)
        assert self.d._has_key('b')
        self.d._delete('b')
        assert not self.d._has_key('b')

        # test _updateItem
        self.d._updateItem('a', 123)    # insert
        assert self.d._get('a') == 123, self.d._items()
        self.d._updateItem('a', 321)
        assert self.d._get('a') == 321, self.d._get('a')
        self.d._updateItem('c', {'2':22, '3':3})
        assert self.d._get('c') == {'1':1, '2':22, '3':3}, self.d._get('c')
        
        # test setDefaultItem
        x = self.d.default_item
        y = self.d.setDefaultItem({})
        assert y == x, x
        z = {'a':123, 'd':3}
        y = self.d.setDefaultItem(z)
        x.update(z)
        assert y == x, y
        
    def test_sync(self):            # write data from mem to disk
        self.d._put('k', 10)
        #self.d.close() # del already closes db
        del self.d
        assert not hasattr(self, 'd')
        self.d = cachedb.BasicDB(self.dirname)
        x = self.d._get('k')
        assert x == 10, x


class TestPeerDB(unittest.TestCase):

    def setUp(self):
        self.dirname = os.path.join(tempfile.gettempdir(), 'testdb')
        self.d = cachedb.PeerDB.getInstance(db_dir=self.dirname)
        
    def tearDown(self):
        self.d._clear()
        
    def test_peerdb(self):
        
        # test updateItem, getItem, deleteItem
        self.d.updateItem('peer1',update_time=False)
        assert self.d.getItem('peer1'), self.d.getItem('peer1')
        assert self.d.getItem('peer1') == self.d.default_item, self.d.getItem('peer1')
        
        x = {'ip':'1.2.3.4', 'port':3}
        y = deepcopy(self.d.default_item)
        y.update(x)
        self.d.updateItem('peer1', x, update_time=False)
        assert self.d.getItem('peer1') == y, self.d.getItem('peer1')
        
        x2 = {'port':7}
        y = deepcopy(self.d.default_item)
        y.update(x)
        y.update(x2)
        self.d.updateItem('peer1', x2, update_time=False)
        assert self.d.getItem('peer1') == y, self.d.getItem('peer1')
        
        self.d.deleteItem('peer1')
        assert not self.d.getItem('peer1')
        
        
class TestTorrentDB(unittest.TestCase):
    
    def setUp(self):
        self.dirname = os.path.join(tempfile.gettempdir(), 'testdb')
        self.d = cachedb.TorrentDB.getInstance(db_dir=self.dirname)
        self.d._clear()
        
    def tearDown(self):
        self.d._clear()
        
    def test_torrentdb(self):
        
        # test updateItem, getItem, deleteItem
        self.d.updateItem('torrent1')
        assert self.d.getItem('torrent1'), self.d.getItem('torrent1')
        assert self.d.getItem('torrent1') == self.d.default_item, self.d.getItem('torrent1')
        
        x = {'name':'torrent 1', 'relevance':32}
        y = deepcopy(self.d.default_item)
        y.update(x)
        self.d.updateItem('torrent1', x)
        assert self.d.getItem('torrent1') == y, self.d.getItem('torrent1')
        
        x2 = {'relevance':56}
        y = deepcopy(self.d.default_item)
        y.update(x)
        y.update(x2)
        self.d.updateItem('torrent1', x2)
        assert self.d.getItem('torrent1') == y, self.d.getItem('torrent1')
        
        self.d.deleteItem('torrent1')
        assert not self.d.getItem('torrent1')


class TestPreferenceDB(unittest.TestCase):
    
    def setUp(self):
        self.dirname = os.path.join(tempfile.gettempdir(), 'testdb')
        self.d = cachedb.PreferenceDB.getInstance(db_dir=self.dirname)
        self.d._clear()
        
    def tearDown(self):
        self.d._clear()
        
    def test_prefdb(self):
        
        # test addPreference, getPreference, hasPreference, getItem
        self.d.addPreference('peer1', 'torrent1')
        self.d.addPreference('peer1', 'torrent2')
        assert self.d.hasPreference('peer1', 'torrent2')
        
        it1 = self.d.getItem('peer1')
        assert isinstance(it1, dict) and len(it1) == 2, it1
        
        self.d.addPreference('peer2', 'torrent3')
        pf2 = self.d.getPreference('peer2', 'torrent1')
        assert pf2 is None, pf2
        
        self.d.addPreference('peer2', 'torrent5')
        pf2 = self.d.getPreference('peer2', 'torrent5')
        assert pf2 == self.d.default_item, pf2

        pf2 = self.d.getPreference('peer2', 'torrent3')
        assert pf2 == self.d.default_item, pf2
        
        z = {'rank':3, 'relevance':5}
        self.d.addPreference('peer2', 'torrent3', z)
        x = deepcopy(self.d.default_item)
        x.update(z)
        pf2 = self.d.getPreference('peer2', 'torrent3')
        assert pf2 == x, pf2
        
        z2 = {'relevance':7}
        self.d.addPreference('peer2', 'torrent3', z2)
        x = deepcopy(self.d.default_item)
        x.update(z)
        x.update(z2)
        pf2 = self.d.getPreference('peer2', 'torrent3')
        assert pf2 == x, pf2
        
        # test deletePreference, deleteItem
        self.d.deletePreference('peer1', 'torrent2')
        assert not self.d.hasPreference('peer1', 'torrent2')
        self.d.deleteItem('peer2')
        assert not self.d.getItem('peer2')
        

class TestMyPreferenceDB(unittest.TestCase):
    
    def setUp(self):
        self.dirname = os.path.join(tempfile.gettempdir(), 'testdb')
        self.d = cachedb.MyPreferenceDB.getInstance(db_dir=self.dirname)
        self.d._clear()
        
    def tearDown(self):
        self.d._clear()
        
    def test_myprefdb(self):
        
        # test updateItem, getItem, deleteItem
        self.d.updateItem('torrent1')
        assert self.d.getItem('torrent1'), self.d.getItem('torrent1')
        assert self.d.getItem('torrent1') == self.d.default_item, self.d.getItem('torrent1')
        
        x = {'name':'torrent 1', 'rank':3}
        y = deepcopy(self.d.default_item)
        y.update(x)
        self.d.updateItem('torrent1', x)
        item = self.d.getItem('torrent1')
        assert item['name'] == y['name'] and item['rank'] == y['rank'], self.d.getItem('torrent1')
        
        x2 = {'rank':'5'}
        y = deepcopy(self.d.default_item)
        y.update(x)
        y.update(x2)
        self.d.updateItem('torrent1', x2)
        item = self.d.getItem('torrent1')
        assert item['name'] == y['name'] and item['rank'] == y['rank'], self.d.getItem('torrent1')
                
        self.d.deleteItem('torrent1')
        assert not self.d.getItem('torrent1')

class TestOwnerDB(unittest.TestCase):
    
    def setUp(self):
        self.dirname = os.path.join(tempfile.gettempdir(), 'testdb')
        self.d = cachedb.OwnerDB.getInstance(db_dir=self.dirname)
        
    def tearDown(self):
        self.d._clear()
            
    def test_owner(self):
        # test addOwner, getOwner, isOwner, getItem
        self.d.addOwner('torrent1', 'peer1')
        self.d.addOwner('torrent1', 'peer2')
        assert self.d.isOwner('peer2', 'torrent1')
        it1 = self.d.getItem('torrent1')
        assert isinstance(it1, list)
        assert len(it1) == 2, len(it1)
        self.d.addOwner('torrent2', 'peer3')
        self.d.addOwner('torrent2', 'peer3')
        it2 = self.d.getItem('torrent2')
        assert len(it2) == 1, len(it2)
        
        # test deleteOwner, deleteItem
        self.d.deleteOwner('torrent2', 'peer3')
        assert not self.d.isOwner('peer3', 'torrent2')
        self.d.deleteItem('torrent1')
        assert not self.d.getItem('torrent1')
        

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestBasicDB))
    suite.addTest(unittest.makeSuite(TestPeerDB))
    suite.addTest(unittest.makeSuite(TestTorrentDB))
    suite.addTest(unittest.makeSuite(TestPreferenceDB))
    suite.addTest(unittest.makeSuite(TestMyPreferenceDB))
    suite.addTest(unittest.makeSuite(TestOwnerDB))
    
    return suite        
        

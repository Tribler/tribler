import os
import tempfile
import unittest
import socket

from copy import deepcopy
from sets import Set

import Tribler.CacheDB.cachedb as cachedb

class TestBasicDB(unittest.TestCase):
    
    def setUp(self):
        self.dirname = tempfile.mktemp()
        self.d = cachedb.BasicDB(self.dirname)

    def tearDown(self):
        self.d.close()
        try:
            filepath = os.path.join(self.dirname, self.d.db_name)
            os.remove(filepath)
            os.rmdir(self.dirname)
        except Exception, msg:
            print Exception, msg, self.dirname, "not removed"
        
    def test_basic(self):
        
        # test _put, _get, _has_key, _size
        self.d._put('a', 123)
        assert self.d._has_key('a')
        assert not self.d._has_key('b')
        assert self.d._get('a') == 123
        self.d._put('c', {'1':1,'2':2})
        assert self.d._size() == 2
        
        # test _pop, _delete
        x = self.d._pop('a')
        assert x == 123
        assert not self.d._has_key('a')
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
        self.d.close()
        del self.d
        assert not hasattr(self, 'd')
        self.d = cachedb.BasicDB(self.dirname)
        x = self.d._get('k')
        assert x == 10, x


class TestMyDB(unittest.TestCase):
    
    def setUp(self):
        self.dirname = os.path.join(tempfile.gettempdir(), 'testdb')
        self.name = socket.gethostname()
        myinfo = {'permid':'my_permid', 'ip':'1.2.3.4', 'name':self.name}
        self.d = cachedb.MyDB.getInstance(myinfo=myinfo, db_dir=self.dirname)
        self.d.initData(myinfo)
        
    def tearDown(self):
        self.d._clear()
    
    def test_initData(self):
        init = {
            'version':cachedb.curr_version, 
            'permid':'my_permid', 
            'ip':'1.2.3.4', 
            'port':0, 
            'name':self.name, 
            'torrent_path':'',
            'prefxchg_queue':[],
            'bootstrapping':1, 
            'max_num_torrents':100000,
            'max_num_my_preferences':1000,
            'superpeers':Set(),
            'friends':Set(),
        }
        
        assert self.d._size() == len(init), self.d._data
        y = {'ip':'1.2.3.4', 'permid':'permid 1'}    # only ip, permid, torrent_path can be updated
        init.update(y)
        init.update({'name':'1n;2_qfq2v@$'})
        self.d.initData(init)
        assert self.d._get('ip') == '1.2.3.4', self.d._get('ip')
        assert self.d._get('permid') == 'permid 1', self.d._get('permid')
        assert self.d._get('name') != '1n;2_qfq2v@$', self.d._get('name')
        
      
    def test_superpeers(self):
        
        # test addSuperPeer, deleteSuperPeer, isSuperPeer, getSuperPeers
        self.d.addSuperPeer('sp1')
        self.d.addSuperPeer('sp2')
        self.d.addSuperPeer('sp1')
        assert self.d.isSuperPeer('sp1'), self.d._data['superpeers']
        assert self.d.isSuperPeer('sp2'), self.d._data['superpeers']
        sp = self.d.getSuperPeers()
        assert isinstance(sp, list)
        assert Set(sp) == Set(['sp1', 'sp2'])
        self.d.deleteSuperPeer('sp2')
        assert not self.d.isSuperPeer('sp2')
        
    def test_friends(self):
        
        # test addFriend, isFriend, getFriends, deleteFriend
        self.d.addFriend('friend1')
        self.d.addFriend('friend2')
        self.d.addFriend('friend1')
        assert self.d.isFriend('friend1'), self.d._data['friends']
        assert self.d.isFriend('friend2'), self.d._data['friends']
        friends = self.d.getFriends()
        assert isinstance(friends, list)
        assert Set(friends) == Set(['friend1', 'friend2'])
        self.d.deleteFriend('friend2')
        assert not self.d.isFriend('friend2')


class TestPeerDB(unittest.TestCase):

    def setUp(self):
        self.dirname = os.path.join(tempfile.gettempdir(), 'testdb')
        self.d = cachedb.PeerDB.getInstance(db_dir=self.dirname)
        
    def tearDown(self):
        self.d._clear()
        
    def test_peerdb(self):
        
        # test updateItem, getItem, deleteItem
        self.d.updateItem('peer1')
        assert self.d.getItem('peer1'), self.d.getItem('peer1')
        assert self.d.getItem('peer1') == self.d.default_item, self.d.getItem('peer1')
        x = {'ip':'1.2.3.4', 'port':3}
        y = deepcopy(self.d.default_item)
        y.update(x)
        self.d.updateItem('peer1', x)
        assert self.d.getItem('peer1') == y, self.d.getItem('peer1')
        self.d.deleteItem('peer1')
        assert not self.d.getItem('peer1')
        
        
class TestTorrentDB(unittest.TestCase):
    
    def setUp(self):
        self.dirname = os.path.join(tempfile.gettempdir(), 'testdb')
        self.d = cachedb.PeerDB.getInstance(db_dir=self.dirname)
        
    def tearDown(self):
        self.d._clear()
        
    def test_torrentdb(self):
        
        # test updateItem, getItem, deleteItem
        self.d.updateItem('torrent1')
        assert self.d.getItem('torrent1'), self.d.getItem('torrent1')
        assert self.d.getItem('torrent1') == self.d.default_item, self.d.getItem('torrent1')
        x = {'name':'torrent 1'}
        y = deepcopy(self.d.default_item)
        y.update(x)
        self.d.updateItem('torrent1', x)
        assert self.d.getItem('torrent1') == y, self.d.getItem('torrent1')
        self.d.deleteItem('torrent1')
        assert not self.d.getItem('torrent1')


class TestPreferenceDB(unittest.TestCase):
    
    def setUp(self):
        self.dirname = os.path.join(tempfile.gettempdir(), 'testdb')
        self.d = cachedb.PreferenceDB.getInstance(db_dir=self.dirname)
        
    def tearDown(self):
        self.d._clear()
        
    def test_prefdb(self):
        
        # test addPreference, getPreference, hasPreference, getItem
        self.d.addPreference('permid1', 'torrent1')
        self.d.addPreference('permid1', 'torrent2')
        assert self.d.hasPreference('permid1', 'torrent2')
        it1 = self.d.getItem('permid1')
        assert isinstance(it1, dict)
        assert len(it1) == 2
        self.d.addPreference('permid2', 'torrent3')
        pf2 = self.d.getPreference('permid2', 'torrent1')
        assert pf2 is None
        pf2 = self.d.getPreference('permid2', 'torrent3')
        assert pf2 == self.d.default_item
        z = {'rank':3}
        self.d.addPreference('permid2', 'torrent3', z)
        x = deepcopy(self.d.default_item)
        x.update(z)
        pf2 = self.d.getPreference('permid2', 'torrent3')
        assert pf2 == x
        it2 = self.d.getItem('permid2')
        assert len(it2) == 1, len(it2)
        
        # test deletePreference, deleteItem
        self.d.deletePreference('permid1', 'torrent2')
        assert not self.d.hasPreference('permid1', 'torrent2')
        self.d.deleteItem('permid2')
        assert not self.d.getItem('permid2')
        

class TestMyPreferenceDB(unittest.TestCase):
    
    def setUp(self):
        self.dirname = os.path.join(tempfile.gettempdir(), 'testdb')
        self.d = cachedb.MyPreferenceDB.getInstance(db_dir=self.dirname)
        
    def tearDown(self):
        self.d._clear()
        
    def test_myprefdb(self):
        
        # test updateItem, getItem, deleteItem
        self.d.updateItem('torrent1')
        assert self.d.getItem('torrent1'), self.d.getItem('torrent1')
        assert self.d.getItem('torrent1') == self.d.default_item, self.d.getItem('torrent1')
        x = {'name':'torrent 1'}
        y = deepcopy(self.d.default_item)
        y.update(x)
        self.d.updateItem('torrent1', x)
        assert self.d.getItem('torrent1') == y, self.d.getItem('torrent1')
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
        self.d.addOwner('torrent1', 'permid1')
        self.d.addOwner('torrent1', 'permid2')
        assert self.d.isOwner('permid2', 'torrent1')
        it1 = self.d.getItem('torrent1')
        assert isinstance(it1, list)
        assert len(it1) == 2, len(it1)
        self.d.addOwner('torrent2', 'permid3')
        self.d.addOwner('torrent2', 'permid3')
        it2 = self.d.getItem('torrent2')
        assert len(it2) == 1, len(it2)
        
        # test deleteOwner, deleteItem
        self.d.deleteOwner('torrent2', 'permid3')
        assert not self.d.isOwner('permid3', 'torrent2')
        self.d.deleteItem('torrent1')
        assert not self.d.getItem('torrent1')
        

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestBasicDB))
    suite.addTest(unittest.makeSuite(TestMyDB))
    suite.addTest(unittest.makeSuite(TestPeerDB))
    suite.addTest(unittest.makeSuite(TestTorrentDB))
    suite.addTest(unittest.makeSuite(TestPreferenceDB))
    suite.addTest(unittest.makeSuite(TestMyPreferenceDB))
    suite.addTest(unittest.makeSuite(TestOwnerDB))
    
    return suite        
        
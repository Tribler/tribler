from Tribler.Core.CacheDB.SqliteCacheDBHandler import PeerDBHandler
from Tribler.Core.CacheDB.sqlitecachedb import str2bin
from Tribler.Test.Core.test_sqlitecachedbhandler import AbstractDB
from Tribler.dispersy.util import blocking_call_on_reactor_thread


FAKE_PERMID_X = 'fake_permid_x' + '0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'


class TestSqlitePeerDBHandler(AbstractDB):

    def setUp(self):
        super(TestSqlitePeerDBHandler, self).setUp()

        self.p1 = str2bin(
            'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAAA6SYI4NHxwQ8P7P8QXgWAP+v8SaMVzF5+fSUHdAMrs6NvL5Epe1nCNSdlBHIjNjEiC5iiwSFZhRLsr')
        self.p2 = str2bin(
            'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAABo69alKy95H7RHzvDCsolAurKyrVvtDdT9/DzNAGvky6YejcK4GWQXBkIoQGQgxVEgIn8dwaR9B+3U')

        self.pdb = PeerDBHandler(self.session)

        hp = self.pdb.hasPeer(FAKE_PERMID_X)
        assert not hp

    @blocking_call_on_reactor_thread
    def tearDown(self):
        self.pdb.close()
        self.pdb = None
        super(TestSqlitePeerDBHandler, self).tearDown()

    @blocking_call_on_reactor_thread
    def test_getList(self):
        peer1 = self.pdb.getPeer(self.p1)
        peer2 = self.pdb.getPeer(self.p2)
        assert isinstance(peer1, dict)
        assert isinstance(peer2, dict)
        assert peer1[u'peer_id'] == 1, peer1
        assert peer2[u'peer_id'] == 2, peer2

    @blocking_call_on_reactor_thread
    def test_addPeer(self):
        peer_x = {'permid': FAKE_PERMID_X, 'name': 'fake peer x'}
        oldsize = self.pdb.size()
        self.pdb.addPeer(FAKE_PERMID_X, peer_x)
        assert self.pdb.size() == oldsize + 1, (self.pdb.size(), oldsize + 1)

        p = self.pdb.getPeer(FAKE_PERMID_X)
        assert p['name'] == 'fake peer x'

        self.assertEqual(self.pdb.getPeer(FAKE_PERMID_X, 'name'), 'fake peer x')

        self.pdb.deletePeer(FAKE_PERMID_X)
        p = self.pdb.getPeer(FAKE_PERMID_X)
        assert p is None
        assert self.pdb.size() == oldsize

        self.pdb.addPeer(FAKE_PERMID_X, peer_x)
        self.pdb.addPeer(FAKE_PERMID_X, {'permid': FAKE_PERMID_X, 'name': 'faka peer x'})
        p = self.pdb.getPeer(FAKE_PERMID_X)
        self.assertEqual(p['name'], 'faka peer x')

    @blocking_call_on_reactor_thread
    def test_aa_hasPeer(self):
        assert self.pdb.hasPeer(self.p1)
        assert self.pdb.hasPeer(self.p1, check_db=True)
        assert self.pdb.hasPeer(self.p2)
        assert not self.pdb.hasPeer(FAKE_PERMID_X)

    @blocking_call_on_reactor_thread
    def test_deletePeer(self):
        peer_x = {'permid': FAKE_PERMID_X, 'name': 'fake peer x'}
        oldsize = self.pdb.size()
        p = self.pdb.getPeer(FAKE_PERMID_X)
        assert p is None, p

        self.pdb.addPeer(FAKE_PERMID_X, peer_x)
        assert self.pdb.size() == oldsize + 1, (self.pdb.size(), oldsize + 1)
        assert self.pdb.hasPeer(FAKE_PERMID_X)
        p = self.pdb.getPeer(FAKE_PERMID_X)
        assert p is not None

        self.pdb.deletePeer(FAKE_PERMID_X)
        assert not self.pdb.hasPeer(FAKE_PERMID_X)
        assert self.pdb.size() == oldsize

        p = self.pdb.getPeer(FAKE_PERMID_X)
        assert p is None

        self.assertFalse(self.pdb.deletePeer(FAKE_PERMID_X))

    @blocking_call_on_reactor_thread
    def test_add_or_get_peer(self):
        self.assertIsInstance(self.pdb.addOrGetPeerID(FAKE_PERMID_X), int)
        self.assertIsInstance(self.pdb.addOrGetPeerID(FAKE_PERMID_X), int)

    @blocking_call_on_reactor_thread
    def test_get_peer_by_id(self):
        self.assertEqual(self.pdb.getPeerById(1, ['name']), 'Peer 1')
        p = self.pdb.getPeerById(1)
        self.assertEqual(p['name'], 'Peer 1')
        self.assertFalse(self.pdb.getPeerById(1234567))

"""
Module of Credit mining function testing.

Author(s): Mihai Capota, Ardhi Putra
"""
from twisted.internet.defer import inlineCallbacks, succeed

from Tribler.Core.CreditMining.CreditMiningPolicy import BasePolicy
from Tribler.Core.CreditMining.CreditMiningManager import CreditMiningTorrent

from Tribler.Core.simpledefs import DLSTATUS_STOPPED
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.Core.base_test import MockObject


class FakeTorrent(object):

    def __init__(self, infohash, name):
        self.infohash = infohash
        self.name = name

        self.download = MockObject()
        self.download.running = None
        self.download.restart = lambda: setattr(self.download, 'running', True)
        self.download.stop = lambda: setattr(self.download, 'running', False)
        self.download.get_status = lambda: DLSTATUS_STOPPED

        tdef = MockObject()
        tdef.get_infohash = lambda: self.infohash
        self.download.get_def = lambda: tdef


class FakePolicy(BasePolicy):

    def __init__(self, reverse):
        self.reverse = reverse

    def sort(self, torrents):
        return sorted(torrents, key=lambda t: t.infohash, reverse=self.reverse)


class TestCreditMiningManager(TestAsServer):
    """
    Class to test the credit mining manager
    """

    def __init__(self, *argv, **kwargs):
        super(TestCreditMiningManager, self).__init__(*argv, **kwargs)
        # Some fake data for convenience
        self.cid = '0' * 40
        self.infohash = '0' * 40
        self.infohash_bin = '\00' * 20
        self.name = u'torrent'

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        yield super(TestCreditMiningManager, self).setUp()
        self.credit_mining_manager = self.session.lm.credit_mining_manager
        self.credit_mining_manager.settings.max_torrents_active = 4

    def setUpPreSession(self):
        super(TestCreditMiningManager, self).setUpPreSession()
        self.config.set_megacache_enabled(True)
        self.config.set_dispersy_enabled(True)
        self.config.set_libtorrent_enabled(True)
        self.config.set_credit_mining_enabled(True)

    def test_source_add_remove(self):
        self.credit_mining_manager.add_source(self.cid)
        self.assertIn(self.cid, self.credit_mining_manager.sources)
        self.credit_mining_manager.remove_source(self.cid)
        self.assertNotIn(self.cid, self.credit_mining_manager.sources)

    def test_torrent_remove(self):
        removed = []

        def fake_remove(download, **_):
            removed.append(download.get_def().get_infohash())
            return succeed(None)

        self.session.remove_download = fake_remove

        torrents = {i: FakeTorrent(i, self.name + str(i)) for i in range(5)}
        self.credit_mining_manager.add_source(self.cid)
        for infohash, torrent in torrents.iteritems():
            self.credit_mining_manager.torrents[infohash] = torrent
            torrent.sources = set([self.cid])
        self.credit_mining_manager.remove_source(self.cid)
        self.assertTrue(len(self.credit_mining_manager.torrents) == 0)
        self.assertItemsEqual(torrents.keys(), removed)

    def test_torrent_insert(self):
        self.credit_mining_manager.add_source(self.cid)
        self.credit_mining_manager.on_torrent_insert(self.cid, self.infohash, self.name)
        self.assertIn(self.infohash, self.credit_mining_manager.torrents)
        self.assertTrue(self.session.get_download(self.infohash_bin))

    def test_torrent_insert_unknown_source(self):
        self.credit_mining_manager.on_torrent_insert(self.cid, self.infohash, self.name)
        self.assertNotIn(self.infohash, self.credit_mining_manager.torrents)
        self.assertFalse(self.session.get_download(self.infohash_bin))

    def test_torrent_insert_duplicate(self):
        self.credit_mining_manager.torrents[self.infohash] = CreditMiningTorrent(self.infohash, self.name)
        self.credit_mining_manager.on_torrent_insert(self.cid, self.infohash, self.name)
        torrent = self.credit_mining_manager.torrents.values()[0]

        self.credit_mining_manager.on_torrent_insert(self.cid, self.infohash, self.name)
        self.assertIn(torrent, self.credit_mining_manager.torrents.values())
        self.assertFalse(self.session.get_download(self.infohash_bin))

        # When we add a duplicate from another known source, the set of sources should update
        source = '1' * 40
        self.credit_mining_manager.add_source(source)
        self.credit_mining_manager.on_torrent_insert(source, self.infohash, self.name)
        self.assertIn(source, torrent.sources)
        self.assertIn(torrent, self.credit_mining_manager.torrents.values())
        self.assertFalse(self.session.get_download(self.infohash_bin))

    def test_torrent_insert_limit(self):
        self.credit_mining_manager.add_source(self.cid)
        self.credit_mining_manager.settings.max_torrents_listed = 0
        self.credit_mining_manager.on_torrent_insert(self.cid, self.infohash, self.name)
        self.assertNotIn(self.infohash, self.credit_mining_manager.torrents)
        self.assertFalse(self.session.get_download(self.infohash_bin))

    def test_torrent_insert_existing_download(self):
        self.credit_mining_manager.add_source(self.cid)
        self.session.lm.downloads[self.infohash_bin] = MockObject()
        self.credit_mining_manager.on_torrent_insert(self.cid, self.infohash, self.name)
        self.assertNotIn(self.infohash, self.credit_mining_manager.torrents)
        del self.session.lm.downloads[self.infohash_bin]

    def test_select_torrent_single_policy(self):
        self.credit_mining_manager.monitor_downloads = lambda: None
        self.credit_mining_manager.policies = [FakePolicy(reverse=False)]

        for i in range(5):
            self.credit_mining_manager.torrents[i] = FakeTorrent(i, self.name + str(i))

        self.credit_mining_manager.select_torrents()

        # Torrents 0,1,2,3 should be running according to FakePolicy(reverse=False)
        # Torrent 4 should not be running.
        torrents = self.credit_mining_manager.torrents
        self.assertTrue(all([torrents[i].download.running for i in [0, 1, 2, 3]]))
        self.assertFalse(torrents[4].download.running)

    def test_select_torrent_multiple_policies(self):
        self.credit_mining_manager.monitor_downloads = lambda: None
        self.credit_mining_manager.policies = [FakePolicy(reverse=False), FakePolicy(reverse=True)]

        for i in range(5):
            self.credit_mining_manager.torrents[i] = FakeTorrent(i, self.name + str(i))

        self.credit_mining_manager.select_torrents()

        # Torrents 0,1 should be running according to FakePolicy(reverse=False)
        # Torrents 3,4 should be running according to FakePolicy(reverse=True)
        # Torrent 2 should not be running.
        torrents = self.credit_mining_manager.torrents
        self.assertTrue(all([torrents[i].download.running for i in [0, 1, 3, 4]]))
        self.assertFalse(torrents[2].download.running)

    def test_monitor_download_start_selecting(self):
        self.credit_mining_manager.monitor_downloads([])
        self.assertFalse(self.credit_mining_manager.select_lc.running)

        # If the number of torrents > then max_torrents_active, the select_lc LoopingCall should start
        for i in range(5):
            self.credit_mining_manager.torrents[i] = FakeTorrent(i, self.name + str(i))
        self.credit_mining_manager.monitor_downloads([])
        self.assertFalse(self.credit_mining_manager.select_lc.running)

    def test_monitor_download_insert_torrent(self):
        tdef = MockObject()
        tdef.get_infohash = lambda: self.infohash_bin
        tdef.get_name = lambda: self.name

        download = MockObject()
        download.get_def = lambda: tdef
        download.force_recheck = lambda: None
        download.get_credit_mining = lambda: True

        ds = MockObject()
        ds.get_download = lambda: download
        ds.get_status = lambda: DLSTATUS_STOPPED
        ds.seeding_uploaded = 0

        # Credit mining downloads should automatically be inserted in to self.credit_mining_mananger.torrents
        self.credit_mining_manager.monitor_downloads([ds])
        self.assertIn(self.infohash, self.credit_mining_manager.torrents)
        self.assertEqual(self.credit_mining_manager.torrents[self.infohash].download, download)

        # Normal downloads should be ignored
        infohash2_bin = '\01' * 20
        infohash2 = '01' * 20
        tdef.get_infohash = lambda: infohash2_bin
        download.get_credit_mining = lambda: False
        self.credit_mining_manager.monitor_downloads([ds])
        self.assertNotIn(infohash2, self.credit_mining_manager.torrents)

    def test_shutdown(self):
        self.credit_mining_manager.add_source(self.cid)
        self.credit_mining_manager.shutdown(remove_downloads=True)
        self.assertNotIn(self.cid, self.credit_mining_manager.sources)

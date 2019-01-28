"""
Module of Credit mining function testing.

Author(s): Mihai Capota, Ardhi Putra
"""
from __future__ import absolute_import

import logging
import os
import sys

from six.moves import xrange

from twisted.internet.defer import inlineCallbacks, succeed

from Tribler.Core.CreditMining.CreditMiningManager import CreditMiningTorrent
from Tribler.Core.CreditMining.CreditMiningPolicy import BasePolicy, MB
from Tribler.Core.simpledefs import DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING, DLSTATUS_STOPPED, DOWNLOAD, \
    NTFY_CREDIT_MINING, NTFY_ERROR
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.test_as_server import BaseTestCase, TestAsServer


class FakeTorrent(object):

    def __init__(self, infohash, name):
        self.infohash = infohash
        self.name = name

        self.download = MockObject()
        self.download.upload_mode = False
        self.download.running = None
        self.download.restart = lambda: setattr(self.download, 'running', True)
        self.download.stop = lambda: setattr(self.download, 'running', False)
        self.download.get_credit_mining = lambda: True
        self.download.get_handle = lambda: succeed(self.handle)

        self.tdef = MockObject()
        self.tdef.get_infohash = lambda: self.infohash
        self.tdef.get_trackers_as_single_tuple = lambda: ()
        self.tdef.get_length = lambda: 1024 * 1024
        self.download.get_def = lambda: self.tdef

        self.ds = MockObject()
        self.ds.get_status = lambda: DLSTATUS_STOPPED
        self.ds.get_progress = lambda: 0.0
        self.download.get_state = lambda: self.ds

        self.handle = MockObject()
        self.handle.set_upload_mode = lambda enable: setattr(self.download, 'upload_mode', enable)
        self.get_storage = lambda length=self.tdef.get_length(): (length, 0)


class FakePolicy(BasePolicy):

    def __init__(self, reverse):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.reverse = reverse
        self.torrents = {}

    def sort(self, torrents):
        return sorted(torrents, key=lambda t: t.infohash, reverse=self.reverse)


class TestCreditMiningTorrent(BaseTestCase):

    def test_credit_mining_get_storage(self):
        infohash_bin = '0' * 40
        name = u'torrent'

        tdef = MockObject()
        tdef.get_infohash = lambda: infohash_bin
        tdef.get_name = lambda: name
        tdef.get_length = lambda: 1000

        state = MockObject()
        state.get_progress = lambda: 0.5

        download = MockObject()
        download.get_def = lambda: tdef
        download.get_state = lambda: state

        torrent = CreditMiningTorrent(infohash_bin, name, download=download)
        total, downloaded = torrent.get_storage()
        self.assertEqual(total, 1000)
        self.assertEqual(downloaded, 500)


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

    @inlineCallbacks
    def setUp(self):
        yield super(TestCreditMiningManager, self).setUp()
        self.credit_mining_manager = self.session.lm.credit_mining_manager
        self.credit_mining_manager.settings.max_torrents_active = 4

    def setUpPreSession(self):
        super(TestCreditMiningManager, self).setUpPreSession()
        self.config.set_megacache_enabled(True)
        self.config.set_dispersy_enabled(True)
        self.config.set_libtorrent_enabled(True)
        self.config.set_credit_mining_enabled(True)
        self.config.set_market_community_enabled(False)

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
        self.credit_mining_manager.monitor_downloads = lambda _: None
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
        self.credit_mining_manager.monitor_downloads = lambda _: None
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

    def test_select_torrent_disk_space_limit(self):
        self.credit_mining_manager.settings.max_disk_space = 2 * 1024 * 1024
        self.credit_mining_manager.monitor_downloads = lambda _: None
        self.credit_mining_manager.policies = [FakePolicy(reverse=False), FakePolicy(reverse=True)]

        for i in range(5):
            self.credit_mining_manager.torrents[i] = FakeTorrent(i, self.name + str(i))

        self.credit_mining_manager.select_torrents()

        # Torrent 0 should be running according to FakePolicy(reverse=False)
        # Torrent 4 should be running according to FakePolicy(reverse=True)
        # Torrents 1,2,3 should not be running due to max_disk_space.
        torrents = self.credit_mining_manager.torrents
        self.assertTrue(all([torrents[i].download.running for i in [0, 4]]))
        self.assertFalse(any([torrents[i].download.running for i in [1, 2, 3]]))

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
        ds.get_total_transferred = lambda _: 0

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

    def test_monitor_downloads(self):
        """
        Test downloads monitoring works as expected.
        Scenario:
        --------------------------------------------
        Infohash    Status          Download     Upload
            0       Downloading       0 MB        5 MB
            1       Seeding           10 MB       15 MB
            2       Stopped           20 MB       25 MB
            3       Downloading       30 MB       35 MB
            4       Seeding           40 MB       45 MB
            5       Downloading       50 MB       55 MB

        Results:
            Seeding = 3, Downloading = 2, Stopped = 1
            Bytes_up = 180 MB, Bytes_down = 150 MB
        """
        scenario = MockObject()
        scenario.status = [DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING, DLSTATUS_STOPPED, DLSTATUS_DOWNLOADING,
                           DLSTATUS_SEEDING, DLSTATUS_DOWNLOADING]
        scenario.downloads = [10 * i * MB for i in xrange(6)]
        scenario.uploads = [(10 * i + 5) * MB for i in xrange(6)]

        download = MockObject()
        download.tdef = MockObject()
        download.tdef.get_infohash = lambda: '\00' * 20
        download.tdef.get_name = lambda: self.name + str(i)
        download.get_def = lambda _download=download: _download.tdef
        download.force_recheck = lambda: None
        download.get_credit_mining = lambda: True
        download.handle = None

        download_states = []
        for i in xrange(6):
            ds = MockObject()
            ds.get_download = lambda: download
            ds.get_status = lambda _i=i: scenario.status[_i]
            ds.get_total_transferred = lambda transfer_type, _i=i: scenario.downloads[_i] \
                if transfer_type == DOWNLOAD else scenario.uploads[_i]
            download_states.append(ds)

        # We are only interested in monitoring the states, rathen than policies here.
        self.credit_mining_manager.policies = []
        seeding, downloading, stopped, bytes_down, bytes_up = \
            self.credit_mining_manager.monitor_downloads(download_states)
        self.assertEqual(seeding, 3)
        self.assertEqual(downloading, 2)
        self.assertEqual(stopped, 1)
        self.assertEqual(bytes_down, sum(scenario.downloads))
        self.assertEqual(bytes_up, sum(scenario.uploads))

    def test_check_free_space(self):
        self.credit_mining_manager.cancel_pending_task('check_disk_space')
        self.credit_mining_manager.settings.low_disk_space = 1024 ** 2

        downloads = [FakeTorrent(i, self.name + str(i)).download for i in range(5)]
        self.session.get_downloads = lambda: downloads

        # Check that all download have upload_mode=False if we have enough disk space
        self.credit_mining_manager.get_free_disk_space = lambda: 2 * 1024 ** 2
        self.credit_mining_manager.check_disk_space()
        self.assertFalse(any([d.upload_mode for d in downloads]))

        # Check that all download have upload_mode=True if we do not have enough disk space
        self.credit_mining_manager.get_free_disk_space = lambda: 1
        self.credit_mining_manager.check_disk_space()
        self.assertTrue(all([d.upload_mode for d in downloads]))

    def test_get_reserved_space_left(self):
        """
        Tests the reserved space left on disk for credit mining.
        Scenario:
            - 10 torrents,
            - Individual torrent size: 100MB
            - Individual download progress: 50%
        """
        num_downloads = 10
        used_space = num_downloads * 100 * MB * 0.5
        max_space = self.credit_mining_manager.settings.max_disk_space

        downloads = []
        for i in xrange(num_downloads):
            download = FakeTorrent(i, self.name + str(i)).download
            download.get_def().get_length = lambda: 100 * MB
            download.get_state().get_progress = lambda: 0.5
            download.get_state().get_status = lambda: DLSTATUS_DOWNLOADING
            downloads.append(download)

        self.credit_mining_manager.session.get_downloads = lambda: downloads

        space_left = self.credit_mining_manager.get_reserved_space_left()
        self.assertEqual(space_left, max_space - used_space)

    def test_check_free_space_with_non_existing_path(self):
        self.credit_mining_manager.cancel_pending_task('check_disk_space')
        self.assertFalse(self.credit_mining_manager.upload_mode)

        # Given: low disk space available
        self.credit_mining_manager.settings.low_disk_space = 1024 ** 2
        self.credit_mining_manager.get_free_disk_space = lambda: 1

        # Should set credit mining to upload state unless the mining path is invalid or does not exist
        test_path = os.path.join(self.credit_mining_manager.session.config.get_state_dir(), "fake_dir")
        self.credit_mining_manager.settings.save_path = test_path
        self.credit_mining_manager.check_disk_space()
        self.assertFalse(self.credit_mining_manager.upload_mode)

    def test_check_mining_directory(self):
        """ Tests mining directory exists. If does not exist, it should be created. """
        def fake_notifier_notify(miner, subject, changeType, *args):
            miner.subject = subject
            miner.changeType = changeType
            miner.args = args

        def on_mining_shutdown(miner):
            miner.shutdown_task_manager()
            miner.shutdown_called = True

        self.credit_mining_manager.shutdown_called = False
        self.credit_mining_manager.shutdown = lambda: on_mining_shutdown(self.credit_mining_manager)
        self.credit_mining_manager.session.notifier.notify = lambda subject, changeType, object_id, args:\
            fake_notifier_notify(self.credit_mining_manager, subject, changeType, args)

        test_path = os.path.join(self.credit_mining_manager.session.config.get_state_dir(), "fake_dir")
        self.assertFalse(os.path.exists(test_path))

        self.credit_mining_manager.settings.save_path = test_path
        self.credit_mining_manager.check_mining_directory()

        self.assertTrue(os.path.exists(test_path))
        self.assertEqual(self.credit_mining_manager.subject, NTFY_CREDIT_MINING)
        self.assertEqual(self.credit_mining_manager.changeType, NTFY_ERROR)
        self.assertIsNotNone(self.credit_mining_manager.args)

        # Set the path to some non-allowed directory
        test_path = "C:/Windows/system32/credit_mining" if sys.platform == 'win32' else "/root/credit_mining"
        self.credit_mining_manager.settings.save_path = test_path
        self.credit_mining_manager.check_mining_directory()

        self.assertFalse(os.path.exists(test_path))
        self.assertEqual(self.credit_mining_manager.subject, NTFY_CREDIT_MINING)
        self.assertEqual(self.credit_mining_manager.changeType, NTFY_ERROR)
        self.assertIsNotNone(self.credit_mining_manager.args)
        self.assertTrue(self.credit_mining_manager.shutdown_called)

    def test_add_download_while_credit_mining(self):
        infohash_str = '00' * 20
        infohash_bin = '\00' * 20
        magnet = 'magnet:?xt=urn:btih:' + infohash_str

        torrent = FakeTorrent(infohash_bin, self.name)
        self.credit_mining_manager.torrents[infohash_str] = torrent

        # Credit mining downloads should get removed
        torrent.download.removed = False
        self.session.get_download = lambda _: torrent.download
        self.session.remove_download = lambda d: setattr(d, 'removed', True) or \
                                                 setattr(self.session, 'get_download', lambda _: None) or \
                                                 succeed(None)
        self.session.start_download_from_uri(magnet)
        self.assertNotIn(infohash_str, self.credit_mining_manager.torrents)
        self.assertTrue(torrent.download.removed)

        # Non credit mining downloads should not get removed
        torrent.download.removed = False
        torrent.download.get_credit_mining = lambda: False
        self.session.get_download = lambda _: torrent.download
        self.assertFalse(torrent.download.removed)

    def test_shutdown(self):
        self.credit_mining_manager.add_source(self.cid)
        self.credit_mining_manager.shutdown(remove_downloads=True)
        self.assertNotIn(self.cid, self.credit_mining_manager.sources)

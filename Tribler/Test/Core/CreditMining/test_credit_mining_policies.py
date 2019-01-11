"""
Module of Credit mining function testing.

Author(s): Mihai Capota, Ardhi Putra
"""
from __future__ import absolute_import

import time

from six.moves import xrange

from twisted.internet.defer import inlineCallbacks

from Tribler.Core.CreditMining.CreditMiningManager import CreditMiningTorrent
from Tribler.Core.CreditMining.CreditMiningPolicy import InvestmentPolicy, InvestmentState, MB, RandomPolicy, \
    SeederRatioPolicy, UploadPolicy, WEEK
from Tribler.Core.simpledefs import DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING, DLSTATUS_STOPPED, UPLOAD
from Tribler.Test.Core.base_test import MockObject, TriblerCoreTest


class TestCreditMiningPolicies(TriblerCoreTest):
    """
    Class to test the credit mining policies
    """

    @inlineCallbacks
    def setUp(self):
        yield super(TestCreditMiningPolicies, self).setUp()
        self.torrents = [CreditMiningTorrent(i, 'test torrent %d' % i) for i in range(10)]

    def test_random_policy(self):
        policy = RandomPolicy()

        sorted_torrents = policy.sort(self.torrents)
        self.assertItemsEqual(self.torrents, sorted_torrents, 'Arrays contains different torrents')

    def test_seederratio_policy(self):
        for i, torrent in enumerate(self.torrents):
            mock_ds = MockObject()
            mock_ds.get_num_seeds_peers = lambda index=i: (index, 1)
            torrent.state = mock_ds

        policy = SeederRatioPolicy()
        sorted_torrents = policy.sort(self.torrents)
        expected_torrents = list(reversed(self.torrents))

        self.assertItemsEqual(sorted_torrents, expected_torrents, 'Arrays contains different torrents')
        self.assertListEqual(sorted_torrents, expected_torrents, 'Array is not sorted properly')

    def test_upload_based_policy_sort(self):
        """
        Tests both UploadPolicy and InvestmentPolicy since they both sorts torrents based on upload.
        """

        def setup_torrents(torrents):
            for i, torrent in enumerate(torrents):
                mock_status = MockObject()
                mock_status.total_upload = i * i
                mock_status.active_time = i

                mock_handle = MockObject()
                mock_handle.status = lambda status=mock_status: status

                mock_dl = MockObject()
                mock_dl.handle = mock_handle

                torrent.download = mock_dl
            return torrents

        # Test Upload policy
        upload_policy = UploadPolicy()
        torrent_collection1 = setup_torrents(self.torrents)
        sorted_torrents1 = upload_policy.sort(torrent_collection1)
        expected_torrents1 = list(reversed(torrent_collection1))

        self.assertItemsEqual(sorted_torrents1, expected_torrents1, 'Arrays contains different torrents')
        self.assertListEqual(sorted_torrents1, expected_torrents1, 'Array is not sorted properly')

        # Test Investment policy
        investment_policy = InvestmentPolicy()
        torrent_collection2 = setup_torrents(self.torrents)
        sorted_torrents2 = investment_policy.sort(torrent_collection2)
        expected_torrents2 = list(reversed(torrent_collection2))

        self.assertItemsEqual(sorted_torrents2, expected_torrents2, 'Arrays contains different torrents')
        self.assertListEqual(sorted_torrents2, expected_torrents2, 'Array is not sorted properly')

    def test_schedule_start(self):
        policy = UploadPolicy()
        policy.schedule(self.torrents[0])
        self.assertTrue(self.torrents[0].to_start)
        policy.schedule(self.torrents[1], to_start=False)
        self.assertFalse(self.torrents[1].to_start)

    def test_basic_policy_run(self):
        """
        Test running an iteration of basic policy.

        Scenario: There are 10 torrents with infohashes ordered as 0-9 and the torrents with odd infohashes
        are downloading while the rest are stopped. In the next iteration, we assume that all the
        torrents with infohashes as multiple of 3 are scheduled to start and the rest to be stopped.

        The scenario is represented in the table below:
        Infohash    Status         To Start     ->  Result
            0       STOPPED         True            Started
            1       DOWNLOADING     False           Stopped
            2       STOPPED         False           Do Nothing
            3       DOWNLOADING     True            Do Nothing
            4       STOPPED         False           Do Nothing
            5       DOWNLOADING     False           Stopped
            6       STOPPED         True            Started
            7       DOWNLOADING     False           Stopped
            8       STOPPED         False           Do Nothing
            9       DOWNLOADING     True            Do Nothing

        At the end of the iteration, the following result is expected:
        Started = 2
        Stopped = 3
        """

        scenario = MockObject()
        scenario.to_start = [True, False, False, True, False, False, True, False, False, True]
        scenario.torrent_status = [DLSTATUS_STOPPED, DLSTATUS_DOWNLOADING, DLSTATUS_STOPPED,
                                   DLSTATUS_DOWNLOADING, DLSTATUS_STOPPED, DLSTATUS_DOWNLOADING,
                                   DLSTATUS_STOPPED, DLSTATUS_DOWNLOADING, DLSTATUS_STOPPED,
                                   DLSTATUS_DOWNLOADING]

        # Any BasicPolicy implementation is fine.
        policy = UploadPolicy()

        def get_status(scenario, index):
            return scenario.torrent_status[index]

        for i, torrent in enumerate(self.torrents):
            torrent.download = MockObject()
            torrent.download.state = MockObject()
            torrent.download.state.get_status = lambda _scenario=scenario, index=i: get_status(_scenario, index)
            torrent.download.get_state = lambda _torrent=torrent: _torrent.download.state
            torrent.download.restart = lambda: None
            torrent.download.stop = lambda: None
            policy.schedule(torrent, to_start=scenario.to_start[i])

        policy.run()
        self.assertEqual(policy.started_in_iteration, 2)
        self.assertEqual(policy.stopped_in_iteration, 3)

    def test_basic_policy_run_with_no_downloads(self):
        """
        Test running an iteration of basic policy without any downloads.
        Policy should just skip those torrents.
        """
        policy = UploadPolicy()
        for torrent in self.torrents:
            policy.schedule(torrent)

        policy.run()
        self.assertEqual(policy.started_in_iteration, 0)
        self.assertEqual(policy.stopped_in_iteration, 0)


class TestInvestmentPolicy(TriblerCoreTest):
    """
    Class to test investment policy.
    """

    @inlineCallbacks
    def setUp(self):
        yield super(TestInvestmentPolicy, self).setUp()
        self.torrents = [CreditMiningTorrent(i, 'test torrent %d' % i) for i in range(10)]
        self.policy = InvestmentPolicy()

    def test_default_states(self):
        default_states = self.policy.get_default_investment_states()
        self.assertEqual(len(default_states), 20)

        self.assertEqual(default_states[0].state_id, 0)
        self.assertEqual(default_states[0].upload_mode, False)
        self.assertEqual(default_states[0].bandwidth_limit, 5 * MB)

        self.assertEqual(default_states[19].state_id, 19)
        self.assertEqual(default_states[19].upload_mode, True)
        self.assertEqual(default_states[19].bandwidth_limit, 163 * MB)

    def test_state_is_promotion_ready(self):
        download_state1 = InvestmentState(1, False, 5*MB, promotion_ratio=1)
        self.assertFalse(download_state1.is_promotion_ready(4 * MB, 3 * MB))
        self.assertTrue(download_state1.is_promotion_ready(5.1 * MB, 3 * MB))
        self.assertFalse(download_state1.is_promotion_ready(3 * MB, 6 * MB))

        upload_state1 = InvestmentState(1, True, 5 * MB, promotion_ratio=1)
        self.assertFalse(upload_state1.is_promotion_ready(5 * MB, 3 * MB))
        self.assertTrue(upload_state1.is_promotion_ready(5 * MB, 6 * MB))

        upload_state2 = InvestmentState(1, True, 5 * MB, promotion_ratio=2)
        self.assertFalse(upload_state2.is_promotion_ready(5 * MB, 6 * MB))
        self.assertTrue(upload_state2.is_promotion_ready(5 * MB, 10 * MB))

    def test_compute_investment_state(self):
        downloads = [1, 4, 5, 8, 10, 110, 150, 1000]
        uploads = [0, 2, 3, 7, 15, 90, 180, 1000]
        expected_states = [0, 0, 1, 4, 6, 17, 18, 19]

        for i in xrange(len(downloads)):
            computed_state = self.policy.compute_state(downloads[i] * MB, uploads[i] * MB)
            self.assertEqual(expected_states[i], computed_state)

    def test_get_reserved_bytes(self):
        self.torrents[0].get_storage = lambda: (10 * MB, 4 * MB)

        # For state 0 with 5MB bandwidth limit
        self.torrents[0].mining_state['state_id'] = 0
        self.assertTrue(self.policy.investment_states[0].bandwidth_limit, 5 * MB)
        self.assertEqual(self.policy.get_reserved_bytes(self.torrents[0]), 1 * MB)

        # For state 1 with 5MB bandwidth limit
        self.torrents[0].mining_state['state_id'] = 1
        self.assertTrue(self.policy.investment_states[0].bandwidth_limit, 5 * MB)
        self.assertEqual(self.policy.get_reserved_bytes(self.torrents[0]), 1 * MB)

        # For state 2 with 7MB bandwidth limit
        self.torrents[0].mining_state['state_id'] = 2
        self.assertTrue(self.policy.investment_states[1].bandwidth_limit, 7 * MB)
        self.assertEqual(self.policy.get_reserved_bytes(self.torrents[0]), 3 * MB)

    def test_schedule_start(self):
        self.torrents[0].download = MockObject()
        self.torrents[0].state = MockObject()
        self.torrents[0].state.get_total_transferred = lambda _: 0

        time_before = time.time()
        self.policy.schedule_start(self.torrents[0])
        self.assertTrue(self.torrents[0].to_start)
        added_time = self.torrents[0].mining_state['start_time']
        self.assertTrue(added_time >= time_before)

        # Check adding torrent is done only once on subsequent start
        start_time = self.torrents[0].mining_state['start_time']
        self.torrents[0].to_start = False
        self.policy.schedule_start(self.torrents[0])
        self.assertTrue(self.torrents[0].to_start)
        self.assertEqual(start_time, self.torrents[0].mining_state['start_time'])

    def test_promote_torrent(self):

        def set_upload_mode(upload_mode, torrent):
            torrent.upload_mode = upload_mode

        torrent = self.torrents[0]
        torrent.download = MockObject()
        torrent.download.set_upload_mode = lambda upload_mode, _torrent=torrent: set_upload_mode(upload_mode, _torrent)
        torrent.download.restart = lambda: None

        # Promote from state 0
        torrent.upload_mode = False
        torrent.mining_state['state_id'] = 0
        self.policy.promote_torrent(torrent)
        self.assertEqual(torrent.mining_state['state_id'], 1)
        self.assertTrue(torrent.upload_mode)

        # Promote from state 1
        torrent.upload_mode = True
        torrent.mining_state['state_id'] = 1
        self.policy.promote_torrent(torrent)
        self.assertEqual(torrent.mining_state['state_id'], 2)
        self.assertFalse(torrent.upload_mode)

        # Promote from last state
        last_state = len(self.policy.investment_states) - 1
        torrent.upload_mode = True  # Last state is always in upload mode
        torrent.mining_state['state_id'] = last_state
        self.policy.promote_torrent(torrent)
        self.assertEqual(torrent.mining_state['state_id'], last_state)
        self.assertTrue(torrent.upload_mode)

    def test_investment_policy_run(self):
        """
        Test running an iteration of investment policy.

        Scenario
        ------------------------------------------------
        Infohash, Level, Download, Upload, To start,  ETA,  Status     -->  Expected Result
            0       5        20      16       Yes      0    Downloading     Upload mode
            1       0        4       2        Yes      1    Downloading     Stop
            2       1        5       8        Yes      1    Seeding         Promote -> Download mode
            3       9        22      23       Yes      1    Seeding         Promote -> Download mode
            4       9        30      25       No       1    Downloading     Stop
            5       0        4       3        Yes      1    Downloading     Stop; stale
            6       12       40      35       Yes      1    Stopped         Download mode
            7       15       50      40       No       1    Seeding         Stop
            8       18       160     120      Yes      1    Downloading     Do nothing -> Download mode
            9       19       163     170      Yes      1    Stopped         Promote -> Upload mode

        At the end of the iteration, the following result is expected:
        Started = 6         # Includes downloading and seeding torrents
        Stopped = 4
        Upload mode = 2     # New torrents set in upload mode
        Download mode = 3   # New torrents set in download mode
        """

        scenario = MockObject()
        scenario.downloads = [20, 4, 5, 22, 30, 4, 40, 50, 160, 163]
        scenario.uploads = [16, 2, 8, 23, 25, 3, 35, 40, 120, 170]
        scenario.levels = [5, 0, 1, 9, 9, 0, 12, 15, 18, 19]
        scenario.to_start = [True, False, True, True, False, True, True, False, True, True]
        scenario.torrent_status = [DLSTATUS_DOWNLOADING, DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING,
                                   DLSTATUS_SEEDING, DLSTATUS_DOWNLOADING, DLSTATUS_DOWNLOADING,
                                   DLSTATUS_STOPPED, DLSTATUS_SEEDING, DLSTATUS_DOWNLOADING,
                                   DLSTATUS_STOPPED]

        def get_status(scenario, torrent):
            return scenario.torrent_status[torrent.infohash]

        def get_eta(torrent):
            return 0 if torrent.infohash == 0 else 1

        def get_total_transferred(scenario, torrent, transfer_type):
            if transfer_type == UPLOAD:
                return scenario.uploads[torrent.infohash] * MB
            return scenario.downloads[torrent.infohash] * MB

        def get_mining_state(scenario, torrent):
            mining_state = dict()
            mining_state['initial_upload'] = 0
            mining_state['initial_download'] = 0
            mining_state['state_id'] = scenario.levels[torrent.infohash]
            return mining_state

        for torrent in self.torrents:
            torrent.download = MockObject()
            torrent.download.state = MockObject()
            torrent.download.state.get_eta = lambda _torrent=torrent: get_eta(_torrent)
            torrent.download.state.get_total_transferred = lambda transfer_type, _torrent=torrent, _scenario=scenario: \
                get_total_transferred(_scenario, _torrent, transfer_type)
            torrent.mining_state = get_mining_state(scenario, torrent)
            torrent.download.state.get_status = lambda _scenario=scenario, _torrent=torrent: \
                get_status(_scenario, _torrent)
            torrent.download.get_state = lambda _torrent=torrent: _torrent.download.state
            torrent.download.set_upload_mode = lambda _: None
            torrent.download.restart = lambda: None
            torrent.download.stop = lambda: None
            torrent.start_time = time.time() - WEEK - 1 if torrent.infohash == 5 else time.time()

            # Schedule torrent to start or stop
            self.policy.schedule(torrent, to_start=scenario.to_start[torrent.infohash])

        # Torrents are ready, run the policy
        self.policy.run()

        self.assertEqual(self.policy.started_in_iteration, 6)
        self.assertEqual(self.policy.stopped_in_iteration, 4)
        self.assertEqual(self.policy.num_downloading_in_iteration, 3)
        self.assertEqual(self.policy.num_uploading_in_iteration, 2)

    def test_investment_policy_run_with_no_downloads(self):
        """
        Test running an iteration of investment policy without any downloads.
        Policy should just skip those torrents.
        """
        for torrent in self.torrents:
            self.policy.schedule(torrent)

        self.policy.run()
        self.assertEqual(self.policy.started_in_iteration, 0)
        self.assertEqual(self.policy.stopped_in_iteration, 0)

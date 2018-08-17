"""
Module of Credit mining function testing.

Author(s): Mihai Capota, Ardhi Putra
"""

from twisted.internet.defer import inlineCallbacks

from Tribler.Core.CreditMining.CreditMiningPolicy import RandomPolicy, SeederRatioPolicy, UploadPolicy
from Tribler.Core.CreditMining.CreditMiningManager import CreditMiningTorrent
from Tribler.Test.Core.base_test import TriblerCoreTest, MockObject


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

    def test_upload_policy(self):
        for i, torrent in enumerate(self.torrents):
            mock_status = MockObject()
            mock_status.total_upload = i * i
            mock_status.active_time = i

            mock_handle = MockObject()
            mock_handle.status = lambda status=mock_status: status

            mock_dl = MockObject()
            mock_dl.handle = mock_handle

            torrent.download = mock_dl

        policy = UploadPolicy()
        sorted_torrents = policy.sort(self.torrents)
        expected_torrents = list(reversed(self.torrents))

        self.assertItemsEqual(sorted_torrents, expected_torrents, 'Arrays contains different torrents')
        self.assertListEqual(sorted_torrents, expected_torrents, 'Array is not sorted properly')

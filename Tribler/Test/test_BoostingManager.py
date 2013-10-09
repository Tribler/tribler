# -*- coding: utf-8 -*-
# Written by Mihai Capotă
# pylint: disable=too-many-public-methods
"""Test Tribler.Policies.BoostingManager"""

import mock
import random
import unittest

import Tribler.Policies.BoostingManager as bm

class TestBoostingManagerPolicies(unittest.TestCase):

    def setUp(self):
        random.seed(0)
        self.session = mock.Mock()
        self.session.get_download = lambda i: i % 2
        self.torrents = dict()
        for i in range(1, 11):
            mock_metainfo = mock.Mock()
            mock_metainfo.get_id.return_value = i
            self.torrents[i] = {"metainfo": mock_metainfo, "num_seeders": i,
                                "num_leechers": i-1, "creation_date": i}

    def test_RandomPolicy(self):
        policy = bm.RandomPolicy(self.session)
        torrents_start, torrents_stop = policy.apply(self.torrents, 2)
        ids_start = [torrent["metainfo"].get_id() for torrent in
                     torrents_start]
        self.assertEqual(ids_start, [4, 8])
        ids_stop = [torrent["metainfo"].get_id() for torrent in torrents_stop]
        self.assertEqual(ids_stop, [3, 9, 5, 7, 1])

    def test_SeederRatioPolicy(self):
        policy = bm.SeederRatioPolicy(self.session)
        torrents_start, torrents_stop = policy.apply(self.torrents, 6)
        ids_start = [torrent["metainfo"].get_id() for torrent in
                     torrents_start]
        self.assertEqual(ids_start, [10, 8, 6])
        ids_stop = [torrent["metainfo"].get_id() for torrent in torrents_stop]
        self.assertEqual(ids_stop, [3, 1])

    def test_CreationDatePolicy(self):
        policy = bm.CreationDatePolicy(self.session)
        torrents_start, torrents_stop = policy.apply(self.torrents, 5)
        ids_start = [torrent["metainfo"].get_id() for torrent in
                     torrents_start]
        self.assertEqual(ids_start, [10, 8, 6])
        ids_stop = [torrent["metainfo"].get_id() for torrent in torrents_stop]
        self.assertEqual(ids_stop, [5, 3, 1])

if __name__ == "__main__":
    unittest.main()

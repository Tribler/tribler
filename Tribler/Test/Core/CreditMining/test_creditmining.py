"""
Module of Credit mining function testing.

Author(s): Mihai Capota, Ardhi Putra
"""

import binascii
import random
import re
from twisted.internet.defer import inlineCallbacks
from unittest import skip

import Tribler.Core.CreditMining.BoostingManager as bm
from Tribler.Core.CreditMining.BoostingPolicy import CreationDatePolicy, SeederRatioPolicy, RandomPolicy
from Tribler.Core.CreditMining.BoostingSource import ent2chr
from Tribler.Core.CreditMining.credit_mining_util import levenshtein_dist, source_to_string
from Tribler.Core.DownloadConfig import DefaultDownloadStartupConfig
from Tribler.Core.Libtorrent.LibtorrentDownloadImpl import LibtorrentDownloadImpl
from Tribler.Core.Utilities import utilities
from Tribler.Test.Core.CreditMining.mock_creditmining import MockMeta, MockLtPeer, MockLtSession, MockLtTorrent, \
    MockPeerId
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestBoostingManagerPolicies(TriblerCoreTest):
    """
    The class to test core function of credit mining policies
    """

    def __init__(self, *argv, **kwargs):
        super(TestBoostingManagerPolicies, self).__init__(*argv, **kwargs)
        self.session = MockLtSession()

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        yield super(TestBoostingManagerPolicies, self).setUp()
        self.torrents = dict()
        for i in xrange(1, 11):
            mock_metainfo = MockMeta(i)

            self.torrents[i] = {"metainfo": mock_metainfo, "num_seeders": i,
                                "num_leechers": i-1, "creation_date": i}

    def test_random_policy(self):
        """
        testing random policy
        """
        rdrwh = random.WichmannHill(0)
        policy = RandomPolicy(self.session)
        policy.key = lambda _: rdrwh.random()

        torrents_start, torrents_stop = policy.apply(self.torrents, 6, force=True)
        ids_start = [torrent["metainfo"].get_infohash() for torrent in
                     torrents_start]
        self.assertEqual(1, len(ids_start), "Start failed %s vs %s" % (ids_start, torrents_start))
        ids_stop = [torrent["metainfo"].get_infohash() for torrent in torrents_stop]
        self.assertEqual(0, len(ids_stop), "Stop failed %s vs %s" % (ids_stop, torrents_stop))

    def test_seederratio_policy(self):
        """
        testing seeder ratio policy
        """
        policy = SeederRatioPolicy(self.session)
        torrents_start, torrents_stop = policy.apply(self.torrents, 6, force=True)
        ids_start = [torrent["metainfo"].get_infohash() for torrent in
                     torrents_start]
        self.assertEqual(ids_start, [10, 8, 6])
        ids_stop = [torrent["metainfo"].get_infohash() for torrent in torrents_stop]
        self.assertEqual(ids_stop, [3, 1])

    @skip("The random seed is not reliable")
    def test_fallback_policy(self):
        """
        testing policy (seederratio) and then fallback
        """

        for i in xrange(1, 11):
            mock_metainfo = MockMeta(i)
            self.torrents[i] = {"metainfo": mock_metainfo, "num_seeders": -i,
                                "num_leechers": -i, "creation_date": i}

        random.seed(0)
        policy = SeederRatioPolicy(self.session)
        torrents_start, torrents_stop = policy.apply(self.torrents, 6)
        ids_start = [torrent["metainfo"].get_infohash() for torrent in
                     torrents_start]
        self.assertEqual(3, len(ids_start), "Start failed %s vs %s" % (ids_start, torrents_start))
        ids_stop = [torrent["metainfo"].get_infohash() for torrent in torrents_stop]
        self.assertEqual(2, len(ids_stop), "Stop failed %s vs %s" % (ids_stop, torrents_stop))

    def test_creationdate_policy(self):
        """
        test policy based on creation date
        """
        policy = CreationDatePolicy(self.session)
        torrents_start, torrents_stop = policy.apply(self.torrents, 5, force=True)
        ids_start = [torrent["metainfo"].get_infohash() for torrent in
                     torrents_start]
        self.assertEqual(ids_start, [10, 8, 6])
        ids_stop = [torrent["metainfo"].get_infohash() for torrent in torrents_stop]
        self.assertEqual(ids_stop, [5, 3, 1])


class TestBoostingManagerUtilities(TriblerCoreTest):
    """
    Test several utilities used in credit mining
    """

    def __init__(self, *argv, **kwargs):
        super(TestBoostingManagerUtilities, self).__init__(*argv, **kwargs)

        self.peer = [None] * 6
        self.peer[0] = MockLtPeer(MockPeerId("1"), "ip1")
        self.peer[0].setvalue(True, True, True)
        self.peer[1] = MockLtPeer(MockPeerId("2"), "ip2")
        self.peer[1].setvalue(False, False, True)
        self.peer[2] = MockLtPeer(MockPeerId("3"), "ip3")
        self.peer[2].setvalue(True, False, True)
        self.peer[3] = MockLtPeer(MockPeerId("4"), "ip4")
        self.peer[3].setvalue(False, True, False)
        self.peer[4] = MockLtPeer(MockPeerId("5"), "ip5")
        self.peer[4].setvalue(False, True, True)
        self.peer[5] = MockLtPeer(MockPeerId("6"), "ip6")
        self.peer[5].setvalue(False, False, False)

        self.session = MockLtSession()

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        yield super(TestBoostingManagerUtilities, self).setUp()

        self.session.get_libtorrent = lambda: True

        self.bsettings = bm.BoostingSettings(SeederRatioPolicy(self.session))
        self.bsettings.credit_mining_path = self.session_base_dir
        self.bsettings.load_config = False
        self.bsettings.check_dependencies = False
        self.bsettings.initial_logging_interval = 900

    def tearDown(self, annotate=True):
        # TODO(ardhi) : remove it when Tribler free of singleton
        # and 1 below
        DefaultDownloadStartupConfig.delInstance()

        super(TestBoostingManagerUtilities, self).tearDown()

    def test_boosting_dependencies(self):
        """
        Test whether boosting manager dependencies works or not.

        In all test, check dependencies always off. In production, it is on by default.
        """
        self.bsettings.check_dependencies = True
        self.bsettings.initial_swarm_interval = 9000
        self.bsettings.initial_tracker_interval = 9000
        self.bsettings.initial_logging_interval = 9000
        self.session.open_dbhandler = lambda _: None
        self.session.lm.ltmgr = MockLtSession()

        self.session.config.get_torrent_checking_enabled = lambda: True
        self.session.config.get_dispersy_enabled = lambda: True
        self.session.config.get_torrent_store_enabled = lambda: True
        self.session.config.get_torrent_search_enabled = lambda: True
        self.session.config.get_channel_search_enabled = lambda: True
        self.session.get_megacache_enabled = lambda: False

        self.assertRaises(AssertionError, bm.BoostingManager, self.session, self.bsettings)

    def test_load_default(self):
        """
        Test load default configuration in BoostingManager
        """
        self.bsettings.load_config = True
        self.bsettings.auto_start_source = False
        self.bsettings.initial_swarm_interval = 9000
        self.bsettings.initial_tracker_interval = 9000
        self.bsettings.initial_logging_interval = 9000
        self.session.open_dbhandler = lambda _: None
        self.session.lm.ltmgr = MockLtSession()

        # it will automatically load the default configuration
        boost_man = bm.BoostingManager(self.session, self.bsettings)

        # def validate(d_defer):
        self.assertEqual(self.session.config.get_credit_mining_source_interval(), boost_man.settings.source_interval)
        self.assertEqual(self.session.config.get_credit_mining_archive_sources(),
                         [source_to_string(src.source) for src in boost_man.boosting_sources.values() if src.archive])

        boost_man.cancel_all_pending_tasks()

    def test_translate_peer_info(self):
        """
        test - predict number of seeder and leecher only based on peer discovered and
        their activities
        """
        peerlist_dict = []
        for peer in self.peer:
            peerlist_dict.append(LibtorrentDownloadImpl.create_peerlist_data(peer))

        num_seed, num_leech = utilities.translate_peers_into_health(peerlist_dict)
        self.assertEqual(num_seed, 4, "Seeder number don't match")
        self.assertEqual(num_leech, 3, "Leecher number don't match")

    def test_levenshtein(self):
        """
        test levenshtein between two string (in this case, file name)

        source :
        http://people.cs.pitt.edu/~kirk/cs1501/Pruhs/Fall2006/Assignments/editdistance/Levenshtein%20Distance.htm
        """
        string1 = "GUMBO"
        string2 = "GAMBOL"
        dist = levenshtein_dist(string1, string2)
        dist_swap = levenshtein_dist(string2, string1)

        # random string check
        self.assertEqual(dist, 2, "Wrong levenshtein distance")
        self.assertEqual(dist_swap, 2, "Wrong levenshtein distance")

        string1 = "ubuntu-15.10-desktop-i386.iso"
        string2 = "ubuntu-15.10-desktop-amd64.iso"
        dist = levenshtein_dist(string1, string2)

        # similar filename check
        self.assertEqual(dist, 4, "Wrong levenshtein distance")

        dist = levenshtein_dist(string1, string1)
        # equal filename check
        self.assertEqual(dist, 0, "Wrong levenshtein distance")

        string2 = "Learning-Ubuntu-Linux-Server.tgz"
        dist = levenshtein_dist(string1, string2)
        # equal filename check
        self.assertEqual(dist, 28, "Wrong levenshtein distance")

    def test_update_statistics(self):
        """
        test updating statistics of a torrent (pick a new one)
        """
        self.session.open_dbhandler = lambda _: None

        infohash_1 = "a"*20
        infohash_2 = "b"*20
        torrents = {
            infohash_1: {
                "last_seeding_stats": {
                    "time_seeding": 100,
                    "value": 5
                }
            },
            infohash_2: {
                "last_seeding_stats": {}
            }
        }

        new_seeding_stats = {
            "time_seeding": 110,
            "value": 1
        }
        new_seeding_stats_unexist = {
            "time_seeding": 10,
            "value": 8
        }

        self.session.lm.ltmgr = MockLtSession()

        boost_man = bm.BoostingManager(self.session, self.bsettings)
        boost_man.torrents = torrents

        boost_man.update_torrent_stats(infohash_1, new_seeding_stats)
        self.assertEqual(boost_man.torrents[infohash_1]['last_seeding_stats']
                         ['value'], 1)

        boost_man.update_torrent_stats(infohash_2, new_seeding_stats_unexist)
        self.assertEqual(boost_man.torrents[infohash_2]['last_seeding_stats']
                         ['value'], 8)

        boost_man.cancel_all_pending_tasks()

    def test_escape_xml(self):
        """
        testing escape symbols occured in xml/rss document file.
        """
        re_symbols = re.compile(r'\&\#(x?[0-9a-fA-F]+);')

        ampersand_str = re_symbols.sub(ent2chr, '&#x26;')
        self.assertEqual(ampersand_str, "&", "wrong ampersand conversion %s" % ampersand_str)

        str_123 = re_symbols.sub(ent2chr, "&#x31;&#x32;&#x33;")
        self.assertEqual(str_123, "123", "wrong number conversion %s" % str_123)

    def test_logging(self):
        self.session.open_dbhandler = lambda _: None

        infohash_1 = "a"*20
        infohash_2 = "b"*20
        torrents = {
            infohash_1: {
                "last_seeding_stats": {
                    "time_seeding": 100,
                    "value": 5
                }
            },
            infohash_2: {
                "last_seeding_stats": {}
            }
        }
        self.session.lm.ltmgr = MockLtSession()

        boost_man = bm.BoostingManager(self.session, self.bsettings)
        boost_man.torrents = torrents

        boost_man.session.lm.ltmgr.get_session().get_torrents = \
            lambda: [MockLtTorrent(binascii.hexlify(infohash_1)),
                     MockLtTorrent(binascii.hexlify(infohash_2))]

        boost_man.log_statistics()
        boost_man.cancel_all_pending_tasks()


class TestBoostingManagerError(TriblerCoreTest):
    """
    Class to test a bunch of credit mining error handle

    """
    def __init__(self, *argv, **kwargs):
        super(TestBoostingManagerError, self).__init__(*argv, **kwargs)
        self.session = MockLtSession()

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        yield super(TestBoostingManagerError, self).setUp()

        self.session.open_dbhandler = lambda _: True
        self.session.get_libtorrent = lambda: True
        self.session.lm.ltmgr = MockLtSession()

        self.boost_setting = bm.BoostingSettings(SeederRatioPolicy(self.session))
        self.boost_setting.load_config = False
        self.boost_setting.initial_logging_interval = 900
        self.boost_setting.check_dependencies = False
        self.boosting_manager = bm.BoostingManager(self.session, self.boost_setting)
        self.session.lm.boosting_manager = self.boosting_manager

    def tearDown(self, annotate=True):
        DefaultDownloadStartupConfig.delInstance()
        self.session.lm.boosting_manager.cancel_all_pending_tasks()
        super(TestBoostingManagerError, self).tearDown()

    def test_insert_torrent_unknown_source(self):
        """
        testing insert torrent on unknown source
        """
        torrent = {
            'preload': False,
            'metainfo': MockMeta("1234"),
            'infohash': '12345'
        }

        self.boosting_manager.on_torrent_insert(binascii.unhexlify("abcd" * 10), '12345', torrent)
        self.assertNotIn('12345', self.boosting_manager.torrents)

    def test_unknown_source(self):
        """
        testing uknkown source added to boosting source, and try to apply archive
        on top of that
        """
        unknown_key = "1234567890"

        sources = len(self.boosting_manager.boosting_sources.keys())
        self.boosting_manager.add_source(unknown_key)
        self.boosting_manager.set_archive(unknown_key, False)
        self.assertEqual(sources, len(self.boosting_manager.boosting_sources.keys()), "unknown source added")

    def test_failed_start_download(self):
        """
        test assertion error then not download the actual torrent
        """
        torrent = {
            'preload': False,
            'metainfo': MockMeta("1234")
        }
        self.session.lm.download_exists = lambda _: True
        self.boosting_manager.start_download(torrent)

        self.assertNotIn('download', torrent, "%s downloading despite error" % torrent)

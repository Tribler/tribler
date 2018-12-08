from __future__ import absolute_import
from six import unichr
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, Deferred

from Tribler.Core.Session import Session
from Tribler.Core.simpledefs import NTFY_TORRENTS, SIGNAL_CHANNEL, SIGNAL_ON_SEARCH_RESULTS, SIGNAL_TORRENT, \
    NTFY_CHANNELCAST
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.tools import trial_timeout
from Tribler.community.allchannel.community import AllChannelCommunity
from Tribler.community.search.community import SearchCommunity
from Tribler.dispersy.candidate import Candidate

MASTER_KEY = "3081a7301006072a8648ce3d020106052b81040027038192000400f4771c58e65f2cc0385a14027a937a0eb54df0e" \
             "4ae2f72acd8f8286066a48a5e8dcff81c7dfa369fbc33bfe9823587057557cf168b41586dc9ff7615a7e5213f3ec6" \
             "c9b4f9f57f00dbc0dd8ca8b9f6d76fd63a432a56d5938ce9dd7bd291daa92bec52ffcd58d9718836163868f493063" \
             "77c3b8bf36d43ea99122c3276e1a89fb5b9b2ff3f7f6f1702d057dca3e8c0"
MASTER_KEY_SEARCH = "3081a7301006072a8648ce3d020106052b8104002703819200040759eff226a7e2efc62ff61538267f837c" \
                    "34d2a32927a10ff31618a69773e4123e405a6d4a930ceeae9a01cfde07496ec21bdb60eb23c92009bf2c93" \
                    "f9fd32653953f136e6704d04077c457497cea70d1b3809f7ee7c4fa40faad7d9ed00a622183ae8623fe64e" \
                    "1017af273a53b347f11bc6a919c01e9db8f6a98eaf1fcea0a1f18b339b013c7eb134797c29d4c4c429"


class AllChannelCommunityTests(AllChannelCommunity):
    """
    We define our own AllChannelCommunity.
    """

    @classmethod
    def get_master_members(cls, dispersy):
        return [dispersy.get_member(public_key=MASTER_KEY.decode("HEX"))]

    @property
    def dispersy_enable_fast_candidate_walker(self):
        return True

    def check_channelsearch_response(self, messages):
        for message in messages:
            yield message


class SearchCommunityTests(SearchCommunity):
    """
    We define our own SearchCommunity.
    """

    @classmethod
    def get_master_members(cls, dispersy):
        return [dispersy.get_member(public_key=MASTER_KEY_SEARCH.decode("HEX"))]


class TestSearchCommunity(TestAsServer):
    """
    Contains tests to test remote search with booted Tribler sessions.
    """

    @inlineCallbacks
    def setUp(self):
        yield super(TestSearchCommunity, self).setUp()

        self.config2 = None
        self.session2 = None
        self.dispersy2 = None
        self.search_community = None
        self.allchannel_community = None

        self.dispersy = self.session.get_dispersy_instance()
        yield self.setup_peer()

    def setUpPreSession(self):
        TestAsServer.setUpPreSession(self)
        self.config.set_dispersy_enabled(True)
        self.config.set_torrent_store_enabled(True)
        self.config.set_torrent_search_enabled(True)
        self.config.set_channel_search_enabled(True)
        self.config.set_metadata_enabled(True)
        self.config.set_channel_community_enabled(True)
        self.config.set_preview_channel_community_enabled(True)
        self.config.set_torrent_collecting_enabled(True)
        self.config.set_torrent_checking_enabled(True)
        self.config.set_megacache_enabled(True)

    @inlineCallbacks
    def setup_peer(self):
        """
        Setup a second peer that contains some search results.
        """
        self.setUpPreSession()

        self.config2 = self.config.copy()
        self.config2.set_state_dir(self.getStateDir(2))

        self.session2 = Session(self.config2)

        yield self.session2.start()
        self.dispersy2 = self.session2.get_dispersy_instance()

        @inlineCallbacks
        def unload_communities():
            for community in self.dispersy.get_communities():
                if isinstance(community, SearchCommunity) or isinstance(community, AllChannelCommunity):
                    yield community.unload_community()

            for community in self.dispersy2.get_communities():
                if isinstance(community, SearchCommunity) or isinstance(community, AllChannelCommunity):
                    yield community.unload_community()

        def load_communities():
            self.search_community = \
            self.dispersy.define_auto_load(SearchCommunityTests, self.session.dispersy_member, load=True,
                                           kargs={'tribler_session': self.session})[0]
            self.dispersy2.define_auto_load(SearchCommunityTests, self.session2.dispersy_member, load=True,
                                            kargs={'tribler_session': self.session2})

            self.allchannel_community = \
            self.dispersy.define_auto_load(AllChannelCommunityTests, self.session.dispersy_member, load=True,
                                           kargs={'tribler_session': self.session})[0]
            self.dispersy2.define_auto_load(AllChannelCommunityTests, self.session2.dispersy_member, load=True,
                                            kargs={'tribler_session': self.session2})

        yield unload_communities()
        load_communities()

        self.search_community.add_discovered_candidate(Candidate(self.dispersy2.lan_address, tunnel=False))
        self.allchannel_community.add_discovered_candidate(Candidate(self.dispersy2.lan_address, tunnel=False))

        # Add some content to second session
        torrent_db_handler = self.session2.open_dbhandler(NTFY_TORRENTS)
        torrent_db_handler.addExternalTorrentNoDef(str(unichr(97)) * 20, 'test test', [('Test.txt', 1337)], [], 1337)
        torrent_db_handler.updateTorrent(str(unichr(97)) * 20, is_collected=1)

        channel_db_handler = self.session2.open_dbhandler(NTFY_CHANNELCAST)
        channel_db_handler.on_channel_from_dispersy('f' * 20, 42, "test", "channel for unit tests")
        torrent_list = [
            [1, 1, 1, ('a' * 40).decode('hex'), 1460000000, "ubuntu-torrent.iso", [['file1.txt', 42]], []]
        ]
        channel_db_handler.on_torrents_from_dispersy(torrent_list)

        # We also need to add the channel to the database of the session initiating the search
        channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)
        channel_db_handler.on_channel_from_dispersy('f' * 20, 42, "test", "channel for unit tests")

    @trial_timeout(20)
    def test_torrent_search(self):
        """
        Test whether we receive results when searching remotely for torrents
        """
        test_deferred = Deferred()

        def on_search_results_torrents(_dummy1, _dummy2, _dummy3, results):
            self.assertEqual(len(results['result_list']), 1)
            test_deferred.callback(None)

        reactor.callLater(2, self.session.search_remote_torrents, [u"test"])
        self.session.add_observer(on_search_results_torrents, SIGNAL_TORRENT, [SIGNAL_ON_SEARCH_RESULTS])

        return test_deferred

    @trial_timeout(20)
    def test_channel_search(self):
        """
        Test whether we receive results when searching remotely for channels
        """
        test_deferred = Deferred()

        def on_search_results_channels(_dummy1, _dummy2, _dummy3, results):
            self.assertEqual(len(results['result_list']), 1)
            test_deferred.callback(None)

        reactor.callLater(5, self.session.search_remote_channels, [u"test"])
        self.session.add_observer(on_search_results_channels, SIGNAL_CHANNEL, [SIGNAL_ON_SEARCH_RESULTS])

        return test_deferred

    @inlineCallbacks
    def tearDown(self):
        yield self.session2.shutdown()
        yield super(TestSearchCommunity, self).tearDown()

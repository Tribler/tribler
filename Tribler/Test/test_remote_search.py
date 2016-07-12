from twisted.internet.defer import Deferred
from twisted.internet.task import LoopingCall

from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Core.simpledefs import SIGNAL_CHANNEL, SIGNAL_SEARCH_COMMUNITY
from Tribler.Core.simpledefs import SIGNAL_ON_SEARCH_RESULTS
from Tribler.Test.test_as_server import TestAsServer


class BaseTestSearch(TestAsServer):
    """
    This is the base class of the search tests.
    """

    def setUpPreSession(self):
        TestAsServer.setUpPreSession(self)
        self.config.set_dispersy(True)
        self.config.set_torrent_store(True)
        self.config.set_enable_torrent_search(True)
        self.config.set_enable_channel_search(True)
        self.config.set_channel_community_enabled(True)
        self.config.set_preview_channel_community_enabled(True)
        self.config.set_torrent_collecting(True)
        self.config.set_torrent_checking(True)
        self.config.set_megacache(True)

    def setUp(self, autoload_discovery=True):
        """
        Setup all things for the search. This methods also creates a LoopingCall that checks every three seconds
        if we have enough connections for our search.
        """
        TestAsServer.setUp(self, autoload_discovery=autoload_discovery)
        self.session.add_observer(self.on_search_results, SIGNAL_CHANNEL, [SIGNAL_ON_SEARCH_RESULTS])
        self.session.add_observer(self.on_search_results, SIGNAL_SEARCH_COMMUNITY, [SIGNAL_ON_SEARCH_RESULTS])

        self.channel_search = False
        self.torrent_search = False

        self.connections_lc = LoopingCall(self.check_num_connections)
        self.connections_lc.start(3)

        self.conn_deferred = Deferred()    # Fired when we have enough connections
        self.search_deferred = Deferred()  # Fired when we have a remote result

        self.min_connections = 10  # The minimum number of required connections in AllChannel/Search community

    def on_search_results(self, subject, changetype, objectID, results):
        if ((subject == SIGNAL_CHANNEL and self.channel_search) or
                (subject == SIGNAL_SEARCH_COMMUNITY and self.torrent_search)) and not self.search_deferred.called:
            self.search_deferred.callback(None)

    def check_num_connections(self):
        """
        Check the number of current connections in AllChannel/Search community
        """
        connections = 0
        for community in self.session.get_dispersy_instance().get_communities():
            from Tribler.community.allchannel.community import AllChannelCommunity
            from Tribler.community.search.community import SearchCommunity

            if isinstance(community, AllChannelCommunity) and self.channel_search or \
                isinstance(community, SearchCommunity) and self.torrent_search:
                connections = community.get_nr_connections()
                break

        if connections >= 10:
            self.connections_lc.stop()
            self.conn_deferred.callback(None)


class TestRemoteChannelSearch(BaseTestSearch):
    """
    This class contains tests to test remote channel search.
    """

    def setUp(self, autoload_discovery=True):
        BaseTestSearch.setUp(self, autoload_discovery=autoload_discovery)
        self.channel_search = True

    @deferred(timeout=120)
    def test_remote_channel_search(self):
        """
        Testing whether remote channels can be found when executing a search query in AllChannel community
        """
        def perform_search(_):
            self.session.search_remote_channels([u'de'])

        self.conn_deferred.addCallback(perform_search)
        return self.search_deferred


class TestRemoteTorrentSearch(BaseTestSearch):
    """
    This class contains tests to test remote torrent search.
    """

    def setUp(self, autoload_discovery=True):
        BaseTestSearch.setUp(self, autoload_discovery=autoload_discovery)
        self.torrent_search = True

    @deferred(timeout=120)
    def test_remote_torrent_search(self):
        """
        Testing whether remote torrents can be found when executing a search query in Search community
        """
        def perform_search(_):
            self.session.search_remote_torrents([u'de'])

        self.conn_deferred.addCallback(perform_search)
        return self.search_deferred

from twisted.internet.defer import inlineCallbacks
from twisted.internet import reactor, task

from Tribler.community.channel.community import ChannelCommunity
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.dispersy.candidate import WalkCandidate
from Tribler.dispersy.member import Member
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.Test.test_as_server import AbstractServer


class ChannelTestBase(AbstractServer):

    """This class provides convenience functions
        for the Channel community tests.
    """

    @blocking_call_on_reactor_thread
    def setUp(self):
        super(ChannelTestBase, self).setUp()
        # Initialize Sessions
        self._initialize_sessions()
        self.dispersy1 = self.ses1.lm.dispersy
        self.dispersy2 = self.ses2.lm.dispersy
        # Create Nodes
        self.node1 = self.dispersy1.get_new_member(u"low")
        self.pub_node1 = Member(
            self.dispersy1, self.node1._ec.pub(), self.node1.database_id)
        self.community1 = ChannelCommunity.init_community(self.dispersy1,
                                                          self.pub_node1,
                                                          self.node1,
                                                          self.ses1)
        self.node2_1 = self.dispersy2.get_member(
            public_key=self.pub_node1.public_key)
        self.node2 = self.dispersy2.get_new_member(u"low")
        self.pub_node2 = Member(
            self.dispersy2, self.node2._ec.pub(), self.node2.database_id)
        self.community2 = ChannelCommunity.init_community(self.dispersy2,
                                                          self.node2_1,
                                                          self.node2,
                                                          self.ses2)
        # Communicate nodes
        self._force_walk_candidate()
        # Field for testing return values
        self.called = []

    def tearDown(self):
        self.ses1.shutdown()
        self.ses2.shutdown()
        super(ChannelTestBase, self).tearDown()

    @blocking_call_on_reactor_thread
    def _initialize_sessions(self):
        """Create the Sessions for both nodes.
        """
        config = SessionStartupConfig()
        config.set_state_dir(self.getStateDir())
        config.set_torrent_checking(False)
        config.set_multicast_local_peer_discovery(False)
        config.set_megacache(True)
        config.set_dispersy(True)
        config.set_mainline_dht(False)
        config.set_torrent_store(False)
        config.set_enable_torrent_search(False)
        config.set_enable_channel_search(False)
        config.set_torrent_collecting(False)
        config.set_libtorrent(False)
        config.set_dht_torrent_collecting(False)
        config.set_enable_metadata(False)
        config.set_upgrader_enabled(False)
        config.set_enable_multichain(False)
        config.set_preview_channel_community_enabled(False)
        config.set_channel_community_enabled(False)
        config.set_tunnel_community_enabled(False)

        self.ses1 = Session(config, ignore_singleton=True)
        config2 = config.copy()
        config2.set_state_dir(self.getStateDir() + "2")
        self.ses2 = Session(config2, ignore_singleton=True)

        for session in [self.ses1, self.ses2]:
            session.start()

    def _flush_community(self, community):
        """Make sure no messages are left in the batch
            cache.
        """
        for meta in list(community._batch_cache.iterkeys()):
            community._process_message_batch(meta)

    def _get_last_synced_packet_id(self, dispersy, community):
        packet_id, = dispersy._database.execute(u"SELECT id FROM sync " +
                                                u"WHERE community = ? " +
                                                u"ORDER BY global_time DESC " +
                                                u"LIMIT 1",
                                                (community.database_id,)).next()
        return packet_id

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def _allow_packet_delivery(self):
        yield task.deferLater(reactor, .05, lambda: None)
        self._flush_community(self.community1)
        self._flush_community(self.community2)
        yield task.deferLater(reactor, .05, lambda: None)
        self._flush_community(self.community1)
        self._flush_community(self.community2)

    def _mock_method(self, instance, cls, method_name, callback):
        """Replace an instance method with a callback.
        """
        sig = type(getattr(cls, method_name))
        setattr(instance, method_name, sig(callback, instance, cls))

    def _force_walk_candidate(self):
        """Forces nodes into each other's walk candidate list.
        """
        for community, dispersy, pub_node in [
                (self.community1, self.dispersy2, self.pub_node2),
                (self.community2, self.dispersy1, self.pub_node1)]:
            wcnd = WalkCandidate(dispersy.lan_address,
                                 False,
                                 dispersy.lan_address,
                                 ('0.0.0.0', 0),
                                 u"symmetric-NAT")
            from time import time
            wcnd.global_time = time()
            wcnd._last_walk_reply = wcnd.global_time - 1
            wcnd.associate(pub_node)
            community._candidates[dispersy.lan_address] = wcnd

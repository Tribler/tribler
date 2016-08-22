from Tribler.community.allchannel.community import AllChannelCommunity
from Tribler.Core.Modules.channel.channel_manager import ChannelManager
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.dispersy.candidate import Candidate, WalkCandidate
from Tribler.dispersy.member import Member
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.Test.test_as_server import AbstractServer


class AllChannelTestBase(AbstractServer):

    """This class provides convenience functions
        for the AllChannel community tests.
    """

    TEST_TORRENT_HASH = "zyxwv" * 4
    TEST_MY_CHANNEL_NAME = "MyChannelTest"

    @blocking_call_on_reactor_thread
    def setUp(self):
        super(AllChannelTestBase, self).setUp()
        # Initialize Sessions
        self._initialize_sessions()
        self.dispersy1 = self.ses1.lm.dispersy
        self.dispersy2 = self.ses2.lm.dispersy
        # Create Nodes
        self.node1 = self.dispersy1.get_new_member(u"low")
        self.pub_node1 = Member(
            self.dispersy1, self.node1._ec.pub(), self.node1.database_id)
        self.community1 = self.dispersy1.define_auto_load(
            AllChannelCommunity, self.node1, load=True, kargs={'tribler_session': self.ses1})[0]
        self.node2 = self.dispersy2.get_new_member(u"low")
        self.pub_node2 = Member(
            self.dispersy2, self.node2._ec.pub(), self.node2.database_id)
        self.community2 = self.dispersy2.define_auto_load(
            AllChannelCommunity, self.node2, load=True, kargs={'tribler_session': self.ses2})[0]
        # Communicate nodes
        for community, member, dispersy, otherdispersy in [
                (self.community1, self.node2,
                 self.dispersy1, self.dispersy2),
                (self.community2, self.node1,
                 self.dispersy2, self.dispersy1)]:
            self._create_identity_messages(
                community, member, dispersy, otherdispersy)
        # Field for testing return values
        self.called = []

    def tearDown(self):
        self.ses1.shutdown()
        self.ses2.shutdown()
        super(AllChannelTestBase, self).tearDown()

    @classmethod
    def tearDownClass(cls):
        """The Twisted reactor is not always stopped when
            it needs to be. Give it some time.
        """
        import threading
        for thread in threading.enumerate():
            if thread.name == 'Twisted':
                thread.join(1.0)

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
        config.set_channel_community_enabled(True)
        config.set_tunnel_community_enabled(False)

        self.ses1 = Session(config, ignore_singleton=True)
        config2 = config.copy()
        config2.set_state_dir(self.getStateDir() + "2")
        self.ses2 = Session(config2, ignore_singleton=True)

        for session in [self.ses1, self.ses2]:
            session.prestart()
            session.start()
            self._mock_method(
                session, Session, 'add_observer', lambda a, b, c, d=None, e=None, f=None: None)
            session.lm.channel_manager = ChannelManager(session)
            session.lm.channel_manager.initialize()

    def _flush_community(self, community):
        """Make sure no messages are left in the batch
            cache.
        """
        for meta in list(community._batch_cache.iterkeys()):
            community._process_message_batch(meta)

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

    def _create_identity_messages(self, community, member, dispersy, otherdispersy):
        """Send a missing-identity message to another node.
            This will cause it to reply with a dispersy-identity.
        """
        meta_miss = community.get_meta_message(u"dispersy-missing-identity")
        message = meta_miss.impl(
            distribution=(community.claim_global_time(),), payload=(member.mid,))
        dispersy._send(
            (Candidate(otherdispersy.lan_address, False),), [message])

    def _add_my_channel(self, session):
        """Add a mychannel for a node"""
        return session.create_channel(TEST_MY_CHANNEL_NAME, "Fake channel for unit testing")

    def _add_other_channel(self, cid, pubkey, sessionsrc, sessiondst):
        """Add a channel for a node by id"""
        channel = sessionsrc.lm.channelcast_db.getChannel(cid)
        peer_id = sessiondst.lm.peer_db.addOrGetPeerID(pubkey)
        sessiondst.lm.channelcast_db.on_channel_from_dispersy(channel[1],
                                                              peer_id,
                                                              channel[2],
                                                              channel[3])

    def _add_my_channel_torrent(self, cid, torrent_hash=TEST_TORRENT_HASH):
        """Add a torrent to node 1's my channel"""
        self.ses1.lm.channelcast_db.on_torrents_from_dispersy([(cid,
                                                                42,
                                                                1,
                                                                torrent_hash,
                                                                0,
                                                                "fakeTorrent",
                                                                [("fakeFile", 0),
                                                                ],
                                                                ["http://localhost/announce"]), ])

TEST_TORRENT_HASH = AllChannelTestBase.TEST_TORRENT_HASH
TEST_MY_CHANNEL_NAME = AllChannelTestBase.TEST_MY_CHANNEL_NAME

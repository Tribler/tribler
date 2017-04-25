import struct

from twisted.internet.defer import inlineCallbacks
from twisted.internet import reactor, task

from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.Test.Community.AllChannel.allchannel_test_base import AllChannelTestBase

TEST_TORRENT_HASH = AllChannelTestBase.TEST_TORRENT_HASH
TEST_MY_CHANNEL_NAME = AllChannelTestBase.TEST_MY_CHANNEL_NAME


class TestAllChannelCommunity(AllChannelTestBase):

    """Outline and design:
        - In these unittests Node 1 has all of the data and
          Node 2 receives all of the data.

        - Node 1 and 2 have seperate Dispersy's [and Sessions].
    """

    def test_db_init(self):
        """Initialization should come with channelcast,
            votecast and peer databases.
        """
        self.assertIsNotNone(self.community1._channelcast_db)
        self.assertIsNotNone(self.community1._votecast_db)
        self.assertIsNotNone(self.community1._peer_db)

    def test_tasks_running(self):
        """The AllChannel community should periodically
            perform channelcasts and clean PreviewCommunity's.
        """
        self.assertTrue(self.community1.is_pending_task_active(u"channelcast"))
        self.assertTrue(
            self.community1.is_pending_task_active(u"unload preview"))

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_channelcast_timeout(self):
        """After a channelcast, a peer should be placed on
            the blocklist and not receive another channelcast.

            This test checks:
            When: Node 1 sends a channelcast
            Then: Node 2 handles on_channelcast
            When: Node 1 sends a channelcast in quick succession
            Then: Node 2 does not handle on_channelcast
        """
        cid = self._add_my_channel(self.ses1)
        self._add_my_channel(self.ses2)
        self._add_other_channel(
            cid, self.pub_node1.public_key, self.ses1, self.ses2)
        self._add_my_channel_torrent(cid)

        # Catch the on_channelcastrequest to verify behavior
        def mock_on_channelcastrequest(messages):
            self.called.append(True)
        self.community1.add_callback('on_channelcast_request', mock_on_channelcastrequest, False)

        # Perform a channelcast by node 1 with
        # forced candidate node 2 twice
        self._force_walk_candidate()
        self.community1.create_channelcast()
        self._force_walk_candidate()
        self.community1.create_channelcast()

        # Allow the packets to be processed
        yield task.deferLater(reactor, .5, lambda: None)

        # Verify that on_channelcastrequest has been called
        self.assertEqual(len(self.called), 1)
        self.assertTrue(self.called[0])

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_channelcast_trim(self):
        """A channelcast should not have too many torrents.
        """
        cid = self._add_my_channel(self.ses1)
        self._add_my_channel(self.ses2)
        self._add_other_channel(
            cid, self.pub_node1.public_key, self.ses1, self.ses2)
        # This is the absolute maximum amount of bytes,
        # without a signature, the bloomfilter should occupy.
        # Because we DO have a signature, it should ALWAYS
        # be less than 266 bytes.
        for i in range(266):
            array_hash = [ord(c) for c in TEST_TORRENT_HASH]
            j = 0
            for b in struct.pack("I", i):
                array_hash[j] ^= ord(b)
                j += 1
            self._add_my_channel_torrent(cid, "".join([chr(c) for c in array_hash]))

        # Catch the on_channelcast to verify behavior
        def mock_on_channelcast(messages):
            for message in messages:
                infohashes = message.payload.torrents.values()[0]
                self.assertLess(len(infohashes), 266)
                for infohash in infohashes:
                    # We XOR up to the first 4 bytes (with an int)
                    # to make it unique.
                    self.assertTrue(infohash.endswith(TEST_TORRENT_HASH[5:]))
                self.called.append(True)
        self.community2.add_callback('on_channelcast', mock_on_channelcast, True)

        # Perform a channelcast by node 1 with
        # forced candidate node 2
        self._force_walk_candidate()
        self.community1.create_channelcast()

        # Allow the packets to be processed
        yield task.deferLater(reactor, .5, lambda: None)

        # Verify that on_channelcastrequest has been called
        self.assertEqual(len(self.called), 1)
        self.assertTrue(self.called[0])

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_channelcast_nochannel(self):
        """When a channelcast is attempted without a
            channel. No channelcast should be sent.
        """
        self._add_my_channel(self.ses2)

        # Catch the on_channelcast to verify behavior
        def mock_on_channelcast(messages):
            self.called.append(True)
        self.community2.add_callback('on_channelcast', mock_on_channelcast, True)

        # Perform a channelcast by node 1 with
        # forced candidate node 2
        self._force_walk_candidate()
        self.community1.create_channelcast()

        # Allow the packets to be processed
        yield task.deferLater(reactor, .5, lambda: None)

        # Verify that on_channelcast has not been called
        self.assertEqual(len(self.called), 0)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_channelcast_nochanneltorrent(self):
        """When a channelcast is attempted without a
            torrent in the the user's channel. No
            channelcast should be sent.
        """
        cid = self._add_my_channel(self.ses1)
        self._add_my_channel(self.ses2)
        self._add_other_channel(
            cid, self.pub_node1.public_key, self.ses1, self.ses2)

        # Catch the on_channelcast to verify behavior
        def mock_on_channelcast(messages):
            self.called.append(True)
        self.community2.add_callback('on_channelcast', mock_on_channelcast, True)

        # Perform a channelcast by node 1 with
        # forced candidate node 2
        self._force_walk_candidate()
        self.community1.create_channelcast()

        # Allow the packets to be processed
        yield task.deferLater(reactor, .5, lambda: None)

        # Verify that on_channelcast has not been called
        self.assertEqual(len(self.called), 0)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_channelcast_request(self):
        """After a channelcast, a peer should reply with a
        channelcast request.

            This test checks:
            When: Node 1 sends a channelcast
            Then: Node 2 sends a channelcast_request
            Then: Node 1 handles a on_channelcastrequest
        """
        cid = self._add_my_channel(self.ses1)
        self._add_my_channel(self.ses2)
        self._add_other_channel(
            cid, self.pub_node1.public_key, self.ses1, self.ses2)
        self._add_my_channel_torrent(cid)

        # Catch the on_channelcastrequest to verify behavior
        def mock_on_channelcastrequest(messages):
            self.called.append(True)
        self.community1.add_callback('on_channelcast_request', mock_on_channelcastrequest, False)

        # Perform a channelcast by node 1 with
        # forced candidate node 2
        self._force_walk_candidate()
        self.community1.create_channelcast()

        # Allow the packets to be processed
        yield task.deferLater(reactor, .5, lambda: None)

        # Verify that on_channelcastrequest has been called
        self.assertEqual(len(self.called), 1)
        self.assertTrue(self.called[0])

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_channelsearch(self):
        """On a channelsearch, a node should reply
            with a channelsearch response.

            This test checks:
            When: Node 2 sends a channelsearch
            Then: Node 1 handles on_channelsearch
            Then: Node 2 handles on_channelsearch_response
        """
        cid = self._add_my_channel(self.ses1)
        self._add_other_channel(
            cid, self.pub_node1.public_key, self.ses1, self.ses2)
        self._add_my_channel_torrent(cid)
        self._force_walk_candidate()

        # Hook into the on_channelsearch[response] to verify behavior
        def mock_on_channelsearch(messages):
            for message in messages:
                self.called.append("ON_CHANNELSEARCH")
                self.assertItemsEqual(message.payload.keywords,
                                      [unicode(TEST_MY_CHANNEL_NAME)])
        self.community1.add_callback('on_channelsearch', mock_on_channelsearch, False)

        def mock_on_channelsearchresponse(messages):
            for message in messages:
                self.assertItemsEqual(message.payload.keywords,
                                      [unicode(TEST_MY_CHANNEL_NAME)])
                self.called.append("ON_CHANNELSEARCHRESPONSE")
        self.community2.add_callback('on_channelsearch_response', mock_on_channelsearchresponse, False)

        # Perform search
        self.community2.create_channelsearch([unicode(TEST_MY_CHANNEL_NAME)])

        # Allow the packets to be processed
        yield task.deferLater(reactor, 0.5, lambda: None)

        # Verify that on_channelsearchresponse has been called
        # (and the additional asserts)
        self.assertListEqual(self.called, ["ON_CHANNELSEARCH",
                                           "ON_CHANNELSEARCHRESPONSE"])

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_channelsearch_noresults(self):
        """On a channelsearch, a node should not reply
            with a channelsearch response, if it has no
            results.

            This test checks:
            When: Node 2 sends a channelsearch
            Then: Node 1 handles on_channelsearch
            Then: Node 2 does not handle a on_channelsearch_response
        """
        cid = self._add_my_channel(self.ses1)
        self._add_other_channel(
            cid, self.pub_node1.public_key, self.ses1, self.ses2)
        self._add_my_channel_torrent(cid)
        self._force_walk_candidate()

        # Hook into the on_channelsearch[response] to verify behavior
        def mock_on_channelsearch(messages):
            for message in messages:
                self.called.append("ON_CHANNELSEARCH")
                self.assertItemsEqual(message.keywords,
                                      [u"#"])
        self.community1.add_callback('on_channelsearch', mock_on_channelsearch, False)

        def mock_on_channelsearchresponse(messages):
            for message in messages:
                self.called.append("ON_CHANNELSEARCHRESPONSE")
        self.community2.add_callback('on_channelsearch_response', mock_on_channelsearchresponse, True)

        # Perform search
        self.community2.create_channelsearch([u"#"])

        # Allow the packets to be processed
        yield task.deferLater(reactor, 0.5, lambda: None)

        # Verify that on_channelsearchresponse has been called
        # (and the additional asserts)
        self.assertListEqual(self.called, ["ON_CHANNELSEARCH"])

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_channelsearch_notorrents(self):
        """On a channelsearch, a node should not reply
            with a channelsearch response, if it has no
            torrents in its channel.

            This test checks:
            When: Node 2 sends a channelsearch
            Then: Node 1 handles on_channelsearch
            Then: Node 2 does not handle a on_channelsearch_response
        """
        cid = self._add_my_channel(self.ses1)
        self._add_other_channel(
            cid, self.pub_node1.public_key, self.ses1, self.ses2)
        self._force_walk_candidate()

        # Hook into the on_channelsearch[response] to verify behavior
        def mock_on_channelsearch(messages):
            for message in messages:
                self.called.append("ON_CHANNELSEARCH")
                self.assertItemsEqual(message.keywords,
                                      [unicode(TEST_MY_CHANNEL_NAME)])
        self.community1.add_callback('on_channelsearch', mock_on_channelsearch, False)

        def mock_on_channelsearchresponse(messages):
            for message in messages:
                self.called.append("ON_CHANNELSEARCHRESPONSE")
        self.community2.add_callback('on_channelsearch_response', mock_on_channelsearchresponse, True)

        # Perform search
        self.community2.create_channelsearch([unicode(TEST_MY_CHANNEL_NAME)])

        # Allow the packets to be processed
        yield task.deferLater(reactor, 0.5, lambda: None)

        # Verify that on_channelsearchresponse has been called
        # (and the additional asserts)
        self.assertListEqual(self.called, ["ON_CHANNELSEARCH"])

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_votecast(self):
        """When a node favorites a channel, the
            other node needs to receive this vote.
        """
        cid = self._add_my_channel(self.ses1)
        self._add_other_channel(
            cid, self.pub_node1.public_key, self.ses1, self.ses2)
        did = str(
            self.community1._channelcast_db.getDispersyCIDFromChannelId(cid))
        peer_id = self.community1._peer_db.addOrGetPeerID(
            self.pub_node2.public_key)

        # Catch the on_channelcast to verify behavior
        def mock_on_votecast(messages):
            for message in messages:
                self.called.append(True)
        self.community1.add_callback('on_votecast', mock_on_votecast, False)

        # Perform a votecast (favorite) by node 2 with
        # node 1's channel.
        self._force_walk_candidate()
        self.community2.disp_create_votecast(did, 2, 1)

        # Allow the packets to be processed
        yield task.deferLater(reactor, .5, lambda: None)
        self._flush_community(self.community1)

        # Verify that on_votecast has been called
        self.assertListEqual(self.called, [True])
        self.assertEqual(
            self.community1._votecast_db.getVoteOnChannel(cid, peer_id), 2)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_votecast_replace(self):
        """When a node updates its vote it should
            undo its old vote first.
        """
        cid = self._add_my_channel(self.ses1)
        self._add_other_channel(
            cid, self.pub_node1.public_key, self.ses1, self.ses2)
        did = str(
            self.community1._channelcast_db.getDispersyCIDFromChannelId(cid))
        peer_id = self.community1._peer_db.addOrGetPeerID(
            self.pub_node2.public_key)

        # Catch the on_channelcast to verify behavior
        def mock_on_votecast(messages):
            for message in messages:
                self.called.append("ON_VOTECAST")
        self.community1.add_callback('on_votecast', mock_on_votecast, False)

        def mock_undo_votecast(messages, redo=False):
            for message in messages:
                self.called.append("UNDO_VOTECAST")
        self.community2.add_callback('undo_votecast', mock_undo_votecast, False)

        # Perform a votecast (spam) by node 2 with
        # node 1's channel.
        self._force_walk_candidate()
        self.community2.disp_create_votecast(did, -1, 1)

        # Allow the packets to be processed
        yield task.deferLater(reactor, .5, lambda: None)
        self._flush_community(self.community1)

        # Verify that on_votecast has been called
        self.assertListEqual(self.called, ["ON_VOTECAST"])
        self.assertEqual(
            self.community1._votecast_db.getVoteOnChannel(cid, peer_id), -1)

        # Perform a votecast (favorite) by node 2 with
        # node 1's channel.
        self.community2.disp_create_votecast(did, 2, 1)

        # Allow the packets to be processed
        yield task.deferLater(reactor, .5, lambda: None)
        self._flush_community(self.community1)

        # Verify that on_votecast has been called
        self.assertListEqual(
            self.called, ["ON_VOTECAST", "UNDO_VOTECAST", "ON_VOTECAST"])
        self.assertEqual(
            self.community1._votecast_db.getVoteOnChannel(cid, peer_id), 2)

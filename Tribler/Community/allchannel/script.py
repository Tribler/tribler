from community import AllChannelCommunity

from Tribler.Core.dispersy.bloomfilter import BloomFilter
from Tribler.Core.dispersy.crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin
from Tribler.Core.dispersy.member import MyMember
from Tribler.Core.dispersy.script import ScriptBase
from Tribler.Core.dispersy.debug import Node
from Tribler.Core.dispersy.dprint import dprint

class AllChannelNode(Node):
    def create_propagate_torrents(self, infohashes, global_time):
        meta = self._community.get_meta_message(u"propagate-torrents")
        return meta.implement(meta.authentication.implement(),
                              meta.distribution.implement(global_time),
                              meta.destination.implement(),
                              meta.payload.implement(infohashes))

    def create_torrent_request(self, infohash, global_time):
        meta = self._community.get_meta_message(u"torrent-request")
        return meta.implement(meta.authentication.implement(),
                              meta.distribution.implement(global_time),
                              meta.destination.implement(),
                              meta.payload.implement(infohash))

    def create_channel_search_request(self, skips, search, method, global_time):
        meta = self._community.get_meta_message(u"channel-search-request")
        skip = BloomFilter(max(10, len(skips)), 0.01)
        map(skip.add, skips)
        return meta.implement(meta.authentication.implement(),
                              meta.distribution.implement(global_time),
                              meta.destination.implement(),
                              meta.payload.implement(skip, search, method))

class AllChannelScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = MyMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)

        self.caller(self.test_incoming_propagate_torrents)
        self.caller(self.test_outgoing_propagate_torrents)
        self.caller(self.test_incoming_channel_search_request)
        self.caller(self.test_outgoing_channel_search_request)

    def test_incoming_propagate_torrents(self):
        """
        We will send a 'propagate-torrents' message from NODE to SELF with an infohash that is not
        in the local database, the associated .torrent should then be requested by SELF.
        """
        community = AllChannelCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()

        # create node and ensure that SELF knows the node address
        node = AllChannelNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.1

        # send a 'propagate-torrents' message with an infohash that SELF does not have
        infohash = "-this-is-not-an-existing-infohash-"[:20]
        global_time = 10
        node.send_message(node.create_propagate_torrents([infohash], global_time), address)
        yield 0.1

        # # wait for the 'torrent-request' message from SELF to NODE
        # _, message = node.receive_message(addresses=[address], message_names=[u"torrent-request"])
        # assert message.payload.infohash == infohash

    def test_outgoing_propagate_torrents(self):
        """
        We will send a 'propagate-torrents' message from SELF to NODE.

        Restrictions:
         - No duplicate infohashes.
         - No more than 50 infohashes.
         - At least 1 infohash must be given.
         - Infohashes must exist in SELF's database.
        """
        community = AllChannelCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()

        # wait for a few seconds for Tribler to collect some torrents...
        yield 5.0

        # create node and ensure that SELF knows the node address
        node = AllChannelNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.01

        # send a 'propagate-torrents' message
        community.create_propagate_torrents()
        yield 0.01

        # wait for the 'propagate-torrents' message from SELF to NODE
        _, message = node.receive_message(addresses=[address], message_names=[u"propagate-torrents"])
        assert 1 <= len(message.payload.infohashes) <= 50, "to few or to many infohashes"
        assert len(set(message.payload.infohashes)) == len(message.payload.infohashes), "duplicate infohashes"

        dprint(map(lambda infohash: infohash.encode("HEX"), message.payload.infohashes), lines=1)

    def test_incoming_channel_search_request(self):
        """
        We will send a 'channel-search-request' message from NODE to SELF.

        TODO: currently there is nothing in the database to find.  We need to add something and
        verify that we get some response back.  Hence the channel-search-response is not tested yet
        """
        community = AllChannelCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()

        # create node and ensure that SELF knows the node address
        node = AllChannelNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.1

        # send a 'channel-search-message' message from NODE to SELF
        global_time = 10
        node.send_message(node.create_channel_search_request([], [u"foo", u"bar"], u"simple-any-keyword", global_time), address)

    def test_outgoing_channel_search_request(self):
        """
        We will send a 'channel-search-request' message from SELF to NODE.

        TODO: currently there is that we can send back... hence the channel-search-response is not
        tested yet
        """
        def on_response(address, response):
            assert response is None

        community = AllChannelCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()

        # create node and ensure that SELF knows the node address
        node = AllChannelNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.1

        # send a 'channel-search-message' message from NODE to SELF
        community.create_channel_search_request([], [u"foo", u"bar"], on_response, timeout=1.0)
        yield 0.1

        _, request = node.receive_message(addresses=[address], message_names=[u"channel-search-request"])
        assert request.payload.search == (u"foo", u"bar"), request.payload.search
        assert request.payload.method == u"simple-any-keyword", request.payload.method

    # def test_incoming_torrent_request(self):
    #     """
    #     We will send a 'torrent-request' from NODE to SELF.
    #     """
    #     community = AllChannelCommunity.create_community(self._my_member)
    #     address = self._dispersy.socket.get_address()

    #     # wait for a few seconds for Tribler to collect some torrents...
    #     yield 5.0

    #     # create node and ensure that SELF knows the node address
    #     node = AllChannelNode()
    #     node.init_socket()
    #     node.set_community(community)
    #     node.init_my_member()
    #     yield 0.01

    #     # pick an existing infohash from the database
    #     infohash, = community._torrent_database._db.fetchone(u"SELECT infohash FROM Torrent ORDER BY RANDOM() LIMIT 1")
    #     dprint("requesting ", infohash.encode("HEX"))

    #     # send a 'torrent-request' message
    #     node.create_
    #     community.create_propagate_torrents()
    #     yield 0.01

    #     # wait for the 'propagate-torrents' message from SELF to NODE
    #     _, message = node.receive_message(addresses=[address], message_names=[u"propagate-torrents"])
    #     assert 1 <= len(message.payload.infohashes) <= 50, "to few or to many infohashes"
    #     assert len(set(message.payload.infohashes)) == len(message.payload.infohashes), "duplicate infohashes"

    #     dprint(map(lambda infohash: infohash.encode("HEX"), message.payload.infohashes), lines=1)

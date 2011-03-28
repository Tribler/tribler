from hashlib import sha1
from random import choice
from string import letters
from time import time

from community import AllChannelCommunity
from Tribler.Community.channel.community import ChannelCommunity
from preview import PreviewChannelCommunity

from Tribler.Core.dispersy.bloomfilter import BloomFilter
from Tribler.Core.dispersy.crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin
from Tribler.Core.dispersy.member import MyMember
from Tribler.Core.dispersy.script import ScriptBase
from Tribler.Core.dispersy.debug import Node
from Tribler.Core.dispersy.dprint import dprint

from Tribler.Core.dispersy.script import ScenarioScriptBase

class AllChannelNode(Node):
    def create_channel_propagate(self, packets, global_time):
        meta = self._community.get_meta_message(u"channel-propagate")
        return meta.implement(meta.authentication.implement(),
                              meta.distribution.implement(global_time),
                              meta.destination.implement(),
                              meta.payload.implement(packets))

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

        self.caller(self.test_incoming_channel_propagate)
        self.caller(self.test_outgoing_channel_propagate)
        self.caller(self.test_incoming_channel_search_request)
        self.caller(self.test_outgoing_channel_search_request)

    def test_incoming_channel_propagate(self):
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
        packets = ["a"*22 for _ in range(10)]
        global_time = 10
        node.send_message(node.create_channel_propagate(packets, global_time), address)
        yield 0.1

        # # wait for the 'torrent-request' message from SELF to NODE
        # _, message = node.receive_message(addresses=[address], message_names=[u"torrent-request"])
        # assert message.payload.infohash == infohash

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

    def test_outgoing_channel_propagate(self):
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
        community.create_channel_propagate()
        yield 0.01

        # wait for the 'propagate-torrents' message from SELF to NODE
        _, message = node.receive_message(addresses=[address], message_names=[u"propagate-torrents"])
        assert 1 <= len(message.payload.infohashes) <= 50, "to few or to many infohashes"
        assert len(set(message.payload.infohashes)) == len(message.payload.infohashes), "duplicate infohashes"

        dprint(map(lambda infohash: infohash.encode("HEX"), message.payload.infohashes), lines=1)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

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

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

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

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

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
    #     community.create_channel_propagate()
    #     yield 0.01

    #     # wait for the 'propagate-torrents' message from SELF to NODE
    #     _, message = node.receive_message(addresses=[address], message_names=[u"propagate-torrents"])
    #     assert 1 <= len(message.payload.infohashes) <= 50, "to few or to many infohashes"
    #     assert len(set(message.payload.infohashes)) == len(message.payload.infohashes), "duplicate infohashes"

    #     dprint(map(lambda infohash: infohash.encode("HEX"), message.payload.infohashes), lines=1)
    
    
class AllChannelScenarioScript(ScenarioScriptBase):
    def __init__(self, script, name, **kargs):
        ScenarioScriptBase.__init__(self, script, name, 'bartercast.log', **kargs)
        
        self.my_channel = None
        self.want_to_join = False
    
    def join_community(self, my_member):
        master_key = "3081a7301006072a8648ce3d020106052b81040027038192000403cbbfd2dfb67a7db66c88988df56f93fa6e7f982f9a6a0fa8898492c8b8cae23e10b159ace60b7047012082a5aa4c6e221d7e58107bb550436d57e046c11ab4f51f0ab18fa8f58d0346cc12d1cc2b61fc86fe5ed192309152e11e3f02489e30c7c971dd989e1ce5030ea0fb77d5220a92cceb567cbc94bc39ba246a42e215b55e9315b543ddeff0209e916f77c0d747".decode("HEX")
        return AllChannelCommunity.join_community(sha1(master_key).digest(), master_key, my_member, integrate_with_tribler = False)
    
    def execute_scenario_cmd(self, commands):
        if commands[0] == 'create':
            self.my_channel = ChannelCommunity.create_community(self.session.dispersy_member)
            self.my_channel.create_channel('', '')
            
        elif commands[0] == 'publish':
            if self.my_channel:
                infohash = ''.join(choice(letters) for i in xrange(20))
                self.my_channel._disp_create_torrent(infohash, int(time()))
                
        elif commands[0] == 'join':
            self.want_to_join = True
            
        if self.want_to_join:
            from Tribler.Core.dispersy.dispersy import Dispersy
            dispersy = Dispersy.get_instance()
            
            for community in dispersy.get_communities():
                if isinstance(community, PreviewChannelCommunity):
                    dispersy.reclassify_community(community, ChannelCommunity)
                    
                    self.want_to_join = False
from community import ChannelCommunity

from Tribler.Core.dispersy.bloomfilter import BloomFilter
from Tribler.Core.dispersy.crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin
from Tribler.Core.dispersy.member import MyMember
from Tribler.Core.dispersy.script import ScriptBase
from Tribler.Core.dispersy.debug import Node
from Tribler.Core.dispersy.dprint import dprint

class ChannelNode(Node):
    def create_channel(self, name, description, global_time):
        meta = self._community.get_meta_message(u"channel")
        return meta.implement(meta.authentication.implement(self._my_member),
                              meta.distribution.implement(global_time),
                              meta.destination.implement(),
                              meta.payload.implement(name, description))

class ChannelScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = MyMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)

        self.caller(self.test_incoming_channel)
        self.caller(self.test_outgoing_channel)

    def test_incoming_channel(self):
        """
        We will send a 'channel' message from NODE to SELF.
        """
        community = ChannelCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()

        # create node and ensure that SELF knows the node address
        node = ChannelNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.1

        # send a 'channel' message
        global_time = 10
        node.send_message(node.create_channel(u"channel name #1", u"channel description #1", global_time), address)
        yield 0.1

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

    def test_outgoing_channel(self):
        """
        We will send a 'channel' message from SELF to NODE.
        """
        community = ChannelCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()

        # create node and ensure that SELF knows the node address
        node = ChannelNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.1

        # send a 'channel' message
        community.create_channel(u"initial channel name", u"initial channel description")
        yield 0.1

        _, message = node.receive_message(addresses=[address], message_names=[u"channel"])
        assert message.payload.name == u"initial channel name"
        assert message.payload.description == u"initial channel description"

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

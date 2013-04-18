from community import ChannelCommunity

from Tribler.dispersy.crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin
from Tribler.dispersy.member import Member
from Tribler.dispersy.script import ScriptBase
from Tribler.dispersy.tests.debugcommunity.node import DebugNode

class ChannelNode(DebugNode):
    def create_channel(self, name, description, global_time):
        meta = self._community.get_meta_message(u"channel")
        return meta.impl(authentication=(self._my_member,),
                         distribution=(global_time,),
                         payload=(name, description))

class ChannelScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = Member.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)

        self.caller(self.test_incoming_channel)
        self.caller(self.test_outgoing_channel)

    def test_incoming_channel(self):
        """
        We will send a 'channel' message from NODE to SELF.
        """
        community = ChannelCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()

        # create node and ensure that SELF knows the node address
        node = ChannelNode(community)
        node.init_socket()
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
        node = ChannelNode(community)
        node.init_socket()
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

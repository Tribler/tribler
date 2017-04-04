from twisted.internet.defer import inlineCallbacks

from Tribler.community.tunnel.hidden_community import HiddenTunnelCommunity
from Tribler.community.tunnel.tunnel_community import TunnelSettings
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.crypto import ECCrypto
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.Test.test_as_server import TestAsServer


class DummyTunnelCommunity(HiddenTunnelCommunity):

    @classmethod
    def get_master_members(cls, dispersy):
        eccrypto = ECCrypto()
        ec = eccrypto.generate_key(u"curve25519")
        DummyTunnelCommunity.master_key = eccrypto.key_to_bin(ec.pub()).encode('hex')

        master_key_hex = DummyTunnelCommunity.master_key.decode("HEX")
        master = dispersy.get_member(public_key=master_key_hex)
        return [master]


class TestLoadUnloadTunnelCommunity(TestAsServer):

    def setUpPreSession(self):
        super(TestLoadUnloadTunnelCommunity, self).setUpPreSession()
        self.config.set_dispersy(True)
        self.config.set_tunnel_community_enabled(True)

    def create_valid_packet(self, community):
        meta = community.get_meta_message(u"cell")
        conversion = community.get_conversion_for_message(meta)

        meta = community.get_meta_message(u"dht-request")
        message = meta.impl(distribution=(1,), payload=(42, 1, "0"*20))
        return conversion.convert_to_cell(message.packet)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_unload_receive(self):
        """
        Testing whether the TunnelCommunity does not reload itself after unloading
        """
        tunnel_community = self.session.lm.tunnel_community
        dispersy = self.session.lm.dispersy

        some_candidate = Candidate(("1.2.3.4", 1234), False)
        some_packet = self.create_valid_packet(tunnel_community)

        dispersy.on_incoming_packets([(some_candidate, some_packet), ])

        # We should have a functional TunnelCommunity
        self.assertIn(tunnel_community, dispersy.get_communities())

        yield tunnel_community.unload_community()

        # We no longer have a functional TunnelCommunity
        self.assertNotIn(tunnel_community, dispersy.get_communities())

        # There should be no TunnelCommunity classes loaded
        for community in dispersy.get_communities():
            self.assertNotIsInstance(community, HiddenTunnelCommunity)

        dispersy.on_incoming_packets([(some_candidate, some_packet), ])

        # The TunnelCommunity should not reload itself
        for community in dispersy.get_communities():
            self.assertNotIsInstance(community, HiddenTunnelCommunity)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_load_other_tunnel_community(self):
        """
        Testing whether we do not load two different tunnel communities in the same session
        """

        # Load/unload this community so we have a classification
        dispersy = self.session.lm.dispersy
        master_member = DummyTunnelCommunity.get_master_members(dispersy)[0]
        keypair = self.session.multichain_keypair
        dispersy_member = dispersy.get_member(private_key=keypair.key_to_bin())
        community = DummyTunnelCommunity.init_community(dispersy, master_member, dispersy_member,
                                                        tribler_session=self.session, settings=TunnelSettings())
        yield community.unload_community()

        some_candidate = Candidate(("1.2.3.4", 1234), False)
        some_packet = self.create_valid_packet(community)
        dispersy.on_incoming_packets([(some_candidate, some_packet), ])

        tunnel_communities = 0
        for community in dispersy.get_communities():
            if isinstance(community, HiddenTunnelCommunity):
                tunnel_communities += 1

        # We should only have one tunnel community, not multiple
        self.assertEqual(tunnel_communities, 1)

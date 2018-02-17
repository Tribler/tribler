from __future__ import absolute_import

from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto
from Tribler.pyipv8.ipv8.peer import Peer
from Tribler.pyipv8.ipv8.peerdiscovery.network import Network
from twisted.internet.defer import inlineCallbacks

from .endpoint import AutoMockEndpoint
from .discovery import MockWalk


class MockIPv8(object):

    def __init__(self, crypto_curve, overlay_class, *args, **kwargs):
        self.endpoint = AutoMockEndpoint()
        self.endpoint.open()
        self.network = Network()
        self.my_peer = Peer(ECCrypto().generate_key(crypto_curve), self.endpoint.wan_address)
        self.overlay = overlay_class(self.my_peer, self.endpoint, self.network, *args, **kwargs)
        self.discovery = MockWalk(self.overlay)

        self.overlay.my_estimated_wan = self.endpoint.wan_address
        self.overlay.my_estimated_lan = self.endpoint.lan_address

    @inlineCallbacks
    def unload(self):
        self.endpoint.close()
        yield self.overlay.unload()

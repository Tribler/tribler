from typing import Optional
from unittest.mock import Mock

from ipv8.dht.discovery import DHTDiscoveryCommunity
from ipv8.peer import Peer
from ipv8.peerdiscovery.community import DiscoveryCommunity
from ipv8_service import IPv8
from tribler_core.components.base import Component, testcomponent


class Ipv8Component(Component):
    enable_in_gui_test_mode = True

    ipv8: IPv8
    peer: Peer
    peer_discovery_community: Optional[DiscoveryCommunity]
    dht_discovery_community: Optional[DHTDiscoveryCommunity]


@testcomponent
class Ipv8ComponentMock(Ipv8Component):
    ipv8 = Mock()
    peer = Mock()
    peer_discovery_community = Mock()
    dht_discovery_community = Mock()

    def make_bootstrapper(self):
        return Mock()

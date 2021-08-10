from typing import Optional
from unittest.mock import Mock

from ipv8.bootstrapping.dispersy.bootstrapper import DispersyBootstrapper
from ipv8.dht.discovery import DHTDiscoveryCommunity
from ipv8.peer import Peer
from ipv8.peerdiscovery.community import DiscoveryCommunity

from ipv8_service import IPv8

from tribler_core.components.base import Component, testcomponent
from tribler_core.config.tribler_config import TriblerConfig


class Ipv8Component(Component):
    core = True

    ipv8: IPv8
    peer: Peer
    bootstrapper: Optional[DispersyBootstrapper]
    peer_discovery_community: Optional[DiscoveryCommunity]
    dht_discovery_community: Optional[DHTDiscoveryCommunity]

    @classmethod
    def should_be_enabled(cls, config: TriblerConfig):
        return config.ipv8.enabled

    @classmethod
    def make_implementation(cls, config: TriblerConfig, enable: bool):
        if enable:
            from tribler_core.components.implementation.ipv8 import Ipv8ComponentImp
            return Ipv8ComponentImp()
        return Ipv8ComponentMock()


@testcomponent
class Ipv8ComponentMock(Ipv8Component):
    ipv8 = Mock()
    peer = Mock()
    bootstrapper = Mock()
    peer_discovery_community = Mock()
    dht_discovery_community = Mock()

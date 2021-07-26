from ipv8.bootstrapping.dispersy.bootstrapper import DispersyBootstrapper
from ipv8.dht.discovery import DHTDiscoveryCommunity
from ipv8.peer import Peer
from ipv8.peerdiscovery.community import DiscoveryCommunity

from ipv8_service import IPv8

from tribler_core.components.base import Component


class Ipv8Component(Component):
    ipv8: IPv8

class Ipv8PeerComponent(Component):
    peer: Peer

class Ipv8BootstrapperComponent(Component):
    bootstrapper: DispersyBootstrapper

class DHTDiscoveryCommunityComponent(Component):
    community: DHTDiscoveryCommunity

class DiscoveryCommunityComponent(Component):
    community: DiscoveryCommunity

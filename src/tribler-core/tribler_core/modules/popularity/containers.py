from dependency_injector import providers

from ipv8.peerdiscovery.discovery import RandomWalk
from tribler_core.modules import container
from tribler_core.modules.metadata_store.community.sync_strategy import RemovePeers
from tribler_core.modules.popularity.community import PopularityCommunity


class PopularityCommunityContainer(container.CommunityContainer):
    config = providers.Configuration()
    rqc_config = providers.Configuration()

    metadata_store = providers.Dependency()
    torrent_checker = providers.Dependency()

    peer = providers.Dependency()
    endpoint = providers.Dependency()
    network = providers.Dependency()

    community = providers.Factory(PopularityCommunity, peer, endpoint, network,
                                  settings=config, rqc_settings=rqc_config,
                                  metadata_store=metadata_store, torrent_checker=torrent_checker)

    strategies = providers.List(
        providers.Factory(RandomWalk, community, target_peers=30),
        providers.Factory(RemovePeers, community, target_peers=-1),
    )

# pylint: disable=import-outside-toplevel
from ipv8.peer import Peer
from ipv8.peerdiscovery.churn import RandomChurn
from ipv8.peerdiscovery.discovery import RandomWalk

from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.metadata_store.community.sync_strategy import RemovePeers

INFINITE = -1
"""
The amount of target_peers for a walk_strategy definition to never stop.
"""


def add_bootstrapper(community, bootstrapper):
    if bootstrapper:
        community.bootstrappers.append(bootstrapper)


def load_communities(config: TriblerConfig, trustchain_keypair, ipv8, dlmgr, metadata_store,
                     torrent_checker, notifier, bootstrapper):
    """ This method will be splitted after grand Vadim's PR is merged
    """
    peer = Peer(trustchain_keypair)

    if config.discovery_community.enabled:
        from ipv8.peerdiscovery.community import DiscoveryCommunity
        from ipv8.peerdiscovery.community import PeriodicSimilarity

        community = DiscoveryCommunity(peer, ipv8.endpoint, ipv8.network, max_peers=100)
        add_bootstrapper(community, bootstrapper)
        ipv8.overlays.append(community)
        ipv8.strategies.append((RandomChurn(community), INFINITE))
        ipv8.strategies.append((PeriodicSimilarity(community), INFINITE))
        ipv8.strategies.append((RandomWalk(community), 20))

    dht_community = None
    if config.dht.enabled:
        from ipv8.dht.discovery import DHTDiscoveryCommunity
        from ipv8.dht.churn import PingChurn

        dht_community = DHTDiscoveryCommunity(peer, ipv8.endpoint, ipv8.network, max_peers=60)
        add_bootstrapper(dht_community, bootstrapper)

        ipv8.overlays.append(dht_community)
        ipv8.strategies.append((RandomWalk(dht_community), 20))
        ipv8.strategies.append((PingChurn(dht_community), INFINITE))

    #

    if config.general.testnet or config.bandwidth_accounting.testnet:
        from tribler_core.modules.bandwidth_accounting.community import BandwidthAccountingTestnetCommunity
        bandwidth_community_cls = BandwidthAccountingTestnetCommunity
    else:
        from tribler_core.modules.bandwidth_accounting.community import BandwidthAccountingCommunity
        bandwidth_community_cls = BandwidthAccountingCommunity

    bandwidth_community = bandwidth_community_cls(peer, ipv8.endpoint, ipv8.network,
                                                  settings=config.bandwidth_accounting,
                                                  database_path=config.state_dir / "sqlite" / "bandwidth.db")
    add_bootstrapper(bandwidth_community, bootstrapper)

    ipv8.overlays.append(bandwidth_community)
    ipv8.strategies.append((RandomWalk(bandwidth_community), 20))

    #
    if config.tunnel_community.enabled:
        tunnel_community_cls = None
        if config.general.testnet or config.tunnel_community.testnet:
            from tribler_core.modules.tunnel.community.community import TriblerTunnelTestnetCommunity
            tunnel_community_cls = TriblerTunnelTestnetCommunity
        else:
            from tribler_core.modules.tunnel.community.community import TriblerTunnelCommunity
            tunnel_community_cls = TriblerTunnelCommunity

        from tribler_core.modules.tunnel.community.discovery import GoldenRatioStrategy
        from ipv8.messaging.anonymization.community import TunnelSettings
        from ipv8.dht.provider import DHTCommunityProvider

        settings = TunnelSettings()
        settings.min_circuits = config.tunnel_community.min_circuits
        settings.max_circuits = config.tunnel_community.max_circuits

        community = tunnel_community_cls(peer, ipv8.endpoint, ipv8.network,
                                         bandwidth_community=bandwidth_community,
                                         competing_slots=config.tunnel_community.competing_slots,
                                         ipv8=ipv8,
                                         random_slots=config.tunnel_community.random_slots,
                                         config=config,
                                         notifier=notifier,
                                         dlmgr=dlmgr,
                                         dht_provider=DHTCommunityProvider(dht_community, config.ipv8.port),
                                         settings=settings,
                                         )
        add_bootstrapper(community, bootstrapper)

        ipv8.overlays.append(community)
        ipv8.strategies.append((RandomWalk(community), 20))
        ipv8.strategies.append((GoldenRatioStrategy(community), INFINITE))

    if config.popularity_community.enabled:
        from tribler_core.modules.popularity.community import PopularityCommunity

        community = PopularityCommunity(peer, ipv8.endpoint, ipv8.network,
                                        settings=config.popularity_community,
                                        rqc_settings=config.remote_query_community,
                                        metadata_store=metadata_store,
                                        torrent_checker=torrent_checker
                                        )
        add_bootstrapper(community, bootstrapper)

        ipv8.overlays.append(community)
        ipv8.strategies.append((RandomWalk(community), 30))
        ipv8.strategies.append((RemovePeers(community), INFINITE))

    if config.chant.enabled:
        if config.general.testnet or config.chant.testnet:
            from tribler_core.modules.metadata_store.community.gigachannel_community import GigaChannelTestnetCommunity
            gigachannel_community_cls = GigaChannelTestnetCommunity
        else:
            from tribler_core.modules.metadata_store.community.gigachannel_community import GigaChannelCommunity
            gigachannel_community_cls = GigaChannelCommunity

        community = gigachannel_community_cls(peer, ipv8.endpoint, ipv8.network,
                                              settings=config.chant,
                                              rqc_settings=config.remote_query_community,
                                              metadata_store=metadata_store,
                                              notifier=notifier,
                                              max_peers=50
                                              )
        add_bootstrapper(community, bootstrapper)

        ipv8.overlays.append(community)
        ipv8.strategies.append((RandomWalk(community), 30))
        ipv8.strategies.append((RemovePeers(community), INFINITE))

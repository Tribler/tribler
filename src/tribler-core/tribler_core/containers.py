from dependency_injector import containers, providers

from tribler_core.trustchain_keys import TrustChainKeys


# class Ipv8Container(containers.DeclarativeContainer):
#     config = providers.Dependency()
#     endpoint = providers.Factory(DispatcherEndpoint, ["UDPIPv4"], UDPIPv4={'port': config.port, 'ip': config.address})
#     ipv8 = providers.Factory(IPv8, config, enable_statistics=config.enable_statistics, endpoint_override=endpoint)


class ApplicationContainer(containers.DeclarativeContainer):
    config = providers.Dependency()

    trustchain_keys = providers.Singleton(TrustChainKeys, config=config)
    # peer = providers.Factory(Peer, trustchain_keys.provided.trustchain_keypair)
    # ipv8_container = providers.Container(Ipv8Container, peer=peer)

#
# class TriblerContainer(containers.DeclarativeContainer):
#     communities = providers.List(providers.Object(1))
#     ipv8 = providers.Container(Ipv8Container)
# config: TriblerConfig = providers.Configuration()
#
# peer = providers.Dependency()
# endpoint = providers.Dependency()
# network = providers.Dependency()
#
# metadata_store = providers.Dependency()
# torrent_checker = providers.Dependency()
# some = providers.Container(PopularityCommunityContainer,
#                         config=config.popularity_community,
#                         rqc_config=config.remote_query_community,
#                         metadata_store=metadata_store,
#                         torrent_checker=torrent_checker,
#                         endpoint=endpoint, peer=peer,
#                         network=network)
# communities = providers.Object(
#     CommunityProviders(communities=providers.List(
#         providers.Container(PopularityCommunityContainer,
#                             config=config.popularity_community,
#                             rqc_config=config.remote_query_community,
#                             metadata_store=metadata_store,
#                             torrent_checker=torrent_checker,
#                             endpoint=endpoint, peer=peer,
#                             network=network)
#
#     )))

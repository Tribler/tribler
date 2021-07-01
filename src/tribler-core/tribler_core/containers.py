from ipv8.messaging.interfaces.dispatcher.endpoint import DispatcherEndpoint
from ipv8.peer import Peer

from ipv8_service import IPv8

from dependency_injector import containers, providers

from tribler_core.ipv8_config import Ipv8Config
from tribler_core.trustchain_keys import TrustChainKeys


class Ipv8Container(containers.DeclarativeContainer):
    state_dir = providers.Dependency()
    config = providers.Configuration()

    ipv8_config = providers.Singleton(Ipv8Config, state_dir=state_dir, config=config.provider)

    endpoint = providers.Singleton(
        DispatcherEndpoint,
        providers.List(providers.Object("UDPIPv4")),
        UDPIPv4=providers.Dict(port=providers.Factory(config.port), ip=providers.Factory(config.address)),
    )

    ipv8 = providers.Singleton(
        IPv8, ipv8_config.provided.value, enable_statistics=config.statistics, endpoint_override=endpoint
    )


class ApplicationContainer(containers.DeclarativeContainer):
    state_dir = providers.Dependency()
    config = providers.Configuration()

    trustchain_keys = providers.Singleton(TrustChainKeys, state_dir=state_dir, config=config.provider)
    peer = providers.Singleton(Peer, trustchain_keys.provided.trustchain_keypair)

    ipv8_container = providers.Container(Ipv8Container, state_dir=state_dir, config=config.ipv8)

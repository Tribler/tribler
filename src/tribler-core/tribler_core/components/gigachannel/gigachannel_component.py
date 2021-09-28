from ipv8.peerdiscovery.discovery import RandomWalk

from ipv8_service import IPv8

from tribler_core.components.base import Component
from tribler_core.components.ipv8 import Ipv8Component
from tribler_core.components.gigachannel.community.gigachannel_community import GigaChannelCommunity, \
    GigaChannelTestnetCommunity
from tribler_core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler_core.components.reporter import ReporterComponent
from tribler_core.components.restapi import RestfulComponent
from tribler_core.components.gigachannel.community.sync_strategy import RemovePeers
from tribler_core.restapi.rest_manager import RESTManager

INFINITE = -1


class GigaChannelComponent(RestfulComponent):
    community: GigaChannelCommunity

    _ipv8: IPv8

    async def run(self):
        await self.get_component(ReporterComponent)

        config = self.session.config
        notifier = self.session.notifier

        ipv8_component = await self.require_component(Ipv8Component)
        self._ipv8 = ipv8_component.ipv8
        peer = ipv8_component.peer

        metadata_store_component = await self.require_component(MetadataStoreComponent)

        giga_channel_cls = GigaChannelTestnetCommunity if config.general.testnet else GigaChannelCommunity
        community = giga_channel_cls(
            peer,
            self._ipv8.endpoint,
            self._ipv8.network,
            notifier=notifier,
            settings=config.chant,
            rqc_settings=config.remote_query_community,
            metadata_store=metadata_store_component.mds,
            max_peers=50,
        )
        self.community = community

        self._ipv8.add_strategy(community, RandomWalk(community), 30)
        self._ipv8.add_strategy(community, RemovePeers(community), INFINITE)

        community.bootstrappers.append(ipv8_component.make_bootstrapper())

        await self.init_endpoints(['remote_query', 'channels', 'collections'], [('gigachannel_community', community)])


    async def shutdown(self):
        await super().shutdown()
        if self._ipv8:
            await self._ipv8.unload_overlay(self.community)

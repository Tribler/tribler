from tribler.core.components.gigachannel.gigachannel_component import GigaChannelComponent
from tribler.core.components.ipv8.ipv8_component import Ipv8Component
from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.knowledge.knowledge_component import KnowledgeComponent
from tribler.core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler.core.components.session import Session

# pylint: disable=protected-access


async def test_giga_channel_component(tribler_config):
    tribler_config.ipv8.enabled = True
    tribler_config.libtorrent.enabled = True
    tribler_config.chant.enabled = True
    components = [KnowledgeComponent(), MetadataStoreComponent(), KeyComponent(), Ipv8Component(),
                  GigaChannelComponent()]
    async with Session(tribler_config, components) as session:
        comp = session.get_instance(GigaChannelComponent)
        assert comp.started_event.is_set()
        assert not comp.failed
        assert comp.community
        assert comp._ipv8_component

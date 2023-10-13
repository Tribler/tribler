from tribler.core.components.ipv8.ipv8_component import Ipv8Component
from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.session import Session


# pylint: disable=protected-access
async def test_ipv8_component(tribler_config):
    async with Session(tribler_config, [KeyComponent(), Ipv8Component()]) as session:
        comp = session.get_instance(Ipv8Component)
        assert comp.started_event.is_set() and not comp.failed
        assert comp.ipv8
        assert comp.peer
        assert not comp.dht_discovery_community
        assert comp._task_manager
        assert not comp._peer_discovery_community


async def test_ipv8_component_dht_disabled(tribler_config):
    tribler_config.ipv8.enabled = True
    tribler_config.dht.enabled = True
    async with Session(tribler_config, [KeyComponent(), Ipv8Component()]) as session:
        comp = session.get_instance(Ipv8Component)
        assert comp.dht_discovery_community


async def test_ipv8_component_discovery_community_enabled(tribler_config):
    tribler_config.ipv8.enabled = True
    tribler_config.gui_test_mode = False
    tribler_config.discovery_community.enabled = True
    async with Session(tribler_config, [KeyComponent(), Ipv8Component()]) as session:
        comp = session.get_instance(Ipv8Component)
        assert comp._peer_discovery_community


async def test_ipv8_component_statistics_enabled(tribler_config):
    tribler_config.ipv8.enabled = True
    tribler_config.ipv8.statistics = True
    tribler_config.gui_test_mode = False
    tribler_config.dht.enabled = True
    async with Session(tribler_config, [KeyComponent(), Ipv8Component()]) as session:
        comp = session.get_instance(Ipv8Component)
        assert comp.dht_discovery_community.get_prefix() in comp.ipv8.endpoint.statistics


async def test_ipv8_rendezvous_enabled(tribler_config):
    tribler_config.ipv8.rendezvous_stats = True
    async with Session(tribler_config, [KeyComponent(), Ipv8Component()]) as session:
        comp = session.get_instance(Ipv8Component)
        assert comp.rendezvous_db is not None
        assert comp.rendevous_hook is not None

from tribler.core.components.database.database_component import DatabaseComponent
from tribler.core.components.ipv8.ipv8_component import Ipv8Component
from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.knowledge.knowledge_component import KnowledgeComponent
from tribler.core.components.session import Session


async def test_database_component(tribler_config):
    components = [DatabaseComponent(), KnowledgeComponent(), Ipv8Component(), KeyComponent()]
    async with Session(tribler_config, components) as session:
        comp = session.get_instance(DatabaseComponent)
        assert comp.started_event.is_set() and not comp.failed
        assert comp.mds

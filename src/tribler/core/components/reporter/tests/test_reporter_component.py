from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.reporter.reporter_component import ReporterComponent
from tribler.core.components.session import Session


# pylint: disable=protected-access
async def test_reporter_component(tribler_config):
    components = [KeyComponent(), ReporterComponent()]
    async with Session(tribler_config, components) as session:
        comp = session.get_instance(ReporterComponent)
        assert comp.started_event.is_set() and not comp.failed

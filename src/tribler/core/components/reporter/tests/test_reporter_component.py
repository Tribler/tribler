import pytest

from tribler.core.components.base import Session
from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.reporter.reporter_component import ReporterComponent



# pylint: disable=protected-access
async def test_reporter_component(tribler_config):
    components = [KeyComponent(), ReporterComponent()]
    async with Session(tribler_config, components).start():
        comp = ReporterComponent.instance()
        assert comp.started_event.is_set() and not comp.failed

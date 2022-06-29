from tribler.core.components.session import Session
from tribler.core.components.version_check.version_check_component import VersionCheckComponent


# pylint: disable=protected-access
async def test_version_check_component(tribler_config):
    components = [VersionCheckComponent()]
    async with Session(tribler_config, components) as session:
        comp = session.get_instance(VersionCheckComponent)
        assert comp.started_event.is_set() and not comp.failed
        assert comp.version_check_manager

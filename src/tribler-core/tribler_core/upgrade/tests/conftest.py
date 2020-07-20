import pytest

from tribler_core.upgrade.upgrade import TriblerUpgrader


@pytest.fixture
def upgrader(session):
    return TriblerUpgrader(session)

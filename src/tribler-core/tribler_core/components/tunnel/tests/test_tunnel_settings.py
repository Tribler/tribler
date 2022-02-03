import pytest

from tribler_core.components.ipv8.settings import Ipv8Settings
from tribler_core.utilities.network_utils import NetworkUtils


@pytest.mark.asyncio
async def test_port_validation():
    assert Ipv8Settings(port=0)

    with pytest.raises(ValueError):
        Ipv8Settings(port=-1)

    with pytest.raises(ValueError):
        Ipv8Settings(port=NetworkUtils.MAX_PORT + 1)

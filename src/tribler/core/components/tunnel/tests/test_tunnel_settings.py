import pytest

from tribler.core.components.ipv8.settings import Ipv8Settings
from tribler.core.utilities.network_utils import NetworkUtils


def test_port_validation():
    assert Ipv8Settings(port=0)

    with pytest.raises(ValueError):
        Ipv8Settings(port=-1)

    with pytest.raises(ValueError):
        Ipv8Settings(port=NetworkUtils.MAX_PORT + 1)

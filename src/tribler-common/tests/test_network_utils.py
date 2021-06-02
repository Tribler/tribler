import pytest

from tribler_common.network_utils import (
    FreePortNotFoundError,
    NetworkUtils,
)


# fmt: off


@pytest.fixture(name="mock_socket")
def fixture_mock_socket():
    class MockSocket:
        bound_ports = set()

        def bind(self, host_port):
            _, port = host_port
            try:
                if port in self.bound_ports:
                    raise OSError
            finally:
                self.bound_ports.add(port)

        def __enter__(self):
            return self

        def __exit__(self, t, v, tb):
            pass

    return {MockSocket}


def test_get_first_free_port(mock_socket):
    # target port is free
    assert NetworkUtils(mock_socket).get_first_free_port(start=0) == 0

    # target port is locked
    assert NetworkUtils(mock_socket).get_first_free_port(start=0) == 1


def test_get_random_free_port(mock_socket):
    assert NetworkUtils(mock_socket).get_random_free_port(start=0, stop=0) == 0

    port1 = NetworkUtils(mock_socket).get_random_free_port(start=0, stop=3)
    port2 = NetworkUtils(mock_socket).get_random_free_port(start=0, stop=3)

    assert port1 != port2


def test_get_first_free_port_exceptions():
    with pytest.raises(OverflowError):
        NetworkUtils().get_first_free_port(start=-100)

    with pytest.raises(FreePortNotFoundError):
        NetworkUtils().get_first_free_port(start=100, stop=0)

    with pytest.raises(OverflowError):
        NetworkUtils().get_first_free_port(start=NetworkUtils.MAX_PORT + 1, stop=NetworkUtils.MAX_PORT + 2)


def test_get_random_free_port_exceptions():
    with pytest.raises(ValueError):
        NetworkUtils().get_random_free_port(start=100, stop=50)

    with pytest.raises(ValueError):
        NetworkUtils().get_random_free_port(start=-100, stop=-50)

    with pytest.raises(ValueError):
        NetworkUtils().get_random_free_port(start=NetworkUtils.MAX_PORT + 1, stop=NetworkUtils.MAX_PORT + 2)

    with pytest.raises(FreePortNotFoundError):
        NetworkUtils().get_random_free_port(attempts=0)

import random
import socket

import pytest

from tribler_common.network_utils import (
    FreePortNotFoundError,
    NetworkUtils, autodetect_socket_style,
    get_random_port,
)


def test_get_random_port():
    random_port = get_random_port()
    assert isinstance(random_port, int)
    assert random_port


def test_get_random_port_tcp():
    rand_port_num = random.randint(1000, 10000)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        attempts = 0
        while attempts < 20:
            try:
                sock.bind(('', rand_port_num))
                random_port = get_random_port(socket_type='tcp', min_port=rand_port_num, max_port=rand_port_num)
                assert random_port > rand_port_num  # It should have picked a higher port
                return
            except OSError:
                attempts += 1
                rand_port_num += 1

    assert False


def test_get_random_port_udp():
    random_port = get_random_port(socket_type='udp')
    assert isinstance(random_port, int)
    assert random_port


def test_get_random_port_invalid_type():
    with pytest.raises(AssertionError):
        get_random_port(socket_type="http")


def test_autodetect_socket_style():
    style = autodetect_socket_style()
    assert style == 0 or autodetect_socket_style() == 1


def test_get_first_free_port():
    class MockSocket:
        def __init__(self):
            self.bound_ports = [60000, 60001]

        def bind(self, host_port):
            _, port = host_port

            if port in self.bound_ports:
                raise OSError

            self.bound_ports.append(port)

        def __enter__(self):
            return self

        def __exit__(self, t, v, tb):
            pass

    # target port is free
    assert NetworkUtils(MockSocket).get_first_free_port(start=50000) == 50000

    # target port is locked
    assert NetworkUtils(MockSocket).get_first_free_port(start=60000) == 60002


def test_get_first_free_port_none_available():
    # no free ports found
    with pytest.raises(FreePortNotFoundError):
        NetworkUtils().get_first_free_port(start=50000, limit=0)

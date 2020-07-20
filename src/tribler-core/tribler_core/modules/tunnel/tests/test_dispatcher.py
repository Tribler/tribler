from unittest.mock import Mock

from ipv8.messaging.anonymization.tunnel import CIRCUIT_STATE_EXTENDING, CIRCUIT_STATE_READY, CIRCUIT_TYPE_DATA
from ipv8.util import succeed

import pytest

from tribler_core.modules.tunnel.community.dispatcher import TunnelDispatcher


@pytest.fixture
async def dispatcher():
    mock_tunnel_community = Mock()
    mock_tunnel_community.select_circuit = lambda *_: None
    mock_tunnel_community.send_data = lambda *_: None
    dispatcher = TunnelDispatcher(mock_tunnel_community)
    yield dispatcher
    await dispatcher.shutdown_task_manager()


@pytest.fixture
def mock_circuit():
    mock_circuit = Mock()
    mock_circuit.state = CIRCUIT_STATE_EXTENDING
    mock_circuit.circuit_id = 3
    mock_circuit.peer.address = ("1.1.1.1", 1234)
    mock_circuit.tunnel_data = lambda *_: None
    return mock_circuit


def test_on_tunnel_in(dispatcher):
    """
    Test whether no data is sent to the SOCKS5 server when we receive data from the tunnels
    """
    mock_circuit = Mock()
    mock_circuit.goal_hops = 300
    mock_circuit.circuit_id = b'a'
    mock_circuit.ctype = CIRCUIT_TYPE_DATA
    origin = ("0.0.0.0", 1024)
    assert not dispatcher.on_incoming_from_tunnel(dispatcher.tunnel_community, mock_circuit, origin, b'a')

    mock_circuit.goal_hops = 1
    mock_sock_server = Mock()
    mock_session = Mock()
    mock_session._udp_socket = None
    mock_sock_server.sessions = [mock_session]
    dispatcher.set_socks_servers([mock_sock_server])
    dispatcher.destinations[1] = {b'a': mock_circuit}
    assert not dispatcher.on_incoming_from_tunnel(dispatcher.tunnel_community, mock_circuit, origin, b'a')

    mock_session._udp_socket = Mock()
    mock_session._udp_socket.sendDatagram = lambda _: True
    assert dispatcher.on_incoming_from_tunnel(dispatcher.tunnel_community, mock_circuit, origin, b'a')


def test_on_socks_in_udp(dispatcher, mock_circuit):
    """
    Test whether data is correctly dispatched to a circuit
    """
    mock_socks_server = Mock()
    dispatcher.set_socks_servers([mock_socks_server])

    mock_udp_connection = Mock()
    mock_udp_connection.socksconnection = Mock()
    mock_udp_connection.socksconnection.socksserver = mock_socks_server

    mock_request = Mock()
    mock_request.destination = ("0.0.0.0", 1024)
    mock_request.payload = 'a'

    # No circuit is selected
    assert not dispatcher.on_socks5_udp_data(mock_udp_connection, mock_request)

    dispatcher.tunnel_community.select_circuit = lambda *_: mock_circuit

    # Circuit is not ready
    assert not dispatcher.on_socks5_udp_data(mock_udp_connection, mock_request)

    mock_circuit.state = CIRCUIT_STATE_READY

    # Circuit ready, should be able to tunnel data
    assert dispatcher.on_socks5_udp_data(mock_udp_connection, mock_request)


@pytest.mark.asyncio
async def test_on_socks_in_tcp(dispatcher):
    """
    Test whether TCP connect request are correctly dispatched to the TunnelCommunity
    """
    tcp_connection = Mock()
    dispatcher.set_socks_servers([tcp_connection.socksserver])

    dispatcher.tunnel_community.perform_http_request = Mock(return_value=succeed(None))
    await dispatcher.on_socks5_tcp_data(tcp_connection, ("0.0.0.0", 1024), b'')
    tcp_connection.transport.write.assert_not_called()

    dispatcher.tunnel_community.perform_http_request = Mock(return_value=succeed(b'test'))
    await dispatcher.on_socks5_tcp_data(tcp_connection, ("0.0.0.0", 1024), b'')
    tcp_connection.transport.write.assert_called_once_with(b'test')


def test_circuit_dead(dispatcher, mock_circuit):
    """
    Test whether the correct peers are removed when a circuit breaks
    """
    dispatcher.destinations = {1: {'a': mock_circuit, 'b': mock_circuit},
                               2: {'c': mock_circuit, 'a': mock_circuit}}
    res = dispatcher.circuit_dead(mock_circuit)
    assert res
    assert len(res) == 3

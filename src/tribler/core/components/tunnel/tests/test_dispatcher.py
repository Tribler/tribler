from unittest.mock import Mock

from ipv8.messaging.anonymization.tunnel import CIRCUIT_STATE_EXTENDING, CIRCUIT_STATE_READY, CIRCUIT_TYPE_DATA
from ipv8.util import succeed

import pytest

from tribler_core.components.tunnel.community.dispatcher import TunnelDispatcher


@pytest.fixture(name='dispatcher')
async def fixture_dispatcher():
    mock_tunnel_community = Mock()
    mock_tunnel_community.send_data = lambda *_: None
    dispatcher = TunnelDispatcher(mock_tunnel_community)
    yield dispatcher
    await dispatcher.shutdown_task_manager()


@pytest.fixture(name='mock_circuit')
def fixture_mock_circuit():
    mock_circuit = Mock()
    mock_circuit.state = CIRCUIT_STATE_EXTENDING
    mock_circuit.circuit_id = 3
    mock_circuit.goal_hops = 1
    mock_circuit.peer.address = ("1.1.1.1", 1234)
    mock_circuit.tunnel_data = lambda *_: None
    return mock_circuit


def test_on_tunnel_in(dispatcher):
    """
    Test whether no data is sent to the SOCKS5 server when we receive data from the tunnels
    """
    origin = ("0.0.0.0", 1024)

    mock_circuit = Mock(goal_hops=300, circuit_id=123, ctype=CIRCUIT_TYPE_DATA)
    assert not dispatcher.on_incoming_from_tunnel(dispatcher.tunnels, mock_circuit, origin, b'a')

    mock_circuit.goal_hops = 1
    mock_sock_server = Mock(sessions=[])
    dispatcher.set_socks_servers([mock_sock_server])
    assert not dispatcher.on_incoming_from_tunnel(dispatcher.tunnels, mock_circuit, origin, b'a')

    mock_session = Mock(udp_connection=None)
    mock_sock_server.sessions = [mock_session]
    assert not dispatcher.on_incoming_from_tunnel(dispatcher.tunnels, mock_circuit, origin, b'a')

    dispatcher.cid_to_con[b'a'] = mock_session
    assert not dispatcher.on_incoming_from_tunnel(dispatcher.tunnels, mock_circuit, origin, b'a')

    mock_session.udp_connection = Mock()
    mock_session.udp_connection.send_datagram = lambda _: True
    assert dispatcher.on_incoming_from_tunnel(dispatcher.tunnels, mock_circuit, origin, b'a')


def test_on_socks_in_udp(dispatcher, mock_circuit):
    """
    Test whether data is correctly dispatched to a circuit
    """
    mock_circuit.ctype = CIRCUIT_TYPE_DATA
    mock_request = Mock(destination=("0.0.0.0", 1024), data=b'a')
    mock_udp_connection = Mock()
    dispatcher.set_socks_servers([mock_udp_connection.socksconnection.socksserver])
    dispatcher.tunnels.create_circuit = lambda **_: None
    dispatcher.tunnels.circuits = {}

    # No circuit is selected
    assert not dispatcher.on_socks5_udp_data(mock_udp_connection, mock_request)

    dispatcher.tunnels.circuits = {mock_circuit.circuit_id: mock_circuit}

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

    dispatcher.tunnels.perform_http_request = Mock(return_value=succeed(None))
    await dispatcher.on_socks5_tcp_data(tcp_connection, ("0.0.0.0", 1024), b'')
    tcp_connection.transport.write.assert_not_called()

    dispatcher.tunnels.perform_http_request = Mock(return_value=succeed(b'test'))
    await dispatcher.on_socks5_tcp_data(tcp_connection, ("0.0.0.0", 1024), b'')
    tcp_connection.transport.write.assert_called_once_with(b'test')


def test_circuit_dead(dispatcher, mock_circuit):
    """
    Test whether the correct peers are removed when a circuit breaks
    """
    connection = Mock()

    dispatcher.con_to_cir = {connection: {1: mock_circuit,
                                          2: mock_circuit,
                                          3: mock_circuit}}
    dispatcher.cid_to_con = {mock_circuit.circuit_id: connection}

    res = dispatcher.circuit_dead(mock_circuit)
    assert res
    assert len(res) == 3
    assert len(dispatcher.con_to_cir[connection]) == 0
    assert mock_circuit.circuit_id not in dispatcher.cid_to_con


def test_check_connections(dispatcher, mock_circuit):
    """
    Test whether closed connections are cleaned up properly
    """
    connection = Mock(udp_connection=None)

    dispatcher.con_to_cir = {connection: {1: mock_circuit,
                                          2: mock_circuit,
                                          3: mock_circuit}}
    dispatcher.cid_to_con = {mock_circuit.circuit_id: connection, 2: Mock()}

    dispatcher.check_connections()
    assert connection not in dispatcher.con_to_cir
    assert mock_circuit.circuit_id not in dispatcher.cid_to_con
    assert 2 in dispatcher.cid_to_con

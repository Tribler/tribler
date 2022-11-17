import socket
from unittest.mock import Mock, patch

import pytest
from PyQt5 import QtTest

from tribler.gui.port_checker import PortChecker


@pytest.fixture(name="base_port")
def mock_base_port():
    return 52194


@pytest.fixture(name="mock_callback")
def mock_callback():
    return Mock()


@pytest.fixture(name="port_checker_helpers")
@patch('psutil.Process')
def port_checker_helpers(mock_process, base_port, mock_callback):
    mock_pid = 123
    check_interval_in_ms = 10
    timeout_in_ms = 100
    port_checker = PortChecker(mock_pid,
                               base_port,
                               callback=mock_callback,
                               check_interval_in_ms=check_interval_in_ms,
                               timeout_in_ms=timeout_in_ms)
    return port_checker, mock_process, mock_callback


def test_detect_port_with_no_connections(port_checker_helpers):
    port_checker, mock_process, _ = port_checker_helpers

    mock_process.return_value.connections.return_value = []

    port_checker.check_port()

    assert port_checker.detected_port is None


def test_detect_port_with_out_of_range_connections(base_port, port_checker_helpers):
    port_checker, mock_process, _ = port_checker_helpers

    mock_process.return_value.connections.return_value = [
        mock_connection(base_port + port_checker.num_ports_to_check + 1),  # out of range port
        mock_connection(base_port + port_checker.num_ports_to_check + 2),  # out of range port
    ]

    port_checker.check_port()

    assert port_checker.detected_port is None


def test_detect_port_with_in_range_connections(base_port, port_checker_helpers):
    port_checker, mock_process, _ = port_checker_helpers

    port_in_range_1 = base_port + port_checker.num_ports_to_check - 1
    port_in_range_2 = base_port + port_checker.num_ports_to_check - 2
    mock_process.return_value.connections.return_value = [
        mock_connection(port_in_range_1),  # port within range
        mock_connection(port_in_range_2),  # closest port to the base port expected to be detected
    ]

    port_checker.check_port()

    assert port_checker.detected_port == port_in_range_2


def test_check_port_detected(base_port, port_checker_helpers):
    port_checker, mock_process, callback = port_checker_helpers

    port_checker.check_port()
    callback.assert_not_called()

    # If the port is detected, callback should be called
    port_checker.detected_port = base_port
    port_checker.check_port()

    callback.assert_called_once()
    callback.assert_called_with(base_port)


async def test_start_checking(base_port, port_checker_helpers, qapp):
    port_checker, mock_process, callback = port_checker_helpers

    mock_process.return_value.connections.return_value = [
        mock_connection(base_port)
    ]

    port_checker.start_checking()
    QtTest.QTest.qWait(port_checker.timeout_in_ms)

    assert port_checker.detected_port == base_port
    callback.assert_called_with(base_port)
    callback.assert_called_once()


async def test_start_checking_no_port_detected(base_port, port_checker_helpers, qapp):
    port_checker, mock_process, callback = port_checker_helpers

    port_checker.start_checking()
    QtTest.QTest.qWait(port_checker.timeout_in_ms)

    assert port_checker.detected_port is None


def mock_connection(port):
    mock_connection = Mock()
    mock_connection.laddr.ip = '127.0.0.1'
    mock_connection.laddr.port = port
    mock_connection.status = 'LISTEN'
    mock_connection.type = socket.SocketKind.SOCK_STREAM
    return mock_connection
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tribler.core.components.resource_monitor.implementation.core import CoreResourceMonitor
from tribler.core.components.resource_monitor.settings import ResourceMonitorSettings
from tribler.core.components.restapi.rest.base_api_test import do_request
from tribler.core.components.restapi.rest.debug_endpoint import DebugEndpoint


# pylint: disable=redefined-outer-name, unused-argument, protected-access


@pytest.fixture
def mock_tunnel_community():
    return MagicMock()


@pytest.fixture
async def core_resource_monitor(tmp_path):
    resource_monitor = CoreResourceMonitor(notifier=MagicMock(),
                                           state_dir=tmp_path,
                                           config=ResourceMonitorSettings(),
                                           log_dir=tmp_path / 'logs')
    resource_monitor.check_resources()
    yield resource_monitor
    await resource_monitor.stop()


@pytest.fixture
def endpoint(mock_tunnel_community, tmp_path, core_resource_monitor):
    return DebugEndpoint(tmp_path, tmp_path / 'logs', tunnel_community=mock_tunnel_community,
                         resource_monitor=core_resource_monitor)


async def test_get_open_files(rest_api, tmp_path):
    """
    Test whether the API returns open files
    """
    with open(tmp_path / "test.txt", "w"):
        response_json = await do_request(rest_api, 'debug/open_files', expected_code=200)
        assert response_json['open_files']


async def test_get_open_sockets(rest_api):
    """
    Test whether the API returns open sockets
    """
    response_json = await do_request(rest_api, 'debug/open_sockets', expected_code=200)
    assert len(response_json['open_sockets']) >= 1


async def test_get_threads(rest_api):
    """
    Test whether the API returns open threads
    """
    response_json = await do_request(rest_api, 'debug/threads', expected_code=200)
    assert len(response_json['threads']) >= 1


async def test_get_cpu_history(rest_api):
    """
    Test whether the API returns the cpu history
    """
    response_json = await do_request(rest_api, 'debug/cpu/history', expected_code=200)
    assert len(response_json['cpu_history']) >= 1


async def test_get_memory_history(rest_api):
    """
    Test whether the API returns the memory history
    """
    response_json = await do_request(rest_api, 'debug/memory/history', expected_code=200)
    assert len(response_json['memory_history']) >= 1


@pytest.mark.skip
async def test_dump_memory(rest_api, tmp_path):
    """
    Test whether the API returns a memory dump
    """
    response = await do_request(rest_api, 'debug/memory/dump', expected_code=200)
    assert response


def create_dummy_logs(log_dir: Path, process: str = 'core', log_message: str = None, num_logs: int = 100):
    """
    Create dummy log lines to test debug log endpoint.
    :param log_dir: Directory to place the log files.
    :param process: Either 'core' or 'gui'
    :param log_message: log line to write to file.
    :param num_logs: Number of log lines to write
    :return: None
    """
    if not log_dir.exists():
        os.makedirs(log_dir)

    info_log_file_path = log_dir / f'tribler-{process}-info.log'
    log_message = log_message if log_message else f"This is a {process} test log message."

    with open(info_log_file_path, "w") as info_log_file:
        for log_index in range(num_logs):
            info_log_file.write(f"{log_message} {log_index}\n")


async def test_debug_pane_core_logs(rest_api, tmp_path):
    """
    Test whether the API returns the logs
    """
    process = 'core'
    test_core_log_message = "This is the core test log message"
    num_logs = 100

    create_dummy_logs(tmp_path / 'logs', process='core', log_message=test_core_log_message, num_logs=num_logs)

    json_response = await do_request(rest_api, f'debug/log?process={process}&max_lines={num_logs}', expected_code=200)
    logs = json_response['content'].strip().split("\n")

    # Check number of logs returned is correct
    assert len(logs) == num_logs

    # Check if test log message is present in the logs, at least once
    log_exists = any(test_core_log_message in log for log in logs)
    assert log_exists, "Test log not found in the debug log response"


async def test_debug_pane_core_logs_in_root_dir(rest_api, tmp_path):
    """
    Test whether the API returns the logs when logs are present in the root directory.
    """

    # Tribler logs are by default set to root state directory. Here we define the
    # root state directory by updating 'TSTATEDIR' environment variable.
    process = 'foobar'
    num_logs = 100

    create_dummy_logs(tmp_path / 'logs', process=process, num_logs=num_logs)
    json_response = await do_request(rest_api, f'debug/log?process={process}&max_lines={num_logs}',
                                     expected_code=200)
    logs = json_response['content'].strip().split("\n")

    # Check number of logs returned is correct
    assert len(logs) == num_logs


async def test_debug_pane_default_num_logs(rest_api, tmp_path):
    """
    Test whether the API returns the last 100 logs when no max_lines parameter is not provided
    """
    module = 'gui'
    default_num_logs_returned = 100
    num_logs_to_write = 200

    # Log directory
    log_dir = tmp_path / 'logs'
    create_dummy_logs(log_dir, process=module, log_message=log_dir, num_logs=num_logs_to_write)

    json_response = await do_request(rest_api, f'debug/log?process={module}&max_lines=', expected_code=200)
    logs = json_response['content'].strip().split("\n")
    assert len(logs) == default_num_logs_returned


async def test_debug_pane_no_logs(rest_api, tmp_path):
    """
    Test whether the API returns the default response when no log files are found.
    """
    module = 'gui'
    with patch('tribler.core.components.restapi.rest.debug_endpoint.get_root_state_directory',
               new=lambda: tmp_path / 'nondir'):
        json_response = await do_request(rest_api, f'debug/log?process={module}&max_lines=', expected_code=200)

    assert not json_response['content']
    assert json_response['max_lines'] == 0


async def test_get_profiler_state(rest_api):
    """
    Test getting the state of the profiler
    """
    json_response = await do_request(rest_api, 'debug/profiler', expected_code=200)
    assert 'state' in json_response


async def test_start_stop_profiler(rest_api, core_resource_monitor):
    """
    Test starting and stopping the profiler using the API

    Note that we mock the start/stop profiler methods since actually starting the profiler could influence the
    tests.
    """
    core_resource_monitor.profiler.start = MagicMock()
    core_resource_monitor.profiler.stop = MagicMock()

    await do_request(rest_api, 'debug/profiler', expected_code=200, request_type='PUT')
    assert core_resource_monitor.profiler.start.called
    await do_request(rest_api, 'debug/profiler', expected_code=200, request_type='DELETE')
    assert core_resource_monitor.profiler.stop.called

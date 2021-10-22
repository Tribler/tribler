import os
from pathlib import Path
from unittest.mock import Mock, patch

from aiohttp.web_app import Application

import pytest

from tribler_core.components.resource_monitor.implementation.core import CoreResourceMonitor
from tribler_core.components.resource_monitor.settings import ResourceMonitorSettings
from tribler_core.components.restapi.rest.base_api_test import do_request
from tribler_core.components.restapi.rest.debug_endpoint import DebugEndpoint
from tribler_core.components.restapi.rest.rest_manager import error_middleware


@pytest.fixture
def mock_tunnel_community():
    mock_tunnel_community = Mock()
    return mock_tunnel_community


@pytest.fixture
def endpoint():
    endpoint = DebugEndpoint()
    return endpoint


@pytest.fixture
async def core_resource_monitor(tmp_path):
    resource_monitor = CoreResourceMonitor(notifier=Mock(),
                                           state_dir=tmp_path,
                                           config=ResourceMonitorSettings(),
                                           log_dir=tmp_path / 'logs')
    yield resource_monitor
    await resource_monitor.stop()


@pytest.fixture
def rest_api(loop, aiohttp_client, mock_tunnel_community, endpoint):  # pylint: disable=unused-argument
    endpoint.tunnel_community = mock_tunnel_community

    app = Application(middlewares=[error_middleware])
    app.add_subapp('/debug', endpoint.app)
    return loop.run_until_complete(aiohttp_client(app))


async def test_get_slots(rest_api, mock_tunnel_community):
    """
    Test whether we can get slot information from the API
    """

    mock_tunnel_community.random_slots = [None, None, None, 12345]
    mock_tunnel_community.competing_slots = [(0, None), (12345, 12345)]
    response_json = await do_request(rest_api, 'debug/circuits/slots', expected_code=200)
    assert len(response_json["slots"]["random"]) == 4


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


async def test_get_cpu_history(rest_api, endpoint, core_resource_monitor):
    """
    Test whether the API returns the cpu history
    """
    endpoint.resource_monitor = core_resource_monitor
    core_resource_monitor.check_resources()
    response_json = await do_request(rest_api, 'debug/cpu/history', expected_code=200)
    assert len(response_json['cpu_history']) >= 1


async def test_get_memory_history(rest_api, endpoint, core_resource_monitor):
    """
    Test whether the API returns the memory history
    """
    endpoint.resource_monitor = core_resource_monitor
    core_resource_monitor.check_resources()
    response_json = await do_request(rest_api, 'debug/memory/history', expected_code=200)
    assert len(response_json['memory_history']) >= 1


@pytest.mark.skip
async def test_dump_memory(rest_api, tmp_path, endpoint):
    """
    Test whether the API returns a memory dump
    """
    endpoint.state_dir = tmp_path
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


async def test_debug_pane_core_logs(rest_api, endpoint, tmp_path):
    """
    Test whether the API returns the logs
    """
    log_dir = tmp_path / 'logs'
    endpoint.log_dir = log_dir
    process = 'core'
    test_core_log_message = "This is the core test log message"
    num_logs = 100

    create_dummy_logs(log_dir, process='core', log_message=test_core_log_message, num_logs=num_logs)

    json_response = await do_request(rest_api, f'debug/log?process={process}&max_lines={num_logs}', expected_code=200)
    logs = json_response['content'].strip().split("\n")

    # Check number of logs returned is correct
    assert len(logs) == num_logs

    # Check if test log message is present in the logs, at least once
    log_exists = any(test_core_log_message in log for log in logs)
    assert log_exists, "Test log not found in the debug log response"


async def test_debug_pane_core_logs_in_root_dir(rest_api, tmp_path, endpoint):
    """
    Test whether the API returns the logs when logs are present in the root directory.
    """

    # Tribler logs are by default set to root state directory. Here we define the
    # root state directory by updating 'TSTATEDIR' environment variable.
    root_state_dir = tmp_path
    endpoint.log_dir = root_state_dir / 'some_version' / 'log_dir'

    process = 'foobar'
    num_logs = 100

    create_dummy_logs(root_state_dir, process=process, num_logs=num_logs)
    with patch('tribler_core.components.restapi.rest.debug_endpoint.get_root_state_directory',
               new=lambda: root_state_dir):
        json_response = await do_request(rest_api, f'debug/log?process={process}&max_lines={num_logs}', expected_code=200)
    logs = json_response['content'].strip().split("\n")

    # Check number of logs returned is correct
    assert len(logs) == num_logs


async def test_debug_pane_default_num_logs(rest_api, endpoint, tmp_path):
    """
    Test whether the API returns the last 100 logs when no max_lines parameter is not provided
    """
    module = 'gui'
    default_num_logs_returned = 100
    num_logs_to_write = 200

    # Log directory
    log_dir = tmp_path
    create_dummy_logs(log_dir, process=module, log_message=log_dir, num_logs=num_logs_to_write)
    endpoint.log_dir = log_dir

    json_response = await do_request(rest_api, f'debug/log?process={module}&max_lines=', expected_code=200)
    logs = json_response['content'].strip().split("\n")
    assert len(logs) == default_num_logs_returned


async def test_debug_pane_no_logs(rest_api, endpoint, tmp_path):
    """
    Test whether the API returns the default response when no log files are found.
    """
    log_dir = tmp_path
    endpoint.log_dir = log_dir

    module = 'gui'
    with patch('tribler_core.components.restapi.rest.debug_endpoint.get_root_state_directory',
               new=lambda: tmp_path / 'nondir'):
        json_response = await do_request(rest_api, f'debug/log?process={module}&max_lines=', expected_code=200)

    assert not json_response['content']
    assert json_response['max_lines'] == 0


async def test_get_profiler_state(rest_api, endpoint, core_resource_monitor):
    """
    Test getting the state of the profiler
    """
    endpoint.resource_monitor = core_resource_monitor
    json_response = await do_request(rest_api, 'debug/profiler', expected_code=200)
    assert 'state' in json_response


async def test_start_stop_profiler(rest_api, endpoint, core_resource_monitor):
    """
    Test starting and stopping the profiler using the API

    Note that we mock the start/stop profiler methods since actually starting the profiler could influence the
    tests.
    """

    endpoint.resource_monitor = core_resource_monitor

    def mocked_start_profiler():
        endpoint.resource_monitor.profiler._is_running = True

    def mocked_stop_profiler():
        endpoint.resource_monitor.profiler._is_running = False
        return 'yappi_1611750286.stats'

    endpoint.resource_monitor.profiler.start = mocked_start_profiler
    endpoint.resource_monitor.profiler.stop = mocked_stop_profiler

    await do_request(rest_api, 'debug/profiler', expected_code=200, request_type='PUT')
    assert endpoint.resource_monitor.profiler.is_running()
    await do_request(rest_api, 'debug/profiler', expected_code=200, request_type='DELETE')
    assert not endpoint.resource_monitor.profiler.is_running()

import os
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from tribler_core.restapi.base_api_test import do_request
from tribler_core.utilities.osutils import get_root_state_directory


@pytest.fixture
def enable_resource_monitor(tribler_config):
    tribler_config.set_resource_monitor_enabled(True)


@pytest.mark.asyncio
async def test_get_slots(enable_api, session):
    """
    Test whether we can get slot information from the API
    """
    session.tunnel_community = Mock()
    session.tunnel_community.random_slots = [None, None, None, 12345]
    session.tunnel_community.competing_slots = [(0, None), (12345, 12345)]
    response_json = await do_request(session, 'debug/circuits/slots', expected_code=200)
    assert len(response_json["slots"]["random"]) == 4


@pytest.mark.asyncio
async def test_get_open_files(enable_api, session, tmpdir):
    """
    Test whether the API returns open files
    """
    with open(tmpdir / "test.txt", "w"):
        response_json = await do_request(session, 'debug/open_files', expected_code=200)
        assert response_json['open_files']


@pytest.mark.asyncio
async def test_get_open_sockets(enable_api, session):
    """
    Test whether the API returns open sockets
    """
    response_json = await do_request(session, 'debug/open_sockets', expected_code=200)
    assert len(response_json['open_sockets']) >= 1


@pytest.mark.asyncio
async def test_get_threads(enable_api, session):
    """
    Test whether the API returns open threads
    """
    response_json = await do_request(session, 'debug/threads', expected_code=200)
    assert len(response_json['threads']) >= 1


@pytest.mark.asyncio
async def test_get_cpu_history(enable_api, enable_resource_monitor, session):
    """
    Test whether the API returns the cpu history
    """
    session.resource_monitor.check_resources()
    response_json = await do_request(session, 'debug/cpu/history', expected_code=200)
    assert len(response_json['cpu_history']) >= 1


@pytest.mark.asyncio
async def test_get_memory_history(enable_api, enable_resource_monitor, session):
    """
    Test whether the API returns the memory history
    """
    session.resource_monitor.check_resources()
    response_json = await do_request(session, 'debug/memory/history', expected_code=200)
    assert len(response_json['memory_history']) >= 1


@pytest.mark.skipif(sys.version_info.major > 2, reason="meliae is not Python 3 compatible")
@pytest.mark.asyncio
async def test_dump_memory(enable_api, session):
    """
    Test whether the API returns a memory dump
    """
    response = await do_request(session, 'debug/memory/dump', expected_code=200)
    assert response


@pytest.fixture(name='env_state_directory')
def fixture_env_state_directory(tribler_root_dir):
    old_state_dir = os.environ.get('TSTATEDIR', None)
    os.environ['TSTATEDIR'] = str(tribler_root_dir)

    yield tribler_root_dir

    if old_state_dir:
        os.environ['TSTATEDIR'] = old_state_dir
    else:
        os.environ.pop('TSTATEDIR', None)


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


@pytest.mark.asyncio
async def test_debug_pane_core_logs(enable_api, session):
    """
    Test whether the API returns the logs
    """
    log_dir = session.config.get_log_dir()
    process = 'core'
    test_core_log_message = "This is the core test log message"
    num_logs = 100

    create_dummy_logs(log_dir, process='core', log_message=test_core_log_message, num_logs=num_logs)

    json_response = await do_request(session, f'debug/log?process={process}&max_lines={num_logs}', expected_code=200)
    logs = json_response['content'].strip().split("\n")

    # Check number of logs returned is correct
    assert len(logs) == num_logs

    # Check if test log message is present in the logs, at least once
    log_exists = any(test_core_log_message in log for log in logs)
    assert log_exists, "Test log not found in the debug log response"


@pytest.mark.asyncio
async def test_debug_pane_core_logs_in_root_dir(env_state_directory, enable_api, session):
    """
    Test whether the API returns the logs when logs are present in the root directory.
    """

    # Tribler logs are by default set to root state directory. Here we define the
    # root state directory by updating 'TSTATEDIR' environment variable.
    log_dir = get_root_state_directory()

    process = 'core'
    num_logs = 100

    create_dummy_logs(log_dir, process='core', num_logs=num_logs)

    json_response = await do_request(session, f'debug/log?process={process}&max_lines={num_logs}', expected_code=200)
    logs = json_response['content'].strip().split("\n")

    # Check number of logs returned is correct
    assert len(logs) == num_logs


@pytest.mark.asyncio
async def test_debug_pane_default_num_logs(enable_api, session):
    """
    Test whether the API returns the last 100 logs when no max_lines parameter is not provided
    """
    module = 'gui'
    default_num_logs_returned = 100
    num_logs_to_write = 200

    # Log directory
    log_dir = session.config.get_log_dir()
    create_dummy_logs(log_dir, process=module, log_message=log_dir, num_logs=num_logs_to_write)

    json_response = await do_request(session, f'debug/log?process={module}&max_lines=', expected_code=200)
    logs = json_response['content'].strip().split("\n")
    assert len(logs) == default_num_logs_returned


@pytest.mark.asyncio
async def test_debug_pane_no_logs(env_state_directory, enable_api, session):
    """
    Test whether the API returns the default response when no log files are found.
    """
    module = 'gui'
    json_response = await do_request(session, f'debug/log?process={module}&max_lines=', expected_code=200)

    assert not json_response['content']
    assert json_response['max_lines'] == 0


@pytest.mark.asyncio
async def test_get_profiler_state(enable_api, session):
    """
    Test getting the state of the profiler
    """
    json_response = await do_request(session, 'debug/profiler', expected_code=200)
    assert 'state' in json_response


@pytest.mark.asyncio
async def test_start_stop_profiler(enable_api, enable_resource_monitor, session):
    """
    Test starting and stopping the profiler using the API

    Note that we mock the start/stop profiler methods since actually starting the profiler could influence the
    tests.
    """
    def mocked_start_profiler():
        session.resource_monitor.profiler_running = True

    def mocked_stop_profiler():
        session.resource_monitor.profiler_running = False
        return 'a'

    session.resource_monitor.start_profiler = mocked_start_profiler
    session.resource_monitor.stop_profiler = mocked_stop_profiler

    await do_request(session, 'debug/profiler', expected_code=200, request_type='PUT')
    assert session.resource_monitor.profiler_running
    await do_request(session, 'debug/profiler', expected_code=200, request_type='DELETE')
    assert not session.resource_monitor.profiler_running

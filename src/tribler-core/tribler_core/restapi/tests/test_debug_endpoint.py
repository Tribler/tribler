import os
import sys
from unittest.mock import Mock

import pytest

from tribler_core.restapi.base_api_test import do_request


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


@pytest.mark.asyncio
async def test_debug_pane_core_logs(enable_api, session):
    """
    Test whether the API returns the logs
    """

    test_core_log_message = "This is the core test log message"
    max_lines = 100

    # Directory for logs
    log_dir = session.config.get_log_dir()
    if not log_dir.exists():
        os.makedirs(log_dir)

    # Fill logging files with statements
    core_info_log_file_path = log_dir / 'tribler-core-info.log'

    # write 100 test lines which is used to test for its presence in the response
    with open(core_info_log_file_path, "w") as core_info_log_file:
        for log_index in range(max_lines):
            core_info_log_file.write("%s %d\n" % (test_core_log_message, log_index))

    json_response = await do_request(session, 'debug/log?process=core&max_lines=%d' % max_lines, expected_code=200)
    logs = json_response['content'].strip().split("\n")

    # Check number of logs returned is correct
    assert len(logs) == max_lines

    # Check if test log message is present in the logs, at least once
    log_exists = any((True for log in logs if test_core_log_message in log))
    assert log_exists, "Test log not found in the debug log response"


@pytest.mark.asyncio
async def test_debug_pane_default_num_logs(enable_api, session):
    """
    Test whether the API returns the last 100 logs when no max_lines parameter is not provided
    """
    test_core_log_message = "This is the gui test log message"
    expected_num_lines = 100

    # Log directory
    log_dir = session.config.get_log_dir()
    if not log_dir.exists():
        os.makedirs(log_dir)
    gui_info_log_file_path = log_dir / 'tribler-gui-info.log'

    # write 200 (greater than expected_num_lines) test logs in file
    with open(gui_info_log_file_path, "w") as core_info_log_file:
        for log_index in range(200):   # write more logs
            core_info_log_file.write("%s %d\n" % (test_core_log_message, log_index))

    json_response = await do_request(session, 'debug/log?process=gui&max_lines=', expected_code=200)
    logs = json_response['content'].strip().split("\n")
    assert len(logs) == expected_num_lines


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

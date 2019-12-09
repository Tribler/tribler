import os
import sys
from unittest import skipIf

from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.tools import timeout


class TestCircuitDebugEndpoint(AbstractApiTest):

    def setUpPreSession(self):
        super(TestCircuitDebugEndpoint, self).setUpPreSession()
        self.config.set_resource_monitor_enabled(True)

    @timeout(10)
    async def test_get_slots(self):
        """
        Test whether we can get slot information from the API
        """
        self.session.lm.tunnel_community = MockObject()
        self.session.lm.tunnel_community.random_slots = [None, None, None, 12345]
        self.session.lm.tunnel_community.competing_slots = [(0, None), (12345, 12345)]
        response_json = await self.do_request('debug/circuits/slots', expected_code=200)
        self.assertEqual(len(response_json["slots"]["random"]), 4)

    @timeout(10)
    async def test_get_open_files(self):
        """
        Test whether the API returns open files
        """
        response_json = await self.do_request('debug/open_files', expected_code=200)
        self.assertGreaterEqual(len(response_json['open_files']), 0)

    @timeout(10)
    async def test_get_open_sockets(self):
        """
        Test whether the API returns open sockets
        """
        response_json = await self.do_request('debug/open_sockets', expected_code=200)
        self.assertGreaterEqual(len(response_json['open_sockets']), 1)

    @timeout(10)
    async def test_get_threads(self):
        """
        Test whether the API returns open threads
        """
        response_json = await self.do_request('debug/threads', expected_code=200)
        self.assertGreaterEqual(len(response_json['threads']), 1)

    @timeout(10)
    async def test_get_cpu_history(self):
        """
        Test whether the API returns the cpu history
        """
        self.session.lm.resource_monitor.check_resources()
        response_json = await self.do_request('debug/cpu/history', expected_code=200)
        self.assertGreaterEqual(len(response_json['cpu_history']), 1)

    @skipIf(sys.version_info.major > 2, "getting memory info produces an AccessDenied error using Python 3")
    @timeout(10)
    async def test_get_memory_history(self):
        """
        Test whether the API returns the memory history
        """
        self.session.lm.resource_monitor.check_resources()
        response_json = await self.do_request('debug/memory/history', expected_code=200)
        self.assertGreaterEqual(len(response_json['memory_history']), 1)

    @skipIf(sys.version_info.major > 2, "meliae is not Python 3 compatible")
    @timeout(60)
    async def ttest_dump_memory(self):
        """
        Test whether the API returns a memory dump
        """
        response = await self.do_request('debug/memory/dump', expected_code=200)
        self.assertTrue(response)

    @timeout(10)
    async def test_debug_pane_core_logs(self):
        """
        Test whether the API returns the logs
        """

        test_core_log_message = "This is the core test log message"
        max_lines = 100

        # Directory for logs
        log_dir = self.session.config.get_log_dir()
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Fill logging files with statements
        core_info_log_file_path = os.path.join(log_dir, 'tribler-core-info.log')

        # write 100 test lines which is used to test for its presence in the response
        with open(core_info_log_file_path, "w") as core_info_log_file:
            for log_index in range(max_lines):
                core_info_log_file.write("%s %d\n" % (test_core_log_message, log_index))

        json_response = await self.do_request('debug/log?process=core&max_lines=%d' % max_lines, expected_code=200)
        logs = json_response['content'].strip().split("\n")

        # Check number of logs returned is correct
        self.assertEqual(len(logs), max_lines)

        # Check if test log message is present in the logs, at least once
        log_exists = any((True for log in logs if test_core_log_message in log))
        self.assertTrue(log_exists, "Test log not found in the debug log response")


    @timeout(10)
    async def test_debug_pane_default_num_logs(self):
        """
        Test whether the API returns the last 100 logs when no max_lines parameter is not provided
        """
        test_core_log_message = "This is the gui test log message"
        expected_num_lines = 100

        # Log directory
        log_dir = self.session.config.get_log_dir()
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        gui_info_log_file_path = os.path.join(log_dir, 'tribler-gui-info.log')

        # write 200 (greater than expected_num_lines) test logs in file
        with open(gui_info_log_file_path, "w") as core_info_log_file:
            for log_index in range(200):   # write more logs
                core_info_log_file.write("%s %d\n" % (test_core_log_message, log_index))

        json_response = await self.do_request('debug/log?process=gui&max_lines=', expected_code=200)
        logs = json_response['content'].strip().split("\n")
        self.assertEqual(len(logs), expected_num_lines)

    @timeout(10)
    async def test_get_profiler_state(self):
        """
        Test getting the state of the profiler
        """
        json_response = await self.do_request('debug/profiler', expected_code=200)
        self.assertIn('state', json_response)

    @timeout(10)
    async def test_start_stop_profiler(self):
        """
        Test starting and stopping the profiler using the API

        Note that we mock the start/stop profiler methods since actually starting the profiler could influence the
        tests.
        """
        def mocked_start_profiler():
            self.session.lm.resource_monitor.profiler_running = True

        def mocked_stop_profiler():
            self.session.lm.resource_monitor.profiler_running = False
            return 'a'

        self.session.lm.resource_monitor.start_profiler = mocked_start_profiler
        self.session.lm.resource_monitor.stop_profiler = mocked_stop_profiler

        await self.do_request('debug/profiler', expected_code=200, request_type='PUT')
        self.assertTrue(self.session.lm.resource_monitor.profiler_running)
        await self.do_request('debug/profiler', expected_code=200, request_type='DELETE')
        self.assertFalse(self.session.lm.resource_monitor.profiler_running)

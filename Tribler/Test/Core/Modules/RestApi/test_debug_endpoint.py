import os

import Tribler.Core.Utilities.json_util as json
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.twisted_thread import deferred
from Tribler.pyipv8.ipv8.messaging.anonymization.tunnel import CIRCUIT_TYPE_DATA


class TestCircuitDebugEndpoint(AbstractApiTest):

    def setUpPreSession(self):
        super(TestCircuitDebugEndpoint, self).setUpPreSession()
        self.config.set_ipv8_enabled(True)
        self.config.set_tunnel_community_enabled(True)
        self.config.set_trustchain_enabled(False)
        self.config.set_tunnel_community_socks5_listen_ports(self.get_socks5_ports())

    @deferred(timeout=10)
    def test_get_circuit_no_community(self):
        """
        Testing whether the API returns error 404 if no tunnel community is loaded
        """
        self.session.lm.tunnel_community = None
        return self.do_request('debug/circuits', expected_code=404)

    @deferred(timeout=10)
    def test_get_circuits(self):
        """
        Testing whether the API returns the correct circuits
        """
        mock_hop = MockObject()
        mock_hop.host = 'somewhere'
        mock_hop.port = 4242

        mock_circuit = MockObject()
        mock_circuit.state = 'TESTSTATE'
        mock_circuit.goal_hops = 42
        mock_circuit.bytes_up = 200
        mock_circuit.bytes_down = 400
        mock_circuit.creation_time = 1234
        mock_circuit.hops = [mock_hop]
        mock_circuit.sock_addr = ("1.1.1.1", 1234)
        mock_circuit.circuit_id = 1234
        mock_circuit.ctype = CIRCUIT_TYPE_DATA
        mock_circuit.destroy = lambda: None

        self.session.lm.tunnel_community.circuits = {1234: mock_circuit}

        def verify_response(response):
            response_json = json.loads(response)
            self.assertEqual(len(response_json['circuits']), 1)
            self.assertEqual(response_json['circuits'][0]['state'], 'TESTSTATE')
            self.assertEqual(response_json['circuits'][0]['bytes_up'], 200)
            self.assertEqual(response_json['circuits'][0]['bytes_down'], 400)
            self.assertEqual(len(response_json['circuits'][0]['hops']), 1)
            self.assertEqual(response_json['circuits'][0]['hops'][0]['host'], 'somewhere:4242')

        self.should_check_equality = False
        return self.do_request('debug/circuits', expected_code=200).addCallback(verify_response)

    @deferred(timeout=10)
    def test_get_open_files(self):
        """
        Test whether the API returns open files
        """
        def verify_response(response):
            response_json = json.loads(response)
            self.assertGreaterEqual(len(response_json['open_files']), 1)

        self.should_check_equality = False
        return self.do_request('debug/open_files', expected_code=200).addCallback(verify_response)

    @deferred(timeout=10)
    def test_get_open_sockets(self):
        """
        Test whether the API returns open sockets
        """

        def verify_response(response):
            response_json = json.loads(response)
            self.assertGreaterEqual(len(response_json['open_sockets']), 1)

        self.should_check_equality = False
        return self.do_request('debug/open_sockets', expected_code=200).addCallback(verify_response)

    @deferred(timeout=10)
    def test_get_threads(self):
        """
        Test whether the API returns open threads
        """

        def verify_response(response):
            response_json = json.loads(response)
            self.assertGreaterEqual(len(response_json['threads']), 1)

        self.should_check_equality = False
        return self.do_request('debug/threads', expected_code=200).addCallback(verify_response)

    @deferred(timeout=10)
    def test_get_cpu_history(self):
        """
        Test whether the API returns the cpu history
        """

        def verify_response(response):
            response_json = json.loads(response)
            self.assertGreaterEqual(len(response_json['cpu_history']), 1)

        self.session.lm.resource_monitor.check_resources()
        self.should_check_equality = False
        return self.do_request('debug/cpu/history', expected_code=200).addCallback(verify_response)

    @deferred(timeout=10)
    def test_get_memory_history(self):
        """
        Test whether the API returns the memory history
        """

        def verify_response(response):
            response_json = json.loads(response)
            self.assertGreaterEqual(len(response_json['memory_history']), 1)

        self.session.lm.resource_monitor.check_resources()
        self.should_check_equality = False
        return self.do_request('debug/memory/history', expected_code=200).addCallback(verify_response)

    @deferred(timeout=60)
    def test_dump_memory(self):
        """
        Test whether the API returns a memory dump
        """

        def verify_response(response):
            self.assertTrue(response)

        self.should_check_equality = False
        return self.do_request('debug/memory/dump', expected_code=200).addCallback(verify_response)

    @deferred(timeout=10)
    def test_debug_pane_core_logs(self):
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
            for log_index in xrange(max_lines):
                core_info_log_file.write("%s %d\n" % (test_core_log_message, log_index))

        def verify_log_exists(response):
            json_response = json.loads(response)
            logs = json_response['content'].strip().split("\n")

            # Check number of logs returned is correct
            self.assertEqual(len(logs), max_lines)

            # Check if test log message is present in the logs, at least once
            log_exists = any((True for log in logs if test_core_log_message in log))
            self.assertTrue(log_exists, "Test log not found in the debug log response")

        self.should_check_equality = False
        return self.do_request('debug/log?process=core&max_lines=%d' % max_lines, expected_code=200)\
            .addCallback(verify_log_exists)\


    @deferred(timeout=10)
    def test_debug_pane_default_num_logs(self):
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
            for log_index in xrange(200):   # write more logs
                core_info_log_file.write("%s %d\n" % (test_core_log_message, log_index))

        # Check number of logs returned is as expected
        def verify_max_logs_returned(response):
            json_response = json.loads(response)
            logs = json_response['content'].strip().split("\n")
            self.assertEqual(len(logs), expected_num_lines)

        self.should_check_equality = False
        return self.do_request('debug/log?process=gui&max_lines=', expected_code=200)\
            .addCallback(verify_max_logs_returned)

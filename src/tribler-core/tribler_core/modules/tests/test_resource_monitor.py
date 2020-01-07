import os
import sys
import time
from collections import namedtuple

from tribler_common.simpledefs import NTFY

from tribler_core.modules.resource_monitor import ResourceMonitor
from tribler_core.tests.tools.base_test import MockObject, TriblerCoreTest
from tribler_core.utilities import path_util


class TestResourceMonitor(TriblerCoreTest):

    async def setUp(self):
        await super(TestResourceMonitor, self).setUp()

        mock_session = MockObject()
        mock_session.config = MockObject()
        mock_session.config.get_resource_monitor_history_size = lambda: 1
        mock_session.config.get_resource_monitor_poll_interval = lambda: 20
        mock_session.config.get_state_dir = lambda: path_util.Path(".")
        mock_session.config.get_log_dir = lambda: path_util.Path("logs")
        mock_session.config.get_resource_monitor_enabled = lambda: False
        self.resource_monitor = ResourceMonitor(mock_session)
        self.resource_monitor.session.notifier = MockObject()
        self.resource_monitor.session.notifier.notify = lambda subject, changeType, obj_id, *args: None

    def test_check_resources(self):
        """
        Test the resource monitor check
        """
        self.resource_monitor.write_resource_logs = lambda _: None
        self.resource_monitor.check_resources()
        self.assertEqual(len(self.resource_monitor.cpu_data), 1)
        # Getting memory info produces an AccessDenied error using Python 3
        if sys.version_info.major < 3:
            self.assertEqual(len(self.resource_monitor.memory_data), 1)
        self.assertEqual(len(self.resource_monitor.disk_usage_data), 1)

        # Check that we remove old history
        self.resource_monitor.history_size = 1
        self.resource_monitor.check_resources()
        self.assertEqual(len(self.resource_monitor.cpu_data), 1)
        if sys.version_info.major < 3:
            self.assertEqual(len(self.resource_monitor.memory_data), 1)
        self.assertEqual(len(self.resource_monitor.disk_usage_data), 1)

    def test_get_history_dicts(self):
        """
        Test the CPU/memory/disk usage history dictionary of a resource monitor
        """
        self.resource_monitor.check_resources()
        cpu_dict = self.resource_monitor.get_cpu_history_dict()
        self.assertIsInstance(cpu_dict, list)

        memory_dict = self.resource_monitor.get_memory_history_dict()
        self.assertIsInstance(memory_dict, list)

        disk_usage_history = self.resource_monitor.get_disk_usage()
        self.assertIsInstance(disk_usage_history, list)

    def test_memory_full_error(self):
        """
        Test if check resources completes when memory_full_info fails
        """
        self.resource_monitor.process.cpu_percent = lambda interval: None

        def fail_with_error():
            raise MemoryError()
        self.resource_monitor.process.memory_full_info = fail_with_error

        self.resource_monitor.check_resources()

        self.assertListEqual([], self.resource_monitor.memory_data)

    def test_low_disk_notification(self):
        """
        Test low disk space notification
        """
        def fake_get_free_disk_space():
            disk = {"total": 318271800, "used": 312005050, "free": 6266750, "percent": 98.0}
            return namedtuple('sdiskusage', disk.keys())(*disk.values())

        def on_notify(subject, *args):
            self.assertEqual(subject, NTFY.LOW_SPACE)

        self.resource_monitor.get_free_disk_space = fake_get_free_disk_space
        self.resource_monitor.session.notifier.notify = on_notify
        self.resource_monitor.check_resources()

    def test_profiler(self):
        """
        Test the profiler functionality
        """
        self.resource_monitor.start_profiler()
        self.assertTrue(self.resource_monitor.profiler_running)
        self.assertRaises(RuntimeError, self.resource_monitor.start_profiler)

        self.resource_monitor.stop_profiler()
        self.assertFalse(self.resource_monitor.profiler_running)
        self.assertRaises(RuntimeError, self.resource_monitor.stop_profiler)

    def test_resource_log(self):
        """
        Test resource log file is created when enabled.
        """
        self.resource_monitor.set_resource_log_enabled(True)
        self.resource_monitor.check_resources()
        self.assertTrue(self.resource_monitor.resource_log_file.exists())

    def test_write_resource_log(self):
        """
        Test no data is written to file and no exception raised when resource data (cpu & memory) is empty which
        happens at startup.
        """
        # Empty resource log to check later if something was written to the log or not.
        with open(self.resource_monitor.resource_log_file, 'w'): pass

        self.resource_monitor.memory_data = []
        self.resource_monitor.cpu_data = []

        # Try writing the log
        self.resource_monitor.write_resource_logs(time.time())

        # Nothing should be written since memory and cpu data was not available
        self.assertTrue(os.stat(self.resource_monitor.resource_log_file).st_size == 0)

    def test_enable_resource_log(self):
        self.resource_monitor.set_resource_log_enabled(True)
        self.assertTrue(self.resource_monitor.is_resource_log_enabled())

    def test_reset_resource_log(self):
        self.resource_monitor.reset_resource_logs()
        self.assertFalse(self.resource_monitor.resource_log_file.exists())

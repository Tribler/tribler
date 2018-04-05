from collections import namedtuple

from Tribler.Core.Modules.resource_monitor import ResourceMonitor
from Tribler.Core.simpledefs import SIGNAL_RESOURCE_CHECK, SIGNAL_LOW_SPACE
from Tribler.Test.Core.base_test import TriblerCoreTest, MockObject


class TestResourceMonitor(TriblerCoreTest):

    def setUp(self, annotate=True):
        super(TestResourceMonitor, self).setUp(annotate=annotate)

        mock_session = MockObject()
        mock_session.config = MockObject()
        mock_session.config.get_resource_monitor_history_size = lambda: 1
        mock_session.config.get_resource_monitor_poll_interval = lambda: 20
        mock_session.config.get_state_dir = lambda: "."
        self.resource_monitor = ResourceMonitor(mock_session)
        self.resource_monitor.session.notifier = MockObject()
        self.resource_monitor.session.notifier.notify = lambda subject, changeType, obj_id, *args: None

    def test_check_resources(self):
        """
        Test the resource monitor check
        """
        self.resource_monitor.check_resources()
        self.assertEqual(len(self.resource_monitor.cpu_data), 1)
        self.assertEqual(len(self.resource_monitor.memory_data), 1)
        self.assertEqual(len(self.resource_monitor.disk_usage_data), 1)

        # Check that we remove old history
        self.resource_monitor.history_size = 1
        self.resource_monitor.check_resources()
        self.assertEqual(len(self.resource_monitor.cpu_data), 1)
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

        def on_notify(subject, changeType, obj_id, *args):
            self.assertEquals(subject, SIGNAL_RESOURCE_CHECK)
            self.assertEquals(changeType, SIGNAL_LOW_SPACE)

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

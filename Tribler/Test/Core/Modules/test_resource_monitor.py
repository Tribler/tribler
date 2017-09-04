from Tribler.Core.Modules.resource_monitor import ResourceMonitor
from Tribler.Test.Core.base_test import TriblerCoreTest, MockObject


class TestResourceMonitor(TriblerCoreTest):

    def setUp(self, annotate=True):
        super(TestResourceMonitor, self).setUp(annotate=annotate)

        mock_session = MockObject()
        mock_session.config = MockObject()
        mock_session.config.get_resource_monitor_history_size = lambda: 1
        mock_session.config.get_resource_monitor_poll_interval = lambda: 20
        self.resource_monitor = ResourceMonitor(mock_session)

    def test_check_resources(self):
        """
        Test the resource monitor check
        """
        self.resource_monitor.check_resources()
        self.assertEqual(len(self.resource_monitor.cpu_data), 1)
        self.assertEqual(len(self.resource_monitor.memory_data), 1)

        # Check that we remove old history
        self.resource_monitor.history_size = 1
        self.resource_monitor.check_resources()
        self.assertEqual(len(self.resource_monitor.cpu_data), 1)
        self.assertEqual(len(self.resource_monitor.memory_data), 1)

    def test_get_history_dicts(self):
        """
        Test the CPU/memory history dictionary of a resource monitor
        """
        self.resource_monitor.check_resources()
        cpu_dict = self.resource_monitor.get_cpu_history_dict()
        self.assertIsInstance(cpu_dict, list)

        memory_dict = self.resource_monitor.get_memory_history_dict()
        self.assertIsInstance(memory_dict, list)

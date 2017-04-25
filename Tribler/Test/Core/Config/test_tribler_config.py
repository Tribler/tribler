from Tribler.Core.Config.tribler_config import TriblerConfig
from Tribler.Test.Core.base_test import TriblerCoreTest


class TestTriblerConfig(TriblerCoreTest):
    """
    This class contains tests for the tribler configuration file.
    """

    def setUp(self, annotate=True):
        super(TestTriblerConfig, self).setUp(annotate=annotate)

        self.tribler_conf = TriblerConfig()
        self.assertIsNotNone(self.tribler_conf)
        self.assertEqual(self.tribler_conf.config['user_download_states'], {})

    def test_set_family_filter(self):
        self.tribler_conf.set_family_filter_enabled(False)
        self.assertFalse(self.tribler_conf.get_family_filter_enabled())

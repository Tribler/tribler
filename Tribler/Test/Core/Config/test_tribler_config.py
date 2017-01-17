from Tribler.Core.Config.tribler_config import TriblerConfig
from Tribler.Test.Core.base_test import TriblerCoreTest, MockObject


class TestTriblerConfig(TriblerCoreTest):
    """
    This class contains tests for the tribler configuration file.
    """

    def setUp(self, annotate=True):
        super(TestTriblerConfig, self).setUp(annotate=annotate)

        self.mock_session = MockObject()
        self.mock_session.get_state_dir = lambda: self.session_base_dir

        self.tribler_conf = TriblerConfig(self.mock_session)
        self.assertIsNotNone(self.tribler_conf)
        self.assertEqual(self.tribler_conf.config['user_download_states'], {})

    def test_set_family_filter(self):
        self.tribler_conf.set_family_filter_enabled(False)
        self.assertFalse(self.tribler_conf.get_family_filter_enabled())

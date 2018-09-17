import os
import pickle

from Tribler.Core.Config.tribler_config import TriblerConfig, FILENAME as TRIBLER_CONFIG_FILENAME
from Tribler.Core.Upgrade.pickle_converter import PickleConverter
from Tribler.Test.Core.base_test import TriblerCoreTest, MockObject


class TestPickleConverter(TriblerCoreTest):
    """
    This file contains tests for the converter that converts older pickle files to the .state format.
    """

    def setUp(self):
        super(TestPickleConverter, self).setUp()

        self.mock_session = MockObject()
        self.mock_session.get_downloads_pstate_dir = lambda: self.session_base_dir
        self.mock_session.config = TriblerConfig()
        self.mock_session.config.get_state_dir = lambda: self.session_base_dir

    def write_pickle_file(self, content, filename):
        pickle_filepath = os.path.join(self.session_base_dir, filename)
        pickle.dump(content, open(pickle_filepath, "wb"))

    def test_convert_session_config(self):
        old_pickle_dict = {"state_dir": "/", "mainline_dht_port": 1337, "torrent_checking": "false",
                           "torrent_collecting": "true", "libtorrent": False, "dispersy_port": 1337,
                           "minport": 1234}
        self.write_pickle_file(old_pickle_dict, "sessconfig.pickle")

        PickleConverter(self.mock_session).convert_session_config()

        self.assertTrue(os.path.exists(os.path.join(self.session_base_dir, TRIBLER_CONFIG_FILENAME)))
        self.assertFalse(os.path.exists(os.path.join(self.session_base_dir, "sessconfig.pickle")))

        # Check the content of the config file
        config = TriblerConfig.load(config_path=os.path.join(self.session_base_dir, TRIBLER_CONFIG_FILENAME))
        self.assertEqual(config.get_state_dir(), '/')
        self.assertEqual(config.get_mainline_dht_port(), 1337)
        self.assertEqual(config.get_torrent_checking_enabled(), False)
        self.assertEqual(config.get_torrent_collecting_enabled(), True)
        self.assertFalse(config.get_libtorrent_enabled())
        self.assertEqual(config.get_dispersy_port(), 1337)
        self.assertEqual(config.get_libtorrent_port(), 1234)

    def test_convert_download_checkpoints(self):
        with open(os.path.join(self.session_base_dir, 'corrupt.pickle'), 'wb') as corrupt_file:
            corrupt_file.write("This is not a pickle file!")

        old_pickle_dict = {"dlconfig": {"saveas": "dunno", "abc": "def"}, "engineresumedata": "test",
                           "dlstate": "test", "metainfo": "none"}
        self.write_pickle_file(old_pickle_dict, "download.pickle")

        PickleConverter(self.mock_session).convert_download_checkpoints()

        self.assertTrue(os.path.exists(os.path.join(self.session_base_dir, 'download.state')))
        self.assertFalse(os.path.exists(os.path.join(self.session_base_dir, 'corrupt.pickle')))

    def test_convert_main_config(self):
        pickle_dict = {"download_state": {"abc": "stop"}}
        self.write_pickle_file(pickle_dict, "user_download_choice.pickle")

        PickleConverter(self.mock_session).convert_main_config()

        self.assertFalse(os.path.exists(os.path.join(self.session_base_dir, "user_download_choice.pickle")))
        self.assertTrue(os.path.exists(os.path.join(self.session_base_dir, TRIBLER_CONFIG_FILENAME)))

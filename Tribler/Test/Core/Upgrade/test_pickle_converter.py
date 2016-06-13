import os
import pickle
from Tribler.Core.DownloadConfig import get_default_dscfg_filename
from Tribler.Core.SessionConfig import SessionConfigInterface
from Tribler.Core.Upgrade.pickle_converter import PickleConverter
from Tribler.Test.Core.base_test import TriblerCoreTest, MockObject


class TestPickleConverter(TriblerCoreTest):
    """
    This file contains tests for the converter that converts older pickle files to the .state format.
    """

    def setUp(self, annotate=True):
        super(TestPickleConverter, self).setUp(annotate=annotate)

        self.mock_session = MockObject()
        self.mock_session.get_state_dir = lambda: self.session_base_dir
        self.mock_session.get_downloads_pstate_dir = lambda: self.session_base_dir

    def write_pickle_file(self, content, filename):
        pickle_filepath = os.path.join(self.session_base_dir, filename)
        pickle.dump(content, open(pickle_filepath, "wb"))

    def test_convert_session_config(self):
        old_pickle_dict = {"state_dir": "/", "mainline_dht_port": 1337, "torrent_checking": "maybe",
                           "torrent_collecting": "maybe", "libtorrent": 1337, "dispersy_port": 1337}
        self.write_pickle_file(old_pickle_dict, "sessconfig.pickle")

        PickleConverter(self.mock_session).convert_session_config()

        self.assertTrue(os.path.exists(SessionConfigInterface.get_default_config_filename(self.session_base_dir)))
        self.assertFalse(os.path.exists(os.path.join(self.session_base_dir, "sessconfig.pickle")))

    def test_convert_default_download_config(self):
        old_pickle_dict = {"saveas": "dunno", "max_upload_rate": 33, "unrelatedkey": "test"}
        self.write_pickle_file(old_pickle_dict, "dlconfig.pickle")

        PickleConverter(self.mock_session).convert_default_download_config()

        self.assertTrue(os.path.exists(get_default_dscfg_filename(self.session_base_dir)))

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

        conf_filepath = os.path.join(self.session_base_dir, 'abc.conf')
        with open(conf_filepath, 'wb') as conf_file:
            conf_file.write("[ABC]")

        gui_filepath = os.path.join(self.session_base_dir, 'gui_settings')
        with open(gui_filepath, 'wb') as gui_settings_file:
            gui_settings_file.write("a=b\nc=d")

        history_filepath = os.path.join(self.session_base_dir, 'recent_download_history')
        with open(history_filepath, 'wb') as history_file:
            history_file.write("a=b\nc=d\ne=\n")

        PickleConverter(self.mock_session).convert_main_config()

        self.assertFalse(os.path.exists(os.path.join(self.session_base_dir, "user_download_choice.pickle")))
        self.assertFalse(os.path.exists(conf_filepath))
        self.assertFalse(os.path.exists(gui_filepath))
        self.assertFalse(os.path.exists(history_filepath))
        self.assertTrue(os.path.exists(os.path.join(self.session_base_dir, "tribler.conf")))

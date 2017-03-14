import os

from nose.tools import raises

from Tribler.Core.SessionConfig import SessionConfigInterface, SessionStartupConfig
from Tribler.Core.Utilities.configparser import CallbackConfigParser
from Tribler.Test.Core.base_test import TriblerCoreTest


class TestSessionConfig(TriblerCoreTest):

    FILE_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    CONFIG_FILES_DIR = os.path.abspath(os.path.join(FILE_DIR, u"data/config_files/"))

    def test_session_config_init(self):
        sessconf = CallbackConfigParser()
        sessconf.add_section('mainline_dht')
        sessconf.set('mainline_dht', 'mainline_dht_port', 1234)
        sci = SessionConfigInterface(sessconf)
        self.assertTrue(sci)

        self.assertIsInstance(sci.get_listen_port(), int)
        self.assertIsInstance(sci.get_mainline_dht_listen_port(), int)
        self.assertIsInstance(sci.get_default_state_dir(), unicode)

        sci.set_state_dir(self.session_base_dir)
        self.assertEqual(sci.get_state_dir(), self.session_base_dir)

        self.assertIsInstance(sci.get_install_dir(), (unicode, str))
        self.assertIsInstance(sci.get_permid_keypair_filename(), str)

        sci.set_listen_port(1337)
        self.assertEqual(sci.sessconfig.get('general', 'minport'), 1337)
        self.assertEqual(sci.sessconfig.get('general', 'maxport'), 1337)

        self.assertIsInstance(sci.get_tunnel_community_socks5_listen_ports(), list)
        self.assertFalse(sci.get_tunnel_community_exitnode_enabled())

        sci.set_tunnel_community_enabled(False)
        self.assertFalse(sci.get_tunnel_community_enabled())

        sci.set_megacache(False)
        self.assertFalse(sci.get_megacache())

        sci.set_libtorrent(False)
        self.assertFalse(sci.get_libtorrent())

        sci.set_libtorrent_max_conn_download(5)
        self.assertEqual(sci.get_libtorrent_max_conn_download(), 5)

        sci.set_libtorrent_proxy_settings(3, ("127.0.0.1", 1337), ("foo", "bar"))
        self.assertEqual(sci.get_libtorrent_proxy_settings(), (3, ("127.0.0.1", 1337), ("foo", "bar")))

        sci.set_anon_proxy_settings(5, ("127.0.0.1", 1337), ("foo", "bar"))
        self.assertEqual(sci.get_anon_proxy_settings(), (5, ("127.0.0.1", 1337), ("foo", "bar")))

        sci.set_libtorrent_utp(False)
        self.assertFalse(sci.get_libtorrent_utp())

        sci.set_torrent_store(False)
        self.assertFalse(sci.get_torrent_store())

        sci.set_torrent_store_dir(self.session_base_dir)
        self.assertEqual(sci.get_torrent_store_dir(), self.session_base_dir)

        sci.set_torrent_collecting(False)
        self.assertFalse(sci.get_torrent_collecting())

        sci.set_dht_torrent_collecting(False)
        self.assertFalse(sci.get_dht_torrent_collecting())

        sci.set_torrent_collecting_max_torrents(1337)
        self.assertEqual(sci.get_torrent_collecting_max_torrents(), 1337)

        sci.set_torrent_collecting_dir(self.session_base_dir)
        self.assertEqual(sci.get_torrent_collecting_dir(), self.session_base_dir)

        sci.set_torrent_checking(False)
        self.assertFalse(sci.get_torrent_checking())

        sci.set_stop_collecting_threshold(1337)
        self.assertEqual(sci.get_stop_collecting_threshold(), 1337)

        sci.set_nickname("foobar")
        self.assertEqual(sci.get_nickname(), "foobar")

        self.assertEqual(sci.get_mugshot(), (None, None))
        sci.set_mugshot("myimage", mime="image/png")
        self.assertEqual(sci.get_mugshot(), ("image/png", "myimage"))

        sci.set_peer_icon_path(self.session_base_dir)
        self.assertEqual(sci.get_peer_icon_path(), self.session_base_dir)

        sci.set_video_analyser_path(self.session_base_dir)
        self.assertEqual(sci.get_video_analyser_path(), self.session_base_dir)

        sci.set_mainline_dht(False)
        self.assertFalse(sci.get_mainline_dht())

        sci.set_mainline_dht_listen_port(1337)
        self.assertEqual(sci.sessconfig.get('mainline_dht', 'mainline_dht_port'), 1337)

        sci.set_multicast_local_peer_discovery(False)
        self.assertFalse(sci.get_multicast_local_peer_discovery())

        sci.set_dispersy(False)
        self.assertFalse(sci.get_dispersy())

        sci.set_dispersy_port(1337)
        self.assertIsInstance(sci.get_dispersy_port(), int)
        self.assertEqual(sci.sessconfig.get('dispersy', 'dispersy_port'), 1337)

        sci.set_videoserver_enabled(False)
        self.assertFalse(sci.get_videoserver_enabled())

        sci.set_videoplayer_path(self.session_base_dir)
        self.assertEqual(sci.get_videoplayer_path(), self.session_base_dir)

        sci.set_videoserver_port(1337)
        self.assertIsInstance(sci.get_videoserver_port(), int)
        self.assertEqual(sci.sessconfig.get('video', 'port'), 1337)

        sci.set_preferred_playback_mode(5)
        self.assertEqual(sci.get_preferred_playback_mode(), 5)

        sci.set_enable_torrent_search(False)
        self.assertFalse(sci.get_enable_torrent_search())

        sci.set_enable_channel_search(False)
        self.assertFalse(sci.get_enable_channel_search())

        sci.set_enable_metadata(False)
        self.assertFalse(sci.get_enable_metadata())

        sci.set_metadata_store_dir(self.session_base_dir)
        self.assertEqual(sci.get_metadata_store_dir(), self.session_base_dir)

        sci.set_channel_community_enabled(False)
        self.assertFalse(sci.get_channel_community_enabled())

        sci.set_preview_channel_community_enabled(False)
        self.assertFalse(sci.get_preview_channel_community_enabled())

        sci.set_upgrader_enabled(False)
        self.assertFalse(sci.get_upgrader_enabled())

        sci.set_http_api_enabled(True)
        self.assertTrue(sci.get_http_api_enabled())

        sci.set_http_api_port(1337)
        self.assertEqual(sci.sessconfig.get('http_api', 'port'), 1337)

        self.assertIsInstance(sci.get_default_config_filename(self.session_base_dir), str)

    def test_startup_session_save_load(self):
        sci = SessionStartupConfig(CallbackConfigParser())
        file_path = os.path.join(self.session_base_dir, "startupconfig.conf")
        sci.save(file_path)

        sci.load(file_path)

    def test_startup_session_invalid_port(self):
        sci = SessionConfigInterface()
        sci.set_mainline_dht_listen_port("abcd")
        self.assertTrue(isinstance(sci.get_mainline_dht_listen_port(), int))

    @raises(IOError)
    def test_startup_session_load_corrupt(self):
        sci = SessionStartupConfig()
        sci.load(os.path.join(self.CONFIG_FILES_DIR, "corrupt_session_config.conf"))

    def test_startup_session_load_no_filename(self):
        sci = SessionStartupConfig()
        sci.load()
        self.assertTrue(sci)

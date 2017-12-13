import os

from configobj import ConfigObj

from Tribler.Core.Config.tribler_config import TriblerConfig, CONFIG_SPEC_PATH, FILENAME
from Tribler.Test.Core.base_test import TriblerCoreTest


class TestTriblerConfig(TriblerCoreTest):
    """
    This class contains tests for the tribler configuration file.
    """

    def setUp(self, annotate=True):
        """
        Create a new TriblerConfig instance
        """
        super(TestTriblerConfig, self).setUp(annotate=annotate)

        self.tribler_config = TriblerConfig()
        self.assertIsNotNone(self.tribler_config)

    def test_init_with_config(self):
        """
        When creating a new instance with a configobject provided, the given options
        must be contained in the resulting instance.
        """
        configdict = ConfigObj({"a": 1, "b": "2"}, configspec=CONFIG_SPEC_PATH)
        self.tribler_config = TriblerConfig(configdict)

        self.tribler_config.validate()
        for key, value in configdict.items():
            self.assertEqual(self.tribler_config.config[key], value)

    def test_init_without_config(self):
        """
        A newly created TriblerConfig is valid.
        """
        self.tribler_config.validate()

    def test_write_load(self):
        """
        When writing and reading a config the options should remain the same.
        """
        port = 4444
        self.tribler_config.set_anon_listen_port(port)
        self.tribler_config.write()
        path = os.path.join(self.tribler_config.get_state_dir(), FILENAME)
        read_config = TriblerConfig.load(path)

        read_config.validate()
        self.assertEqual(read_config.get_anon_listen_port(), port)

    def test_load(self):
        os.path.isdir(self.tribler_config.get_state_dir())

    def test_libtorrent_proxy_settings(self):
        """
        Setting and getting of libtorrent proxy settings.
        """
        proxy_type, server, auth = 3, ("33.33.33.33", 22), 1
        self.tribler_config.set_libtorrent_proxy_settings(proxy_type, server, auth)

        self.assertEqual(self.tribler_config.get_libtorrent_proxy_settings()[0], proxy_type)
        self.assertEqual(self.tribler_config.get_libtorrent_proxy_settings()[1], server)
        self.assertEqual(self.tribler_config.get_libtorrent_proxy_settings()[2], auth)

        # if the proxy type doesn't support authentication, auth setting should be saved as None
        proxy_type = 1
        self.tribler_config.set_libtorrent_proxy_settings(proxy_type, server, auth)
        self.assertEqual(self.tribler_config.get_libtorrent_proxy_settings()[0], proxy_type)
        self.assertEqual(self.tribler_config.get_libtorrent_proxy_settings()[1], server)
        self.assertIsNone(self.tribler_config.get_libtorrent_proxy_settings()[2])

    def test_anon_proxy_settings(self):
        proxy_type, server, auth = 3, ("33.33.33.33", [2222, 2223, 4443, 58848]), 1
        self.tribler_config.set_anon_proxy_settings(proxy_type, server, auth)

        self.assertEqual(self.tribler_config.get_anon_proxy_settings()[0], proxy_type)
        self.assertEqual(self.tribler_config.get_anon_proxy_settings()[1], server)
        self.assertEqual(self.tribler_config.get_anon_proxy_settings()[2], auth)

        proxy_type = 1
        self.tribler_config.set_anon_proxy_settings(proxy_type, server, auth)

        self.assertEqual(self.tribler_config.get_anon_proxy_settings()[0], proxy_type)
        self.assertEqual(self.tribler_config.get_anon_proxy_settings()[1], server)
        self.assertIsNone(self.tribler_config.get_anon_proxy_settings()[2])

    def test_tunnel_community_socks5_listen_ports(self):
        ports = [5554, 9949, 9588, 35555, 84899]
        self.tribler_config.set_tunnel_community_socks5_listen_ports(ports)
        self.assertListEqual(self.tribler_config.get_tunnel_community_socks5_listen_ports(), ports)

    def test_credit_mining_sources(self):
        source_list = "listitem"
        self.tribler_config.set_credit_mining_sources(source_list)
        self.assertEqual(self.tribler_config.get_credit_mining_sources(), source_list)

    def test_get_set_methods_general(self):
        """
        Check whether general get and set methods are working as expected.
        """
        self.tribler_config.set_family_filter_enabled(False)
        self.assertEqual(self.tribler_config.get_family_filter_enabled(), False)

        self.tribler_config.set_state_dir(None)
        self.assertEqual(self.tribler_config.get_state_dir(), self.tribler_config.get_default_state_dir())
        self.tribler_config.set_state_dir("TEST")
        self.assertEqual(self.tribler_config.get_state_dir(), "TEST")

        self.tribler_config.set_permid_keypair_filename(None)
        self.assertEqual(self.tribler_config.get_permid_keypair_filename(), os.path.join("TEST", "ec.pem"))
        self.tribler_config.set_permid_keypair_filename("TEST")
        self.assertEqual(self.tribler_config.get_permid_keypair_filename(), "TEST")

        self.tribler_config.set_trustchain_permid_keypair_filename(None)
        self.assertEqual(self.tribler_config.get_trustchain_permid_keypair_filename(),
                         os.path.join("TEST", "ec_multichain.pem"))
        self.tribler_config.set_trustchain_permid_keypair_filename("TEST")
        self.assertEqual(self.tribler_config.get_trustchain_permid_keypair_filename(), "TEST")

        self.tribler_config.set_megacache_enabled(True)
        self.assertEqual(self.tribler_config.get_megacache_enabled(), True)

        self.tribler_config.set_video_analyser_path(True)
        self.assertEqual(self.tribler_config.get_video_analyser_path(), True)

    def test_get_set_methods_torrent_checking(self):
        """
        Check whether torrent checking get and set methods are working as expected.
        """
        self.tribler_config.set_torrent_checking_enabled(True)
        self.assertEqual(self.tribler_config.get_torrent_checking_enabled(), True)

    def test_get_set_methods_http_api(self):
        """
        Check whether http api get and set methods are working as expected.
        """
        self.tribler_config.set_http_api_enabled(True)
        self.assertEqual(self.tribler_config.get_http_api_enabled(), True)
        self.tribler_config.set_http_api_port(True)
        self.assertEqual(self.tribler_config.get_http_api_port(), True)

    def test_get_set_methods_dispersy(self):
        """
        Check whether dispersy get and set methods are working as expected.
        """
        self.tribler_config.set_dispersy_enabled(True)
        self.assertEqual(self.tribler_config.get_dispersy_enabled(), True)
        self.tribler_config.set_dispersy_port(True)
        self.assertEqual(self.tribler_config.get_dispersy_port(), True)

    def test_get_set_methods_libtorrent(self):
        """
        Check whether libtorrent get and set methods are working as expected.
        """
        self.tribler_config.set_libtorrent_enabled(True)
        self.assertEqual(self.tribler_config.get_libtorrent_enabled(), True)
        self.tribler_config.set_libtorrent_utp(True)
        self.assertEqual(self.tribler_config.get_libtorrent_utp(), True)
        self.tribler_config.set_libtorrent_port(True)
        self.assertEqual(self.tribler_config.get_libtorrent_port(), True)
        self.tribler_config.set_libtorrent_port_runtime(True)
        self.assertEqual(self.tribler_config.get_libtorrent_port(), True)
        self.tribler_config.set_anon_listen_port(True)
        self.assertEqual(self.tribler_config.get_anon_listen_port(), True)
        self.tribler_config.set_libtorrent_proxy_settings(3, True, False)
        self.assertEqual(self.tribler_config.get_libtorrent_proxy_settings(), (3, True, False))
        self.tribler_config.set_anon_proxy_settings(0, None, None)
        self.assertEqual(self.tribler_config.get_anon_proxy_settings(), (0, (None, None), None))
        self.tribler_config.set_anon_proxy_settings(3, ("TEST", [5]), ("TUN", "TPW"))
        self.assertEqual(self.tribler_config.get_anon_proxy_settings(), (3, ("TEST", [5]), ("TUN", "TPW")))
        self.tribler_config.set_libtorrent_max_conn_download(True)
        self.assertEqual(self.tribler_config.get_libtorrent_max_conn_download(), True)
        self.tribler_config.set_libtorrent_max_upload_rate(True)
        self.assertEqual(self.tribler_config.get_libtorrent_max_upload_rate(), True)
        self.tribler_config.set_libtorrent_max_download_rate(True)
        self.assertEqual(self.tribler_config.get_libtorrent_max_download_rate(), True)

    def test_get_set_methods_mainline_dht(self):
        """
        Check whether mainline dht get and set methods are working as expected.
        """
        self.tribler_config.set_mainline_dht_enabled(True)
        self.assertEqual(self.tribler_config.get_mainline_dht_enabled(), True)
        self.tribler_config.set_mainline_dht_port(True)
        self.assertEqual(self.tribler_config.get_mainline_dht_port(), True)

    def test_get_set_methods_video_server(self):
        """
        Check whether video server get and set methods are working as expected.
        """
        self.tribler_config.set_video_server_enabled(True)
        self.assertEqual(self.tribler_config.get_video_server_enabled(), True)
        self.tribler_config.set_video_server_port(True)
        self.assertEqual(self.tribler_config.get_video_server_port(), True)

    def test_get_set_methods_tunnel_community(self):
        """
        Check whether tunnel community get and set methods are working as expected.
        """
        self.tribler_config.set_tunnel_community_enabled(True)
        self.assertEqual(self.tribler_config.get_tunnel_community_enabled(), True)
        self.tribler_config.set_tunnel_community_hidden_seeding(False)
        self.assertEqual(self.tribler_config.get_tunnel_community_hidden_seeding(), False)
        self.tribler_config.set_tunnel_community_socks5_listen_ports([-1])
        self.assertNotEqual(self.tribler_config.get_tunnel_community_socks5_listen_ports(), [-1])
        self.tribler_config.set_tunnel_community_socks5_listen_ports([5])
        self.assertEqual(self.tribler_config.get_tunnel_community_socks5_listen_ports(), [5])
        self.tribler_config.set_tunnel_community_exitnode_enabled(True)
        self.assertEqual(self.tribler_config.get_tunnel_community_exitnode_enabled(), True)
        self.tribler_config.set_default_number_hops(True)
        self.assertEqual(self.tribler_config.get_default_number_hops(), True)
        self.tribler_config.set_default_anonymity_enabled(True)
        self.assertEqual(self.tribler_config.get_default_anonymity_enabled(), True)
        self.tribler_config.set_default_safeseeding_enabled(True)
        self.assertEqual(self.tribler_config.get_default_safeseeding_enabled(), True)
        self.tribler_config.set_default_destination_dir(True)
        self.assertEqual(self.tribler_config.get_default_destination_dir(), True)

    def test_get_set_methods_torrent_store(self):
        """
        Check whether torrent store get and set methods are working as expected.
        """
        self.tribler_config.set_torrent_store_enabled(True)
        self.assertEqual(self.tribler_config.get_torrent_store_enabled(), True)
        self.tribler_config.set_torrent_store_dir("TESTDIR")
        self.tribler_config.set_state_dir("TEST")
        self.assertEqual(self.tribler_config.get_torrent_store_dir(), os.path.join("TEST", "TESTDIR"))

    def test_get_set_methods_wallets(self):
        """
        Check whether wallet get and set methods are working as expected.
        """
        self.tribler_config.set_btc_testnet(True)
        self.assertTrue(self.tribler_config.get_btc_testnet())
        self.tribler_config.set_dummy_wallets_enabled(True)
        self.assertTrue(self.tribler_config.get_dummy_wallets_enabled())

    def test_get_set_is_matchmaker(self):
        """
        Check whether matchmaker get and set methods are working as expected.
        """
        self.tribler_config.set_is_matchmaker(False)
        self.assertFalse(self.tribler_config.get_is_matchmaker())

    def test_get_set_methods_metadata(self):
        """
        Check whether metadata get and set methods are working as expected.
        """
        self.tribler_config.set_metadata_enabled(True)
        self.assertEqual(self.tribler_config.get_metadata_enabled(), True)
        self.tribler_config.set_metadata_store_dir("TESTDIR")
        self.tribler_config.set_state_dir("TEST")
        self.assertEqual(self.tribler_config.get_metadata_store_dir(), os.path.join("TEST", "TESTDIR"))

    def test_get_set_methods_torrent_collecting(self):
        """
        Check whether torrent collecting get and set methods are working as expected.
        """
        self.tribler_config.set_torrent_collecting_enabled(True)
        self.assertEqual(self.tribler_config.get_torrent_collecting_enabled(), True)
        self.tribler_config.set_torrent_collecting_max_torrents(True)
        self.assertEqual(self.tribler_config.get_torrent_collecting_max_torrents(), True)
        self.tribler_config.set_torrent_collecting_dir(True)
        self.assertEqual(self.tribler_config.get_torrent_collecting_dir(), True)

    def test_get_set_methods_search_community(self):
        """
        Check whether search community get and set methods are working as expected.
        """
        self.tribler_config.set_torrent_search_enabled(True)
        self.assertEqual(self.tribler_config.get_torrent_search_enabled(), True)

    def test_get_set_methods_allchannel_community(self):
        """
        Check whether allchannel community get and set methods are working as expected.
        """
        self.tribler_config.set_channel_search_enabled(True)
        self.assertEqual(self.tribler_config.get_channel_search_enabled(), True)

    def test_get_set_methods_channel_community(self):
        """
        Check whether channel community get and set methods are working as expected.
        """
        self.tribler_config.set_channel_community_enabled(True)
        self.assertEqual(self.tribler_config.get_channel_community_enabled(), True)

    def test_get_set_methods_preview_channel_community(self):
        """
        Check whether preview channel community get and set methods are working as expected.
        """
        self.tribler_config.set_preview_channel_community_enabled(True)
        self.assertEqual(self.tribler_config.get_preview_channel_community_enabled(), True)

    def test_get_set_methods_watch_folder(self):
        """
        Check whether watch folder get and set methods are working as expected.
        """
        self.tribler_config.set_watch_folder_enabled(True)
        self.assertEqual(self.tribler_config.get_watch_folder_enabled(), True)
        self.tribler_config.set_watch_folder_path(True)
        self.assertEqual(self.tribler_config.get_watch_folder_path(), True)

    def test_get_set_methods_resource_monitor(self):
        """
        Check whether resource monitor get and set methods are working as expected.
        """
        self.tribler_config.set_resource_monitor_enabled(False)
        self.assertFalse(self.tribler_config.get_resource_monitor_enabled())
        self.tribler_config.set_resource_monitor_poll_interval(21)
        self.assertEqual(self.tribler_config.get_resource_monitor_poll_interval(), 21)
        self.tribler_config.set_resource_monitor_history_size(1234)
        self.assertEqual(self.tribler_config.get_resource_monitor_history_size(), 1234)

    def test_get_set_methods_credit_mining(self):
        """
        Check whether credit mining get and set methods are working as expected.
        """
        self.tribler_config.set_credit_mining_enabled(True)
        self.assertEqual(self.tribler_config.get_credit_mining_enabled(), True)
        self.tribler_config.set_credit_mining_sources(True)
        self.assertEqual(self.tribler_config.get_credit_mining_sources(), True)

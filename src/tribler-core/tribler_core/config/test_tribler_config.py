
from tribler_core.config.tribler_config import CONFIG_FILENAME, TriblerConfig
from tribler_core.tests.tools.base_test import TriblerCoreTest
from tribler_core.utilities import path_util
from tribler_core.utilities.osutils import get_home_dir
from tribler_core.utilities.path_util import Path


class TestTriblerConfig(TriblerCoreTest):
    """
    This class contains tests for the tribler configuration file.
    """

    async def setUp(self):
        """
        Create a new TriblerConfig instance
        """
        await super(TestTriblerConfig, self).setUp()

        self.tribler_config = TriblerConfig(self.getRootStateDir())

        self.assertIsNotNone(self.tribler_config)

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
        path = self.tribler_config.get_state_dir() / CONFIG_FILENAME
        read_config = TriblerConfig(self.root_state_dir, config_file=path)
        self.assertEqual(read_config.get_anon_listen_port(), port)

    def test_load(self):
        self.tribler_config.get_state_dir().is_dir()

    def test_libtorrent_proxy_settings(self):
        """
        Setting and getting of libtorrent proxy settings.
        """
        proxy_type, server, auth = 3, ['33.33.33.33', '22'], ['user', 'pass']
        self.tribler_config.set_libtorrent_proxy_settings(proxy_type, ':'.join(server), ':'.join(auth))
        self.assertEqual(self.tribler_config.get_libtorrent_proxy_settings()[0], proxy_type)
        self.assertEqual(self.tribler_config.get_libtorrent_proxy_settings()[1], server)
        self.assertEqual(self.tribler_config.get_libtorrent_proxy_settings()[2], auth)

        # if the proxy type doesn't support authentication, auth setting should be saved as None
        proxy_type = 1
        self.tribler_config.set_libtorrent_proxy_settings(proxy_type, ':'.join(server), ':'.join(auth))
        self.assertEqual(self.tribler_config.get_libtorrent_proxy_settings()[0], proxy_type)
        self.assertEqual(self.tribler_config.get_libtorrent_proxy_settings()[1], server)
        self.assertEqual(self.tribler_config.get_libtorrent_proxy_settings()[2], ['', ''])

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

    def test_bootstrap_configs(self):

        self.tribler_config.set_bootstrap_enabled(False)
        self.assertFalse(self.tribler_config.get_bootstrap_enabled())

        self.tribler_config.set_bootstrap_max_download_rate(20)
        self.assertEqual(self.tribler_config.get_bootstrap_max_download_rate(), 20)

        self.tribler_config.set_bootstrap_infohash("TestInfohash")
        self.assertEqual(self.tribler_config.get_bootstrap_infohash(), "TestInfohash")

    def test_relative_paths(self):
        # Default should be taken from config.spec
        self.assertEqual(self.tribler_config.get_trustchain_keypair_filename(),
                         path_util.abspath(self.state_dir / "ec_multichain.pem"))

        local_name = Path("somedir") / "ec_multichain.pem"
        global_name = self.state_dir / local_name
        self.tribler_config.set_trustchain_keypair_filename(global_name)

        # It should always return global path
        self.assertEqual(self.tribler_config.get_trustchain_keypair_filename(), global_name)
        # But internally it should be stored as a local path string
        self.assertEqual(self.tribler_config.config['trustchain']['ec_keypair_filename'], str(local_name))

        # If it points out of the state dir, it should be saved as a global path string
        out_of_dir_name_global = path_util.abspath(self.state_dir / ".." / "filename").resolve()
        self.tribler_config.set_trustchain_keypair_filename(out_of_dir_name_global)
        self.assertEqual(self.tribler_config.config['trustchain']['ec_keypair_filename'], str(out_of_dir_name_global))

    def test_get_set_methods_general(self):
        """
        Check whether general get and set methods are working as expected.
        """
        self.assertEqual(self.tribler_config.get_trustchain_testnet_keypair_filename(),
                         self.tribler_config.get_state_dir() / "ec_trustchain_testnet.pem")
        self.tribler_config.set_trustchain_testnet_keypair_filename("bla2")
        self.assertEqual(self.tribler_config.get_trustchain_testnet_keypair_filename(),
                         self.tribler_config.get_state_dir() / "bla2")
        self.tribler_config.set_trustchain_testnet(True)
        self.assertTrue(self.tribler_config.get_trustchain_testnet())
        self.tribler_config.set_log_dir(self.tribler_config.get_state_dir() / "bla3")
        self.assertEqual(self.tribler_config.get_log_dir(), self.tribler_config.get_state_dir() / "bla3")

    def test_get_set_methods_version_checker(self):
        """
        Checks whether version checker get and set methods are working as expected.
        """
        # Default is always true
        self.assertTrue(self.tribler_config.get_version_checker_enabled())
        # Test disabling
        self.tribler_config.set_version_checker_enabled(False)
        self.assertFalse(self.tribler_config.get_version_checker_enabled())
        # Test enabling
        self.tribler_config.set_version_checker_enabled(True)
        self.assertTrue(self.tribler_config.get_version_checker_enabled())

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
        self.tribler_config.set_http_api_retry_port(True)
        self.assertTrue(self.tribler_config.get_http_api_retry_port())

    def test_get_set_methods_ipv8(self):
        """
        Check whether IPv8 get and set methods are working as expected.
        """
        self.tribler_config.set_ipv8_enabled(False)
        self.assertEqual(self.tribler_config.get_ipv8_enabled(), False)
        self.tribler_config.set_ipv8_port(1234)
        self.assertEqual(self.tribler_config.get_ipv8_port(), 1234)
        self.tribler_config.set_ipv8_bootstrap_override("127.0.0.1:12345")
        self.assertEqual(self.tribler_config.get_ipv8_bootstrap_override(), ("127.0.0.1", 12345))
        self.tribler_config.set_ipv8_statistics(True)
        self.assertTrue(self.tribler_config.get_ipv8_statistics())

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
        proxy_server, proxy_auth = ["localhost", "9090"], ["user", "pass"]
        self.tribler_config.set_libtorrent_proxy_settings(3, ":".join(proxy_server), ":".join(proxy_auth))
        self.assertEqual(self.tribler_config.get_libtorrent_proxy_settings(), (3, proxy_server, proxy_auth))
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
        self.tribler_config.set_libtorrent_dht_enabled(False)
        self.assertFalse(self.tribler_config.get_libtorrent_dht_enabled())

    def test_get_set_methods_tunnel_community(self):
        """
        Check whether tunnel community get and set methods are working as expected.
        """
        self.tribler_config.set_tunnel_community_enabled(True)
        self.assertEqual(self.tribler_config.get_tunnel_community_enabled(), True)
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
        self.tribler_config.set_default_destination_dir(get_home_dir())
        self.assertEqual(self.tribler_config.get_default_destination_dir(), path_util.Path(get_home_dir()))
        self.tribler_config.set_tunnel_community_random_slots(10)
        self.assertEqual(self.tribler_config.get_tunnel_community_random_slots(), 10)
        self.tribler_config.set_tunnel_community_competing_slots(20)
        self.assertEqual(self.tribler_config.get_tunnel_community_competing_slots(), 20)
        self.tribler_config.set_tunnel_testnet(True)
        self.assertTrue(self.tribler_config.get_tunnel_testnet())

    def test_get_set_methods_wallets(self):
        """
        Check whether wallet get and set methods are working as expected.
        """
        self.tribler_config.set_dummy_wallets_enabled(True)
        self.assertTrue(self.tribler_config.get_dummy_wallets_enabled())
        self.tribler_config.set_bitcoinlib_enabled(False)
        self.assertFalse(self.tribler_config.get_bitcoinlib_enabled())

    def test_get_set_chant_methods(self):
        """
        Check whether chant get and set methods are working as expected.
        """
        self.tribler_config.set_chant_enabled(False)
        self.assertFalse(self.tribler_config.get_chant_enabled())
        self.tribler_config.set_chant_channels_dir('test')
        self.assertEqual(self.tribler_config.get_chant_channels_dir(),
                         self.tribler_config.get_state_dir() / 'test')
        self.tribler_config.set_chant_testnet(True)
        self.assertTrue(self.tribler_config.get_chant_testnet())

    def test_get_set_is_matchmaker(self):
        """
        Check whether matchmaker get and set methods are working as expected.
        """
        self.tribler_config.set_is_matchmaker(False)
        self.assertFalse(self.tribler_config.get_is_matchmaker())

    def test_get_set_methods_popularity_community(self):
        """
        Check whether popularity community get and set methods are working as expected.
        """
        self.tribler_config.set_popularity_community_enabled(True)
        self.assertEqual(self.tribler_config.get_popularity_community_enabled(), True)

    def test_get_set_methods_watch_folder(self):
        """
        Check whether watch folder get and set methods are working as expected.
        """
        self.tribler_config.set_watch_folder_enabled(True)
        self.assertEqual(self.tribler_config.get_watch_folder_enabled(), True)
        self.tribler_config.set_watch_folder_path(get_home_dir())
        self.assertEqual(self.tribler_config.get_watch_folder_path(), get_home_dir())

    def test_get_set_methods_resource_monitor(self):
        """
        Check whether resource monitor get and set methods are working as expected.
        """
        self.assertTrue(self.tribler_config.get_resource_monitor_enabled())
        self.tribler_config.set_resource_monitor_enabled(False)
        self.assertFalse(self.tribler_config.get_resource_monitor_enabled())
        self.tribler_config.set_resource_monitor_poll_interval(21)
        self.assertEqual(self.tribler_config.get_resource_monitor_poll_interval(), 21)
        self.tribler_config.set_resource_monitor_history_size(1234)
        self.assertEqual(self.tribler_config.get_resource_monitor_history_size(), 1234)

        self.assertEqual(self.tribler_config.get_cpu_priority_order(), 1)
        self.tribler_config.set_cpu_priority_order(3)
        self.assertEqual(self.tribler_config.get_cpu_priority_order(), 3)

    def test_get_set_methods_dht(self):
        """
        Check whether dht get and set methods are working as expected.
        """
        self.tribler_config.set_dht_enabled(False)
        self.assertFalse(self.tribler_config.get_dht_enabled())

    def test_get_set_methods_record_transactions(self):
        """
        Check whether record_transactions get and set methods are working as expected.
        """
        self.tribler_config.set_record_transactions(True)
        self.assertTrue(self.tribler_config.get_record_transactions())

    def test_get_set_default_add_download_to_channel(self):
        """
        Check whether set/get methods of default add download to channel works.
        """
        self.assertEqual(self.tribler_config.get_default_add_download_to_channel(), False)
        self.tribler_config.set_default_add_download_to_channel(True)
        self.assertEqual(self.tribler_config.get_default_add_download_to_channel(), True)

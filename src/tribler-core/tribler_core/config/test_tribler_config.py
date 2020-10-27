from pathlib import Path

from tribler_core.config.tribler_config import CONFIG_FILENAME, TriblerConfig
from tribler_core.utilities.osutils import get_home_dir


def test_init_without_config(tribler_config):
    """
    A newly created TriblerConfig is valid.
    """
    tribler_config.validate()


def test_write_load(tribler_config):
    """
    When writing and reading a config the options should remain the same.
    """
    port = 4444
    tribler_config.set_anon_listen_port(port)
    tribler_config.write()
    path = tribler_config.get_state_dir() / CONFIG_FILENAME
    read_config = TriblerConfig(path, config_file=path)
    assert read_config.get_anon_listen_port() == port


def test_libtorrent_proxy_settings(tribler_config):
    """
    Setting and getting of libtorrent proxy settings.
    """
    proxy_type, server, auth = 3, ['33.33.33.33', '22'], ['user', 'pass']
    tribler_config.set_libtorrent_proxy_settings(proxy_type, ':'.join(server), ':'.join(auth))
    assert tribler_config.get_libtorrent_proxy_settings()[0] == proxy_type
    assert tribler_config.get_libtorrent_proxy_settings()[1] == server
    assert tribler_config.get_libtorrent_proxy_settings()[2] == auth

    # if the proxy type doesn't support authentication, auth setting should be saved as None
    proxy_type = 1
    tribler_config.set_libtorrent_proxy_settings(proxy_type, ':'.join(server), ':'.join(auth))
    assert tribler_config.get_libtorrent_proxy_settings()[0], proxy_type
    assert tribler_config.get_libtorrent_proxy_settings()[1], server
    assert tribler_config.get_libtorrent_proxy_settings()[2], ['', '']


def test_anon_proxy_settings(tribler_config):
    proxy_type, server, auth = 3, ("33.33.33.33", [2222, 2223, 4443, 58848]), 1
    tribler_config.set_anon_proxy_settings(proxy_type, server, auth)

    assert tribler_config.get_anon_proxy_settings()[0] == proxy_type
    assert tribler_config.get_anon_proxy_settings()[1] == server
    assert tribler_config.get_anon_proxy_settings()[2] == auth

    proxy_type = 1
    tribler_config.set_anon_proxy_settings(proxy_type, server, auth)

    assert tribler_config.get_anon_proxy_settings()[0] == proxy_type
    assert tribler_config.get_anon_proxy_settings()[1] == server
    assert not tribler_config.get_anon_proxy_settings()[2]


def test_tunnel_community_socks5_listen_ports(tribler_config):
    ports = [5554, 9949, 9588, 35555, 84899]
    tribler_config.set_tunnel_community_socks5_listen_ports(ports)
    assert tribler_config.get_tunnel_community_socks5_listen_ports() == ports


def test_bootstrap_configs(tribler_config):
    tribler_config.set_bootstrap_enabled(False)
    assert not tribler_config.get_bootstrap_enabled()

    tribler_config.set_bootstrap_max_download_rate(20)
    assert tribler_config.get_bootstrap_max_download_rate() == 20

    tribler_config.set_bootstrap_infohash("TestInfohash")
    assert tribler_config.get_bootstrap_infohash() == "TestInfohash"


def test_relative_paths(tribler_config, state_dir):
    # Default should be taken from config.spec
    assert tribler_config.get_trustchain_keypair_filename() == (state_dir / "ec_multichain.pem").absolute()

    local_name = Path("somedir") / "ec_multichain.pem"
    global_name = state_dir / local_name
    tribler_config.set_trustchain_keypair_filename(global_name)

    # It should always return global path
    assert tribler_config.get_trustchain_keypair_filename() == global_name
    # But internally it should be stored as a local path string
    assert tribler_config.config['trustchain']['ec_keypair_filename'] == str(local_name)

    # If it points out of the state dir, it should be saved as a global path string
    out_of_dir_name_global = (state_dir / ".." / "filename").resolve()
    tribler_config.set_trustchain_keypair_filename(out_of_dir_name_global)
    assert tribler_config.config['trustchain']['ec_keypair_filename'] == str(out_of_dir_name_global)


def test_get_set_methods_general(tribler_config, state_dir):
    """
    Check whether general get and set methods are working as expected.
    """
    assert tribler_config.get_trustchain_testnet_keypair_filename() == state_dir / "ec_trustchain_testnet.pem"
    tribler_config.set_trustchain_testnet_keypair_filename("bla2")
    assert tribler_config.get_trustchain_testnet_keypair_filename(), state_dir / "bla2"

    tribler_config.set_log_dir(tribler_config.get_state_dir() / "bla3")
    assert tribler_config.get_log_dir() == tribler_config.get_state_dir() / "bla3"


def test_get_set_methods_version_checker(tribler_config):
    """
    Checks whether version checker get and set methods are working as expected.
    """
    tribler_config.set_version_checker_enabled(True)
    assert tribler_config.get_version_checker_enabled()


def test_get_set_methods_torrent_checking(tribler_config):
    """
    Check whether torrent checking get and set methods are working as expected.
    """
    tribler_config.set_torrent_checking_enabled(True)
    assert tribler_config.get_torrent_checking_enabled()


def test_get_set_methods_rest_api(tribler_config):
    """
    Check whether http api get and set methods are working as expected.
    """
    tribler_config.set_api_http_enabled(True)
    assert tribler_config.get_api_http_enabled()
    tribler_config.set_api_http_port(123)
    assert tribler_config.get_api_http_port() == 123
    tribler_config.set_api_https_enabled(True)
    assert tribler_config.get_api_https_enabled()
    tribler_config.set_api_https_port(123)
    assert tribler_config.get_api_https_port() == 123
    tribler_config.set_api_https_certfile('certfile.pem')
    assert tribler_config.get_api_https_certfile() == tribler_config.get_state_dir() / 'certfile.pem'
    tribler_config.set_api_key('000')
    assert tribler_config.get_api_key() == '000'
    tribler_config.set_api_retry_port(True)
    assert tribler_config.get_api_retry_port()


def test_get_set_methods_ipv8(tribler_config):
    """
    Check whether IPv8 get and set methods are working as expected.
    """
    tribler_config.set_ipv8_enabled(False)
    assert not tribler_config.get_ipv8_enabled()
    tribler_config.set_ipv8_port(1234)
    assert tribler_config.get_ipv8_port() == 1234
    tribler_config.set_ipv8_bootstrap_override("127.0.0.1:12345")
    assert tribler_config.get_ipv8_bootstrap_override() == ("127.0.0.1", 12345)
    tribler_config.set_ipv8_statistics(True)
    assert tribler_config.get_ipv8_statistics()
    tribler_config.set_ipv8_walk_interval(0.77)
    assert tribler_config.get_ipv8_walk_interval() == 0.77
    tribler_config.set_ipv8_walk_scaling_enabled(False)
    assert not tribler_config.get_ipv8_walk_scaling_enabled()
    tribler_config.set_ipv8_walk_scaling_upper_limit(9.6)
    assert tribler_config.get_ipv8_walk_scaling_upper_limit() == 9.6


def test_get_set_methods_libtorrent(tribler_config):
    """
    Check whether libtorrent get and set methods are working as expected.
    """
    tribler_config.set_libtorrent_enabled(True)
    assert tribler_config.get_libtorrent_enabled()
    tribler_config.set_libtorrent_utp(True)
    assert tribler_config.get_libtorrent_utp()
    tribler_config.set_libtorrent_port(1234)
    assert tribler_config.get_libtorrent_port() == 1234
    tribler_config.set_libtorrent_port_runtime(1235)
    assert tribler_config.get_libtorrent_port() == 1235
    tribler_config.set_anon_listen_port(1236)
    assert tribler_config.get_anon_listen_port() == 1236
    proxy_server, proxy_auth = ["localhost", "9090"], ["user", "pass"]
    tribler_config.set_libtorrent_proxy_settings(3, ":".join(proxy_server), ":".join(proxy_auth))
    assert tribler_config.get_libtorrent_proxy_settings() == (3, proxy_server, proxy_auth)
    tribler_config.set_anon_proxy_settings(0, None, None)
    assert tribler_config.get_anon_proxy_settings() == (0, (None, None), None)
    tribler_config.set_anon_proxy_settings(3, ("TEST", [5]), ("TUN", "TPW"))
    assert tribler_config.get_anon_proxy_settings() == (3, ("TEST", [5]), ("TUN", "TPW"))
    tribler_config.set_libtorrent_max_conn_download(352)
    assert tribler_config.get_libtorrent_max_conn_download() == 352
    tribler_config.set_libtorrent_max_upload_rate(4338224)
    assert tribler_config.get_libtorrent_max_upload_rate() == 4338224
    tribler_config.set_libtorrent_max_download_rate(83924)
    assert tribler_config.get_libtorrent_max_download_rate() == 83924
    tribler_config.set_libtorrent_dht_enabled(False)
    assert not tribler_config.get_libtorrent_dht_enabled()


def test_get_set_methods_tunnel_community(tribler_config):
    """
    Check whether tunnel community get and set methods are working as expected.
    """
    tribler_config.set_tunnel_community_enabled(True)
    assert tribler_config.get_tunnel_community_enabled()
    tribler_config.set_tunnel_community_socks5_listen_ports([-1])
    assert tribler_config.get_tunnel_community_socks5_listen_ports() != [-1]  # We cannot set a negative port
    tribler_config.set_tunnel_community_socks5_listen_ports([5])
    assert tribler_config.get_tunnel_community_socks5_listen_ports() == [5]
    tribler_config.set_tunnel_community_exitnode_enabled(True)
    assert tribler_config.get_tunnel_community_exitnode_enabled()
    tribler_config.set_default_number_hops(324)
    assert tribler_config.get_default_number_hops() == 324
    tribler_config.set_default_anonymity_enabled(True)
    assert tribler_config.get_default_anonymity_enabled()
    tribler_config.set_default_safeseeding_enabled(True)
    assert tribler_config.get_default_safeseeding_enabled()
    tribler_config.set_default_destination_dir(get_home_dir())
    assert tribler_config.get_default_destination_dir() == Path(get_home_dir())
    tribler_config.set_tunnel_community_random_slots(10)
    assert tribler_config.get_tunnel_community_random_slots() == 10
    tribler_config.set_tunnel_community_competing_slots(20)
    assert tribler_config.get_tunnel_community_competing_slots() == 20
    tribler_config.set_tunnel_testnet(True)
    assert tribler_config.get_tunnel_testnet()


def test_get_set_chant_methods(tribler_config, state_dir):
    """
    Check whether chant get and set methods are working as expected.
    """
    tribler_config.set_chant_enabled(False)
    assert not tribler_config.get_chant_enabled()
    tribler_config.set_chant_channels_dir('test')
    assert tribler_config.get_chant_channels_dir() == state_dir / 'test'
    tribler_config.set_chant_testnet(True)
    assert tribler_config.get_chant_testnet()


def test_get_set_methods_popularity_community(tribler_config):
    """
    Check whether popularity community get and set methods are working as expected.
    """
    tribler_config.set_popularity_community_enabled(True)
    assert tribler_config.get_popularity_community_enabled()


def test_get_set_methods_watch_folder(tribler_config):
    """
    Check whether watch folder get and set methods are working as expected.
    """
    tribler_config.set_watch_folder_enabled(True)
    assert tribler_config.get_watch_folder_enabled()
    tribler_config.set_watch_folder_path(get_home_dir())
    assert tribler_config.get_watch_folder_path() == get_home_dir()


def test_get_set_methods_resource_monitor(tribler_config):
    """
    Check whether resource monitor get and set methods are working as expected.
    """
    tribler_config.set_resource_monitor_enabled(False)
    assert not tribler_config.get_resource_monitor_enabled()
    tribler_config.set_resource_monitor_poll_interval(21)
    assert tribler_config.get_resource_monitor_poll_interval() == 21
    tribler_config.set_resource_monitor_history_size(1234)
    assert tribler_config.get_resource_monitor_history_size() == 1234

    assert tribler_config.get_cpu_priority_order() == 1
    tribler_config.set_cpu_priority_order(3)
    assert tribler_config.get_cpu_priority_order() == 3


def test_get_set_methods_dht(tribler_config):
    """
    Check whether dht get and set methods are working as expected.
    """
    tribler_config.set_dht_enabled(False)
    assert not tribler_config.get_dht_enabled()


def test_get_set_default_add_download_to_channel(tribler_config):
    """
    Check whether set/get methods of default add download to channel works.
    """
    assert not tribler_config.get_default_add_download_to_channel()
    tribler_config.set_default_add_download_to_channel(True)
    assert tribler_config.get_default_add_download_to_channel()


def test_get_set_discovery_community_enabled(tribler_config):
    """
    Test disabling the discovery community.
    """
    assert not tribler_config.get_discovery_community_enabled()
    tribler_config.set_discovery_community_enabled(True)
    assert tribler_config.get_discovery_community_enabled()

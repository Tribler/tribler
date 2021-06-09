"""
Configuration object for the Tribler Core.
"""
import logging
import os
import traceback

from configobj import ConfigObj, ParseError
from validate import Validator

from tribler_common.simpledefs import MAX_LIBTORRENT_RATE_LIMIT
from tribler_core.exceptions import InvalidConfigException
from tribler_core.utilities import path_util
from tribler_core.utilities.install_dir import get_lib_path
from tribler_core.utilities.path_util import Path

class TriblerConfig:
    def __init__(self, state_dir):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f'Init. State dir: {state_dir}')

        self.error = None
        self.file = None
        self.config = None

        self.state_dir = state_dir
        self.create_empty_config()

    def create_empty_config(self):
        self.config = TriblerConfig._load()
        self.validate()

    def load(self, file: Path = None, reset_config_on_error=False):
        self.logger.info(f'Load: {file}. Reset config on error: {reset_config_on_error}')
        self.file = file
        self.error = None

        try:
            self.config = TriblerConfig._load(file)
        except ParseError:
            self.error = traceback.format_exc()
            self.logger.warning(f'Error: {self.error}')

            if not reset_config_on_error:
                raise

        if self.error and reset_config_on_error:
            self.logger.info(f'Create a default config')

            self.config = TriblerConfig._load(None)
            self.write(file=file)

        self.validate()

    @staticmethod
    def _load(file=None, spec=get_lib_path() / 'config' / 'tribler_config.spec'):
        return ConfigObj(
            infile=str(file) if file else None,
            configspec=str(spec) if spec else None,
            default_encoding='utf-8',
        )

    def write(self, file: Path = None):
        if not file:
            file = self.file  # try to remember a file from the last load

        self.logger.info(f'Write: {file}')

        if not file:
            return

        parent = Path(file).parent
        if not parent.exists():
            self.logger.info(f'Create folder: {parent}')
            parent.mkdir(parents=True)

        self.config.filename = file
        self.config.write()

    def validate(self):
        self.logger.info(f'Validate')

        result = self.config.validate(Validator())
        self.logger.info(f'Result: {result}')

        if result is not True:
            raise InvalidConfigException(msg=f"TriblerConfig is invalid: {str(result)}")

    def copy(self):
        self.logger.info(f'Copy')

        new_config = TriblerConfig(self.state_dir)
        new_config.config = ConfigObj(infile=self.config.copy(),
                                      configspec=self.config.configspec,
                                      default_encoding='utf-8')

        for section in self.config:
            new_config.config[section] = self.config[section].copy()

        return new_config

    @property
    def state_dir(self):
        return self._state_dir

    @state_dir.setter
    def state_dir(self, value):
        self._state_dir = Path(value)

    def abspath(self, path):
        return path_util.abspath(path, optional_prefix=self.state_dir)

    def norm_path(self, path):
        """
        Return absolute path if it points outside the state dir. Otherwise, change it to relative path.
        """
        return path_util.norm_path(self.state_dir, path)

    # Version and backup
    def set_version(self, version):
        self.config['general']['version'] = version

    def get_version(self):
        return self.config['general']['version']

    def set_log_dir(self, value):
        self.config['general']['log_dir'] = str(self.norm_path(value))

    def get_log_dir(self):
        return self.abspath(self.config['general']['log_dir'])

    def set_version_checker_enabled(self, value):
        self.config['general']['version_checker_enabled'] = value

    def get_version_checker_enabled(self):
        return self.config['general']['version_checker_enabled']

    # Chant
    def set_chant_enabled(self, value):
        self.config['chant']['enabled'] = bool(value)

    def get_chant_enabled(self):
        return self.config['chant']['enabled']

    def get_chant_manager_enabled(self):
        return self.config['chant']['manager_enabled']

    def set_chant_manager_enabled(self, value):
        self.config['chant']['manager_enabled'] = value

    def set_chant_channels_dir(self, chant_db_filename):
        self.config['chant']['channels_dir'] = str(self.norm_path(chant_db_filename))

    def get_chant_channels_dir(self):
        return self.abspath(self.config['chant']['channels_dir'])

    def set_chant_testnet(self, value):
        self.config['chant']['testnet'] = value

    def get_chant_testnet(self):
        return 'TESTNET' in os.environ or 'CHANT_TESTNET' in os.environ or self.config['chant']['testnet']

    # TrustChain

    def set_trustchain_keypair_filename(self, keypairfilename):
        self.config['trustchain']['ec_keypair_filename'] = str(self.norm_path(keypairfilename))

    def get_trustchain_keypair_filename(self):
        return self.abspath(self.config['trustchain']['ec_keypair_filename'])

    def set_trustchain_testnet_keypair_filename(self, keypairfilename):
        self.config['trustchain']['testnet_keypair_filename'] = str(self.norm_path(keypairfilename))

    def get_trustchain_testnet_keypair_filename(self):
        return self.abspath(self.config['trustchain']['testnet_keypair_filename'])

    def get_trustchain_testnet(self):
        return 'TESTNET' in os.environ or 'TRUSTCHAIN_TESTNET' in os.environ or self.config['trustchain']['testnet']

    def set_trustchain_testnet(self, value):
        self.config['trustchain']['testnet'] = value

    # Bandwidth accounting

    def get_bandwidth_testnet(self) -> bool:
        return 'TESTNET' in os.environ or 'BANDWIDTH_TESTNET' in os.environ \
               or self.config['bandwidth_accounting']['testnet']

    def set_bandwidth_testnet(self, value: bool) -> None:
        self.config['bandwidth_accounting']['testnet'] = value

    # Bootstrap

    def set_bootstrap_enabled(self, value):
        self.config['bootstrap']['enabled'] = value

    def get_bootstrap_enabled(self):
        return self.config['bootstrap']['enabled']

    def get_bootstrap_max_download_rate(self):
        return self.config['bootstrap'].as_int('max_download_rate')

    def set_bootstrap_max_download_rate(self, value):
        self.config['bootstrap']['max_download_rate'] = value

    def get_bootstrap_infohash(self):
        return self.config['bootstrap']['infohash']

    def set_bootstrap_infohash(self, value):
        self.config['bootstrap']['infohash'] = value

    # Torrent checking

    def set_torrent_checking_enabled(self, value):
        self.config['torrent_checking']['enabled'] = value

    def get_torrent_checking_enabled(self):
        return self.config['torrent_checking']['enabled']

    # REST API

    def set_api_http_enabled(self, http_enabled):
        self.config['api']['http_enabled'] = http_enabled

    def get_api_http_enabled(self):
        return self.config['api']['http_enabled']

    def set_api_http_port(self, http_port):
        self.config['api']['http_port'] = http_port

    def get_api_http_port(self):
        return self.config['api']['http_port']

    def set_api_https_enabled(self, https_enabled):
        self.config['api']['https_enabled'] = https_enabled

    def get_api_https_enabled(self):
        return self.config['api']['https_enabled']

    def set_api_https_port(self, https_port):
        self.config['api']['https_port'] = https_port

    def get_api_https_port(self):
        return self.config['api']['https_port']

    def set_api_https_certfile(self, certfile):
        self.config['api']['https_certfile'] = certfile

    def get_api_https_certfile(self):
        return self.abspath(self.config['api']['https_certfile'])

    def set_api_key(self, key):
        self.config['api']['key'] = key

    def get_api_key(self):
        return self.config['api']['key']

    def set_api_retry_port(self, retry_port):
        self.config['api']['retry_port'] = retry_port

    def get_api_retry_port(self):
        return self.config['api']['retry_port']

    # IPv8

    def set_ipv8_enabled(self, value):
        self.config['ipv8']['enabled'] = value

    def get_ipv8_enabled(self):
        return self.config['ipv8']['enabled']

    def set_ipv8_port(self, value):
        self.config['ipv8']['port'] = value

    def get_ipv8_port(self):
        return self.config['ipv8']['port']

    def set_ipv8_bootstrap_override(self, value):
        self.config['ipv8']['bootstrap_override'] = value

    def get_ipv8_bootstrap_override(self):
        val = self.config['ipv8']['bootstrap_override']
        if not val:
            return None
        address, port = val.split(':')
        return address, int(port)

    def set_ipv8_address(self, value):
        self.config['ipv8']['address'] = value

    def get_ipv8_address(self):
        return self.config['ipv8']['address']

    def set_ipv8_statistics(self, value):
        self.config['ipv8']['statistics'] = value

    def get_ipv8_statistics(self):
        return self.config['ipv8']['statistics']

    def set_ipv8_walk_interval(self, value: float) -> None:
        self.config['ipv8']['walk_interval'] = value

    def get_ipv8_walk_interval(self) -> float:
        return self.config['ipv8']['walk_interval']

    def set_ipv8_walk_scaling_enabled(self, value: bool) -> None:
        self.config['ipv8']['walk_scaling_enabled'] = value

    def get_ipv8_walk_scaling_enabled(self) -> bool:
        return self.config['ipv8']['walk_scaling_enabled']

    def set_ipv8_walk_scaling_upper_limit(self, value: float) -> None:
        self.config['ipv8']['walk_scaling_upper_limit'] = value

    def get_ipv8_walk_scaling_upper_limit(self) -> float:
        return self.config['ipv8']['walk_scaling_upper_limit']

    # Libtorrent

    def set_libtorrent_enabled(self, value):
        self.config['libtorrent']['enabled'] = value

    def get_libtorrent_enabled(self):
        return self.config['libtorrent']['enabled']

    def set_libtorrent_utp(self, value):
        self.config['libtorrent']['utp'] = value

    def get_libtorrent_utp(self):
        return self.config['libtorrent']['utp']

    def set_libtorrent_port(self, port):
        self.config['libtorrent']['port'] = port

    def get_libtorrent_port(self):
        return self.config['libtorrent']['port']

    def set_libtorrent_dht_readiness_timeout(self, value):
        self.config['libtorrent']['dht_readiness_timeout'] = value

    def get_libtorrent_dht_readiness_timeout(self):
        return self.config['libtorrent']['dht_readiness_timeout']

    def set_anon_listen_port(self, listen_port=None):
        self.config['libtorrent']['anon_listen_port'] = listen_port

    def get_anon_listen_port(self):
        return self.config['libtorrent']['anon_listen_port']

    def set_libtorrent_proxy_settings(self, proxy_type, server=None, auth=None):
        """
        Set which proxy LibTorrent should use (default = 0).

        :param proxy_type: int (0 = no proxy server,
                                1 = SOCKS4,
                                2 = SOCKS5,
                                3 = SOCKS5 + auth,
                                4 = HTTP,
                                5 = HTTP + auth)
        :param server: (host, port) tuple or None
        :param auth: (username, password) tuple or None
        """
        self.config['libtorrent']['proxy_type'] = proxy_type
        self.config['libtorrent']['proxy_server'] = server if proxy_type else ':'
        self.config['libtorrent']['proxy_auth'] = auth if proxy_type in [3, 5] else ':'

    def get_libtorrent_proxy_settings(self):
        proxy_server = str(self.config['libtorrent']['proxy_server'])
        proxy_server = proxy_server.split(':') if proxy_server else ['', '']

        proxy_auth = str(self.config['libtorrent']['proxy_auth'])
        proxy_auth = proxy_auth.split(':') if proxy_auth else ['', '']

        return (self.config['libtorrent']['proxy_type'],
                proxy_server, proxy_auth)

    def set_anon_proxy_settings(self, proxy_type, server=None, auth=None):
        """
        :param proxy_type: int (0 = no proxy server,
                                1 = SOCKS4,
                                2 = SOCKS5,
                                3 = SOCKS5 + auth,
                                4 = HTTP,
                                5 = HTTP + auth)
        :param server: (host, [ports]) tuple or None
        :param auth: (username, password) tuple or None
        """
        self.config['libtorrent']['anon_proxy_type'] = proxy_type
        if server and proxy_type:
            self.config['libtorrent']['anon_proxy_server_ip'] = server[0]
            # Convert the integers into strings for the config
            self.config['libtorrent']['anon_proxy_server_ports'] = [str(i) for i in server[1]]
        else:
            self.config['libtorrent']['anon_proxy_server_ip'] = None
            self.config['libtorrent']['anon_proxy_server_ports'] = None
        self.config['libtorrent']['anon_proxy_auth'] = auth if proxy_type in [3, 5] else None

    def get_anon_proxy_settings(self):
        """
        Get the anon proxy settings.

        :return: a 4-tuple with the proxytype in int, (ip as string, list of ports in int), auth
        """
        server_ports = self.config['libtorrent']['anon_proxy_server_ports']
        return (self.config['libtorrent']['anon_proxy_type'],
                (self.config['libtorrent']['anon_proxy_server_ip'],
                 # Convert the strings from the config into ints
                 [int(s) for s in server_ports] if server_ports else None),
                self.config['libtorrent']['anon_proxy_auth'])

    def set_libtorrent_max_conn_download(self, value):
        """
        Set the maximum amount of connections for each download.

        By default, this is -1, unlimited.
        :param value: int.
        """
        self.config['libtorrent']['max_connections_download'] = value

    def get_libtorrent_max_conn_download(self):
        """ Returns the maximum amount of connections per download
        :return: int.
        """
        return self.config['libtorrent']['max_connections_download']

    def set_libtorrent_max_upload_rate(self, value):
        """
        Sets the maximum upload rate (kB / s).

        :param value: the new maximum upload rate in kB / s
        :return:
        """
        self.config['libtorrent']['max_upload_rate'] = value

    def get_libtorrent_max_upload_rate(self):
        """
        Gets the maximum upload rate (kB / s).

        :return: the maximum upload rate in kB / s
        """
        return min(self.config['libtorrent'].as_int('max_upload_rate'), MAX_LIBTORRENT_RATE_LIMIT)

    def set_libtorrent_max_download_rate(self, value):
        """
        Sets the maximum download rate (kB / s).

        :param value: the new maximum download rate in kB / s
        :return:
        """
        self.config['libtorrent']['max_download_rate'] = value

    def get_libtorrent_max_download_rate(self):
        """
        Gets the maximum download rate (kB / s).

        :return: the maximum download rate in kB / s
        """
        return min(self.config['libtorrent'].as_int('max_download_rate'), MAX_LIBTORRENT_RATE_LIMIT)

    def set_libtorrent_dht_enabled(self, value):
        self.config['libtorrent']['dht'] = value

    def get_libtorrent_dht_enabled(self):
        return self.config['libtorrent']['dht']

    # Tunnel Community

    def set_tunnel_community_enabled(self, value):
        self.config['tunnel_community']['enabled'] = value

    def get_tunnel_community_enabled(self):
        return self.config['tunnel_community']['enabled']

    def set_tunnel_community_socks5_listen_ports(self, ports):
        self.config['tunnel_community']['socks5_listen_ports'] = ports

    def get_tunnel_community_socks5_listen_ports(self):
        return self.config['tunnel_community']['socks5_listen_ports']

    def set_tunnel_community_exitnode_enabled(self, value):
        self.config['tunnel_community']['exitnode_enabled'] = value

    def get_tunnel_community_exitnode_enabled(self):
        return self.config['tunnel_community']['exitnode_enabled']

    def set_tunnel_community_random_slots(self, value):
        self.config['tunnel_community']['random_slots'] = value

    def get_tunnel_community_random_slots(self):
        return self.config['tunnel_community']['random_slots']

    def set_tunnel_community_competing_slots(self, value):
        self.config['tunnel_community']['competing_slots'] = value

    def get_tunnel_community_competing_slots(self):
        return self.config['tunnel_community']['competing_slots']

    def set_tunnel_testnet(self, value):
        self.config['tunnel_community']['testnet'] = value

    def get_tunnel_testnet(self):
        return 'TESTNET' in os.environ or 'TUNNEL_TESTNET' in os.environ or self.config['tunnel_community']['testnet']

    def set_default_number_hops(self, value):
        self.config['download_defaults']['number_hops'] = value

    def get_default_number_hops(self):
        return self.config['download_defaults']['number_hops']

    def set_default_anonymity_enabled(self, value):
        self.config['download_defaults']['anonymity_enabled'] = value

    def get_default_anonymity_enabled(self):
        return self.config['download_defaults']['anonymity_enabled']

    def set_default_safeseeding_enabled(self, value):
        self.config['download_defaults']['safeseeding_enabled'] = value

    def get_default_safeseeding_enabled(self):
        return self.config['download_defaults']['safeseeding_enabled']

    def set_default_destination_dir(self, value):
        self.config['download_defaults']['saveas'] = str(self.norm_path(value))

    def get_default_destination_dir(self):
        value = self.config['download_defaults']['saveas']
        return Path(value) if value else None

    def set_default_add_download_to_channel(self, value):
        self.config['download_defaults']['add_download_to_channel'] = value

    def get_default_add_download_to_channel(self):
        return self.config['download_defaults']['add_download_to_channel']

    def set_seeding_mode(self, value):
        self.config['download_defaults']['seeding_mode'] = value

    def get_seeding_mode(self):
        return self.config['download_defaults']['seeding_mode']

    def set_seeding_time(self, value):
        self.config['download_defaults']['seeding_time'] = value

    def get_seeding_time(self):
        return self.config['download_defaults']['seeding_time']

    def set_seeding_ratio(self, value):
        self.config['download_defaults']['seeding_ratio'] = value

    def get_seeding_ratio(self):
        return self.config['download_defaults']['seeding_ratio']

    # Discovery Community

    def set_discovery_community_enabled(self, value: bool) -> None:
        self.config['discovery_community']['enabled'] = value

    def get_discovery_community_enabled(self) -> bool:
        return self.config['discovery_community']['enabled']

    # DHT

    def set_dht_enabled(self, value):
        self.config['dht']['enabled'] = value

    def get_dht_enabled(self):
        return self.config['dht']['enabled']

    # Popular Community

    def get_popularity_community_enabled(self):
        return self.config['popularity_community']['enabled']

    def set_popularity_community_enabled(self, value):
        self.config['popularity_community']['enabled'] = value

    # Watch folder

    def set_watch_folder_enabled(self, value):
        self.config['watch_folder']['enabled'] = value

    def get_watch_folder_enabled(self):
        return self.config['watch_folder']['enabled']

    def set_watch_folder_path(self, value):
        self.config['watch_folder']['directory'] = self.norm_path(value)

    def get_watch_folder_path(self):
        return self.abspath(self.config['watch_folder']['directory'])

    # Resource monitor

    def set_resource_monitor_enabled(self, value):
        self.config['resource_monitor']['enabled'] = value

    def get_resource_monitor_enabled(self):
        if "enabled" in self.config['resource_monitor']:
            return self.config['resource_monitor']['enabled']
        return True

    def set_cpu_priority_order(self, priority):
        self.config['resource_monitor']['cpu_priority'] = priority

    def get_cpu_priority_order(self):
        if "cpu_priority" in self.config['resource_monitor']:
            return self.config['resource_monitor']['cpu_priority']
        return 1

    def set_resource_monitor_poll_interval(self, value):
        self.config['resource_monitor']['poll_interval'] = value

    def get_resource_monitor_poll_interval(self):
        return self.config['resource_monitor']['poll_interval']

    def set_resource_monitor_history_size(self, value):
        self.config['resource_monitor']['history_size'] = value

    def get_resource_monitor_history_size(self):
        return self.config['resource_monitor']['history_size']

    def get_core_error_reporting_requires_user_consent(self):
        return self.config['error_handling']['core_error_reporting_requires_user_consent']

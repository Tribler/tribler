"""
Configuration object for the Tribler Core.
"""
from __future__ import absolute_import

import logging
import os

from configobj import ConfigObj

from six import text_type

from validate import Validator

from Tribler.Core.DownloadConfig import get_default_dest_dir
from Tribler.Core.Utilities.install_dir import get_lib_path
from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Core.exceptions import InvalidConfigException
from Tribler.Core.osutils import get_appstate_dir
from Tribler.util import cast_to_unicode_utf8

CONFIG_FILENAME = 'triblerd.conf'
SPEC_FILENAME = 'config.spec'
CONFIG_SPEC_PATH = os.path.join(get_lib_path(), 'Core', 'Config', SPEC_FILENAME)


class TriblerConfig(object):
    """
    Holds all Tribler Core configurable variables.

    This class is a wrapper around a ConfigObj. It has a specification of it's configuration sections and fields,
    their allowed values and default value in `config.spec`.
    """

    def __init__(self, config=None):
        """
        Create a new TriblerConfig instance.

        :param config: a ConfigObj instance
        :raises an InvalidConfigException if ConfigObj is invalid
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        self._state_dir = self.get_default_state_dir()

        if config is None:
            config_file = os.path.join(self._state_dir, CONFIG_FILENAME)
            config = ConfigObj(infile=(config_file if os.path.exists(config_file) else None),
                               configspec=CONFIG_SPEC_PATH, default_encoding='utf-8')
        self.config = config
        self.validate()

        # set defaults downloads path
        if not self.config['download_defaults']['saveas']:
            self.config['download_defaults']['saveas'] = get_default_dest_dir()
        self.selected_ports = {}

    def abspath(self, path):
        return path if os.path.isabs(path) else os.path.join(self.get_state_dir(), path)

    def norm_path(self, path):
        """
        Return absolute path if it points outside the state dir. Otherwise, change it to relative path.
        """
        if os.path.isabs(path):
            base_path = self.get_state_dir()
            if base_path == os.path.commonprefix([path, base_path]):
                return os.path.relpath(path, base_path)
        return path

    @staticmethod
    def load(config_path=None):
        """
        Load a TriblerConfig from disk.
        """
        return TriblerConfig(ConfigObj(config_path, configspec=CONFIG_SPEC_PATH, default_encoding='utf-8'))

    def copy(self):
        """
        Return a TriblerConfig object that has the same values.
        """
        # References to the sections are copied here
        new_configobj = ConfigObj(self.config.copy(), configspec=self.config.configspec, default_encoding='utf-8')
        # Make a deep copy of every section
        for section in self.config:
            new_configobj[section] = self.config[section].copy()
        return TriblerConfig(new_configobj)

    def validate(self):
        """
        Validate the ConfigObj using Validator.

        Note that `validate()` returns `True` if the ConfigObj is correct and a dictionary with `True` and `False`
        values for keys who's validation failed if at least one key was found to be incorrect.
        """
        validator = Validator()
        validation_result = self.config.validate(validator)
        if validation_result is not True:
            raise InvalidConfigException(msg="TriblerConfig is invalid: %s" % str(validation_result))

    def write(self):
        """
        Write the configuration to the config file in the state dir as specified in the config.
        """
        if not os.path.exists(self.get_state_dir()):
            os.makedirs(self.get_state_dir())
        self.config.filename = os.path.join(self.get_state_dir(), CONFIG_FILENAME)
        self.config.write()

    @staticmethod
    def get_default_state_dir(home_dir_postfix=u'.Tribler'):
        """Get the default application state directory."""
        if 'TSTATEDIR' in os.environ:
            path = os.environ['TSTATEDIR']
            return path if os.path.isabs(path) else os.path.join(os.getcwd(), path)

        return os.path.join(get_appstate_dir(), home_dir_postfix)

    def _obtain_port(self, section, option):
        """
        Fetch a port setting from the config file and in case it's set to -1 (random), look for a free port
        and assign it to this particular setting.
        """
        settings_port = self.config[section][option]
        path = section + '~' + option
        in_selected_ports = path in self.selected_ports

        if in_selected_ports or settings_port == -1:
            return self._get_random_port(path)
        return settings_port

    def _get_random_port(self, path):
        """Get a random port which is not already selected."""
        if path not in self.selected_ports:
            self.selected_ports[path] = get_random_port()
            self._logger.debug(u"Get random port %d for [%s]", self.selected_ports[path], path)
        return self.selected_ports[path]

    # Chant
    def set_chant_enabled(self, value):
        self.config['chant']['enabled'] = bool(value)

    def get_chant_enabled(self):
        return self.config['chant']['enabled']

    def set_chant_channels_dir(self, chant_db_filename):
        self.config['chant']['channels_dir'] = self.norm_path(chant_db_filename)

    def get_chant_channels_dir(self):
        return self.abspath(self.config['chant']['channels_dir'])

    def set_state_dir(self, state_dir):
        self._state_dir = state_dir

    def get_state_dir(self):
        return cast_to_unicode_utf8(self._state_dir)

    def set_trustchain_keypair_filename(self, keypairfilename):
        self.config['trustchain']['ec_keypair_filename'] = self.norm_path(keypairfilename)

    def get_trustchain_keypair_filename(self):
        return self.abspath(self.config['trustchain']['ec_keypair_filename'])

    def set_trustchain_testnet_keypair_filename(self, keypairfilename):
        self.config['trustchain']['testnet_keypair_filename'] = self.norm_path(keypairfilename)

    def get_trustchain_testnet_keypair_filename(self):
        return self.abspath(self.config['trustchain']['testnet_keypair_filename'])

    def set_trustchain_enabled(self, value):
        self.config['trustchain']['enabled'] = value

    def get_trustchain_enabled(self):
        return self.config['trustchain']['enabled']

    def set_trustchain_live_edges_enabled(self, value):
        self.config['trustchain']['live_edges_enabled'] = value

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

    def get_trustchain_live_edges_enabled(self):
        return self.config['trustchain']['live_edges_enabled']

    def set_log_dir(self, value):
        self.config['general']['log_dir'] = self.norm_path(value)

    def get_log_dir(self):
        return self.abspath(self.config['general']['log_dir'])

    def set_testnet(self, value):
        self.config['general']['testnet'] = value

    def get_testnet(self):
        return 'TESTNET' in os.environ or self.config['general']['testnet']

    # Version Checker
    def set_version_checker_enabled(self, value):
        self.config['general']['version_checker_enabled'] = value

    def get_version_checker_enabled(self):
        if 'version_checker_enabled' not in self.config['general']:
            return True
        return self.config['general']['version_checker_enabled']

    # Torrent checking

    def set_torrent_checking_enabled(self, value):
        self.config['torrent_checking']['enabled'] = value

    def get_torrent_checking_enabled(self):
        return self.config['torrent_checking']['enabled']

    # HTTP API

    def set_http_api_enabled(self, http_api_enabled):
        self.config['http_api']['enabled'] = http_api_enabled

    def get_http_api_enabled(self):
        return self.config['http_api']['enabled']

    def set_http_api_port(self, http_api_port):
        self.config['http_api']['port'] = http_api_port

    def get_http_api_port(self):
        return self._obtain_port('http_api', 'port')

    def set_http_api_retry_port(self, retry_port):
        self.config['http_api']['retry_port'] = retry_port

    def get_http_api_retry_port(self):
        return self.config['http_api']['retry_port']

    # IPv8

    def set_ipv8_enabled(self, value):
        self.config['ipv8']['enabled'] = value

    def get_ipv8_enabled(self):
        return self.config['ipv8']['enabled']

    def set_ipv8_port(self, value):
        self.config['ipv8']['port'] = value

    def get_ipv8_port(self):
        return self._obtain_port('ipv8', 'port')

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

    def set_libtorrent_port_runtime(self, port):
        self.selected_ports['~'.join(('libtorrent', 'port'))] = port

    def get_libtorrent_port(self):
        return self._obtain_port('libtorrent', 'port')

    def set_anon_listen_port(self, listen_port=None):
        self.config['libtorrent']['anon_listen_port'] = listen_port

    def get_anon_listen_port(self):
        return self._obtain_port('libtorrent', 'anon_listen_port')

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
        return self.config['libtorrent'].as_int('max_upload_rate')

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
        return self.config['libtorrent'].as_int('max_download_rate')

    def set_libtorrent_dht_enabled(self, value):
        self.config['libtorrent']['dht'] = value

    def get_libtorrent_dht_enabled(self):
        return self.config['libtorrent']['dht']

    # Video server

    def set_video_server_enabled(self, value):
        self.config['video_server']['enabled'] = value

    def get_video_server_enabled(self):
        return self.config['video_server']['enabled']

    def set_video_server_port(self, port):
        self.config['video_server']['port'] = port

    def get_video_server_port(self):
        return self._obtain_port('video_server', 'port')

    # Tunnel Community

    def set_tunnel_community_enabled(self, value):
        self.config['tunnel_community']['enabled'] = value

    def get_tunnel_community_enabled(self):
        return self.config['tunnel_community']['enabled']

    def set_tunnel_community_socks5_listen_ports(self, ports):
        self.config['tunnel_community']['socks5_listen_ports'] = [str(port) for port in ports]

    def get_tunnel_community_socks5_listen_ports(self):
        ports = self.config['tunnel_community']['socks5_listen_ports']
        path = u'tunnel_community~socks5_listen_ports~'
        return [self._get_random_port(path + text_type(index))
                if int(port) < 0 else int(port) for index, port in enumerate(ports)]

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
        self.config['download_defaults']['saveas'] = self.norm_path(value)

    def get_default_destination_dir(self):
        return self.abspath(self.config['download_defaults']['saveas'])

    def set_default_add_download_to_channel(self, value):
        self.config['download_defaults']['add_download_to_channel'] = value

    def get_default_add_download_to_channel(self):
        return self.config['download_defaults']['add_download_to_channel']

    # Market Community

    def set_market_community_enabled(self, value):
        self.config['market_community']['enabled'] = value

    def get_market_community_enabled(self):
        return self.config['market_community']['enabled']

    def set_is_matchmaker(self, value):
        self.config['market_community']['matchmaker'] = value

    def get_is_matchmaker(self):
        return self.config['market_community']['matchmaker']

    def set_record_transactions(self, value):
        self.config['market_community']['record_transactions'] = value

    def get_record_transactions(self):
        return self.config['market_community']['record_transactions']

    # DHT

    def set_dht_enabled(self, value):
        self.config['dht']['enabled'] = value

    def get_dht_enabled(self):
        return self.config['dht']['enabled']

    # Wallets

    def set_dummy_wallets_enabled(self, value):
        self.config['wallets']['dummy_wallets_enabled'] = value

    def get_dummy_wallets_enabled(self):
        return self.config['wallets']['dummy_wallets_enabled']

    def set_bitcoinlib_enabled(self, value):
        self.config['wallets']['bitcoinlib_enabled'] = value

    def get_bitcoinlib_enabled(self):
        return self.config['wallets']['bitcoinlib_enabled']

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

    # Credit mining
    def set_credit_mining_enabled(self, value):
        self.config['credit_mining']['enabled'] = value

    def get_credit_mining_enabled(self):
        return self.config['credit_mining']['enabled']

    def set_credit_mining_sources(self, source_list):
        self.config['credit_mining']['sources'] = source_list

    def get_credit_mining_sources(self):
        return self.config['credit_mining']['sources']

    def set_credit_mining_disk_space(self, value):
        self.config['credit_mining']['max_disk_space'] = value

    def get_credit_mining_disk_space(self):
        return self.config['credit_mining']['max_disk_space']

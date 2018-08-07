"""
Configuration object for the Tribler Core.
"""
import logging
import os

from configobj import ConfigObj
from validate import Validator

from Tribler.Core.Utilities.install_dir import get_lib_path
from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Core.exceptions import InvalidConfigException
from Tribler.Core.osutils import get_appstate_dir
from Tribler.Core.DownloadConfig import get_default_dest_dir

FILENAME = 'triblerd.conf'
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

        if config is None:
            file_name = os.path.join(self.get_default_state_dir(), FILENAME)
            if os.path.exists(file_name):
                config = ConfigObj(file_name, configspec=CONFIG_SPEC_PATH, encoding='latin_1')
            else:
                config = ConfigObj(configspec=CONFIG_SPEC_PATH, encoding='latin_1')
        self.config = config
        self.validate()

        # set defaults downloads path
        if not self.config['download_defaults']['saveas']:
            self.config['download_defaults']['saveas'] = get_default_dest_dir()
        self.selected_ports = {}

    @staticmethod
    def load(config_path=None):
        """
        Load a TriblerConfig from disk.
        """
        return TriblerConfig(ConfigObj(config_path, configspec=CONFIG_SPEC_PATH, encoding='latin_1'))

    def copy(self):
        """
        Return a TriblerConfig object that has the same values.
        """
        # References to the sections are copied here
        new_configobj = ConfigObj(self.config.copy(), configspec=self.config.configspec, encoding='latin_1')
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
        with open(os.path.join(self.get_state_dir(), FILENAME), 'w') as outfile:
            self.config.write(outfile=outfile)

    @staticmethod
    def get_default_state_dir(home_dir_postfix=u'.Tribler'):
        """Get the default application state directory."""
        if 'TSTATEDIR' in os.environ:
            return os.environ['TSTATEDIR']

        if os.path.isdir(home_dir_postfix):
            return os.path.abspath(home_dir_postfix)

        application_directory = get_appstate_dir()
        return os.path.join(application_directory, home_dir_postfix)

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

    # General
    def set_chant_channel_edit(self, value):
        self.config['general']['chant_channel_edit'] = bool(value)

    def get_chant_channel_edit(self):
        return self.config['general'].as_bool('chant_channel_edit')

    def set_family_filter_enabled(self, value):
        self.config['general']['family_filter'] = bool(value)

    def get_family_filter_enabled(self):
        return self.config['general'].as_bool('family_filter')

    def set_state_dir(self, state_dir):
        self.config["general"]["state_dir"] = state_dir

    def get_state_dir(self):
        if not self.config["general"]["state_dir"]:
            self.set_state_dir(TriblerConfig.get_default_state_dir())

        return self.config["general"]["state_dir"]

    def set_permid_keypair_filename(self, keypair_filename):
        self.config['general']['ec_keypair_filename'] = keypair_filename

    def get_permid_keypair_filename(self):
        file_name = self.config["general"]["ec_keypair_filename"]
        if not file_name:
            file_name = os.path.join(self.get_state_dir(), 'ec.pem')
            self.set_permid_keypair_filename(file_name)
        return file_name

    def set_trustchain_keypair_filename(self, keypairfilename):
        self.config['trustchain']['ec_keypair_filename'] = keypairfilename

    def get_trustchain_keypair_filename(self):
        file_name = self.config['trustchain']['ec_keypair_filename']
        if not file_name:
            file_name = os.path.join(self.get_state_dir(), 'ec_multichain.pem')
            self.set_trustchain_keypair_filename(file_name)
        return file_name

    def set_trustchain_testnet_keypair_filename(self, keypairfilename):
        self.config['trustchain']['testnet_keypair_filename'] = keypairfilename

    def get_trustchain_testnet_keypair_filename(self):
        file_name = self.config['trustchain']['testnet_keypair_filename']
        if not file_name:
            file_name = os.path.join(self.get_state_dir(), 'ec_trustchain_testnet.pem')
            self.set_trustchain_testnet_keypair_filename(file_name)
        return file_name

    def set_trustchain_enabled(self, value):
        self.config['trustchain']['enabled'] = value

    def get_trustchain_enabled(self):
        return self.config['trustchain']['enabled']

    def set_trustchain_live_edges_enabled(self, value):
        self.config['trustchain']['live_edges_enabled'] = value

    def get_trustchain_live_edges_enabled(self):
        return self.config['trustchain']['live_edges_enabled']

    def set_megacache_enabled(self, value):
        self.config['general']['megacache'] = value

    def get_megacache_enabled(self):
        return self.config['general']['megacache']

    def set_log_dir(self, value):
        self.config['general']['log_dir'] = value

    def get_log_dir(self):
        log_dir = self.config['general']['log_dir']
        return os.path.join(self.get_state_dir(), 'logs') if (not log_dir or log_dir == 'None') else log_dir

    def set_testnet(self, value):
        self.config['general']['testnet'] = value

    def get_testnet(self):
        return self.config['general']['testnet']

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

    # Dispersy

    def set_dispersy_enabled(self, value):
        self.config['dispersy']['enabled'] = value

    def get_dispersy_enabled(self):
        return self.config['dispersy']['enabled']

    def set_dispersy_port(self, value):
        self.config['dispersy']['port'] = value

    def get_dispersy_port(self):
        return self._obtain_port('dispersy', 'port')

    # IPv8

    def set_ipv8_enabled(self, value):
        self.config['ipv8']['enabled'] = value

    def get_ipv8_enabled(self):
        return self.config['ipv8']['enabled']

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
        self.config['libtorrent']['proxy_server'] = server if proxy_type else None
        self.config['libtorrent']['proxy_auth'] = auth if proxy_type in [3, 5] else None

    def get_libtorrent_proxy_settings(self):
        return (self.config['libtorrent']['proxy_type'],
                self.config['libtorrent']['proxy_server'],
                self.config['libtorrent']['proxy_auth'])

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

    # Mainline DHT

    def set_mainline_dht_enabled(self, value):
        self.config['mainline_dht']['enabled'] = value

    def get_mainline_dht_enabled(self):
        return self.config['mainline_dht']['enabled']

    def set_mainline_dht_port(self, port):
        self.config['mainline_dht']['port'] = port

    def get_mainline_dht_port(self):
        return self._obtain_port('mainline_dht', 'port')

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
        return [self._get_random_port(path + unicode(index))
                if int(port) < 0 else int(port) for index, port in enumerate(ports)]

    def set_tunnel_community_exitnode_enabled(self, value):
        self.config['tunnel_community']['exitnode_enabled'] = value

    def get_tunnel_community_exitnode_enabled(self):
        return self.config['tunnel_community']['exitnode_enabled']

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
        self.config['download_defaults']['saveas'] = value

    def get_default_destination_dir(self):
        return self.config['download_defaults']['saveas']

    # Market Community

    def set_market_community_enabled(self, value):
        self.config['market_community']['enabled'] = value

    def get_market_community_enabled(self):
        return self.config['market_community']['enabled']

    def set_is_matchmaker(self, value):
        self.config['market_community']['matchmaker'] = value

    def get_is_matchmaker(self):
        return self.config['market_community']['matchmaker']

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

    # Torrent store

    def get_torrent_store_enabled(self):
        return self.config['torrent_store']['enabled']

    def set_torrent_store_enabled(self, value):
        self.config['torrent_store']['enabled'] = value

    def get_torrent_store_dir(self):
        return os.path.join(self.get_state_dir(), self.config['torrent_store']['store_dir'])

    def set_torrent_store_dir(self, value):
        self.config['torrent_store']['store_dir'] = value

    # Metadata

    def get_metadata_enabled(self):
        return self.config['metadata']['enabled']

    def set_metadata_enabled(self, mode):
        self.config['metadata']['enabled'] = mode

    def get_metadata_store_dir(self):
        return os.path.join(self.get_state_dir(), self.config['metadata']['store_dir'])

    def set_metadata_store_dir(self, value):
        self.config['metadata']['store_dir'] = value

    # Torrent collecting

    def set_torrent_collecting_enabled(self, value):
        self.config['torrent_collecting']['enabled'] = value

    def get_torrent_collecting_enabled(self):
        return self.config['torrent_collecting']['enabled']

    def set_torrent_collecting_max_torrents(self, value):
        self.config['torrent_collecting']['max_torrents'] = value

    def get_torrent_collecting_max_torrents(self):
        return self.config['torrent_collecting']['max_torrents']

    def set_torrent_collecting_dir(self, value):
        self.config['torrent_collecting']['directory'] = value

    def get_torrent_collecting_dir(self):
        return self.config['torrent_collecting']['directory']

    # Search Community

    def set_torrent_search_enabled(self, mode):
        self.config['search_community']['enabled'] = mode

    def get_torrent_search_enabled(self):
        return self.config['search_community']['enabled']

    # AllChannel Community

    def set_channel_search_enabled(self, mode):
        self.config['allchannel_community']['enabled'] = mode

    def get_channel_search_enabled(self):
        return self.config['allchannel_community']['enabled']

    # Channel Community

    def set_channel_community_enabled(self, value):
        self.config['channel_community']['enabled'] = value

    def get_channel_community_enabled(self):
        return self.config['channel_community']['enabled']

    # PreviewChannel Community

    def set_preview_channel_community_enabled(self, value):
        self.config['preview_channel_community']['enabled'] = value

    def get_preview_channel_community_enabled(self):
        return self.config['preview_channel_community']['enabled']

    # Watch folder

    def set_watch_folder_enabled(self, value):
        self.config['watch_folder']['enabled'] = value

    def get_watch_folder_enabled(self):
        return self.config['watch_folder']['enabled']

    def set_watch_folder_path(self, value):
        self.config['watch_folder']['directory'] = value

    def get_watch_folder_path(self):
        return self.config['watch_folder']['directory']

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

from distutils.spawn import find_executable
import logging
import os
import sys
from configobj import ConfigObj
from validate import Validator

from Tribler.Core.Utilities.install_dir import determine_install_dir
from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Core.osutils import get_appstate_dir, is_android
from Tribler.Core.simpledefs import STATEDIR_CONFIG, STATEDIR_CONFIGSPEC
from Tribler.Policies.BoostingPolicy import RandomPolicy, SeederRatioPolicy, BoostingPolicy
from Tribler.Policies.BoostingPolicy import CreationDatePolicy


CONFIGSPEC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), STATEDIR_CONFIGSPEC)


class TriblerConfig(object):

    def __init__(self, config=None):
        self.selected_ports = {}
        self._logger = logging.getLogger(self.__class__.__name__)

        if config:
            self.config = config
        else:
            self.config = ConfigObj(configspec=CONFIGSPEC_PATH)

        self.validate()
        self._set_video_analyser_path()

    @staticmethod
    def load(config_path=None):
        """
        Load a TriblerConfig from disk.
        """
        tribler_config = TriblerConfig()

        if not config_path:
            config_path = os.path.join(TriblerConfig.get_default_state_dir(), STATEDIR_CONFIG)

        if not os.path.exists(TriblerConfig.get_default_state_dir()):
            os.mkdir(TriblerConfig.get_default_state_dir())

        tribler_config.config = ConfigObj(config_path, configspec=CONFIGSPEC_PATH)
        tribler_config.validate()

        return tribler_config

    def copy(self):
        """
        Return a TriblerConfig object that has the same values.
        """
        cpy_config = TriblerConfig()
        for section in self.config:
            for key in self.config[section]:
                cpy_config.config[section][key] = self.config[section][key]

        return cpy_config

    def validate(self):
        # TODO do something when validation fails
        validator = Validator()
        self.config.validate(validator, copy=True)

    @staticmethod
    def get_default_state_dir(homedirpostfix=u'.Tribler'):
        statedirvar = u'${TSTATEDIR}'
        statedir = os.path.expandvars(statedirvar)
        if statedir and statedir != statedirvar:
            return statedir

        if os.path.isdir(homedirpostfix):
            return os.path.abspath(homedirpostfix)

        appdir = get_appstate_dir()
        return os.path.join(appdir, homedirpostfix)

    def _obtain_port(self, section, option):
        """ Fetch a port setting from the config file and in case it's set to -1 (random), look for a free port
        and assign it to this particular setting.
        """
        settings_port = self.config[section][option]
        path = section + '~' + option
        in_selected_ports = path in self.selected_ports

        if in_selected_ports or settings_port == -1:
            return self._get_random_port(path)
        return settings_port

    def _get_random_port(self, path):
        if path not in self.selected_ports:
            self.selected_ports[path] = get_random_port()
            self._logger.debug(u"Get random port %d for [%s]", self.selected_ports[path], path)
        return self.selected_ports[path]

    def _set_video_analyser_path(self):
        if sys.platform == 'win32':
            # TODO(emilon): This is to work around the case where windows has
            # non-ASCI chars on %PATH% contents. Should be removed if we migrate to
            # python 3.
            from Tribler.Main.hacks import get_environment_variable
            path_env = get_environment_variable(u"PATH")
        elif is_android():
            path_env = unicode(os.environ["PYTHONPATH"])
        else:
            path_env = os.environ["PATH"]

        # Set video_analyser_path
        if sys.platform == 'win32':
            ffmpegname = u"ffmpeg.exe"
        elif sys.platform == 'darwin':
            ffmpegname = u"ffmpeg"
        elif find_executable("avconv", path_env):
            ffmpegname = u"avconv"
        else:
            ffmpegname = u"ffmpeg"

        ffmpegpath = find_executable(ffmpegname, path_env)

        if ffmpegpath is None:
            if sys.platform == 'darwin':
                self.config['general']['videoanalyserpath'] = "vlc/ffmpeg"
            else:
                self.config['general']['videoanalyserpath'] = os.path.abspath(ffmpegname)
        else:
            self.config['general']['videoanalyserpath'] = os.path.abspath(ffmpegpath)

    def write(self):
        """
        Write the configuration to the config file in the state dir as specified in the config.
        """
        with open(os.path.join(self.get_state_dir(), STATEDIR_CONFIG), 'w') as outfile:
            self.config.write(outfile=outfile)

    # General

    def set_family_filter_enabled(self, value):
        self.config['general']['family_filter'] = value

    def get_family_filter_enabled(self):
        return self.config['general']['family_filter']

    def set_install_dir(self, installdir):
        self.config['general']['install_dir'] = installdir

    def get_install_dir(self):
        install_dir = self.config['general']['install_dir']
        if install_dir == '.':
            install_dir = determine_install_dir()
            self.set_install_dir(install_dir)
        return install_dir

    def set_state_dir(self, state_dir):
        self.config["general"]["state_dir"] = state_dir

    def get_state_dir(self):
        if not self.config["general"]["state_dir"]:
            self.set_state_dir(TriblerConfig.get_default_state_dir())

        return self.config["general"]["state_dir"]

    def set_permid_keypair_filename(self, keypairfilename):
        self.config['general']['ec_keypair_filename'] = keypairfilename

    def get_permid_keypair_filename(self):
        file_name = self.config["general"]["ec_keypair_filename"]
        if not file_name:
            file_name = os.path.join(self.get_state_dir(), 'ec.pem')
            self.set_permid_keypair_filename(file_name)
        return file_name

    def set_multichain_permid_keypair_filename(self, keypairfilename):
        self.config['multichain']['ec_keypair_filename_multichain'] = keypairfilename

    def get_multichain_permid_keypair_filename(self):
        file_name = self.config['multichain']['ec_keypair_filename_multichain']
        if not file_name:
            file_name = os.path.join(self.get_state_dir(), 'ec_multichain.pem')
            self.set_multichain_permid_keypair_filename(file_name)
        return file_name

    def set_megacache_enabled(self, value):
        self.config['general']['megacache'] = value

    def get_megacache_enabled(self):
        return self.config['general']['megacache']

    def set_video_analyser_path(self, value):
        self.config['general']['videoanalyserpath'] = value

    def get_video_analyser_path(self):
        return self.config['general']['videoanalyserpath']

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

    def set_libtorrent_proxy_settings(self, ptype, server=None, auth=None):
        """ Set which proxy LibTorrent should use (default = 0).
        @param ptype Integer (0 = no proxy server, 1 = SOCKS4, 2 = SOCKS5, 3 = SOCKS5 + auth, 4 = HTTP, 5 = HTTP + auth)
        @param server (host, port) tuple or None
        @param auth (username, password) tuple or None
        """
        self.config['libtorrent']['lt_proxytype'] = ptype
        self.config['libtorrent']['lt_proxyserver'] = server if ptype else None
        self.config['libtorrent']['lt_proxyauth'] = auth if ptype in [3, 5] else None

    def get_libtorrent_proxy_settings(self):
        return (self.config['libtorrent']['lt_proxytype'],
                self.config['libtorrent']['lt_proxyserver'],
                self.config['libtorrent']['lt_proxyauth'])

    def set_anon_proxy_settings(self, ptype, server=None, auth=None):
        """
        @param ptype Integer (0 = no proxy server, 1 = SOCKS4, 2 = SOCKS5, 3 = SOCKS5 + auth, 4 = HTTP, 5 = HTTP + auth)
        @param server (host, [ports]) tuple or None
        @param auth (username, password) tuple or None
        """
        self.config['libtorrent']['anon_proxytype'] = ptype
        self.config['libtorrent']['anon_proxyserver'] = server if ptype else None
        self.config['libtorrent']['anon_proxyauth'] = auth if ptype in [3, 5] else None

    def get_anon_proxy_settings(self):
        return (self.config['libtorrent']['anon_proxytype'],
                self.config['libtorrent']['anon_proxyserver'],
                self.config['libtorrent']['anon_proxyauth'])

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
        self.config['tunnel_community']['socks5_listen_ports'] = ports

    def get_tunnel_community_socks5_listen_ports(self):
        ports = self.config['tunnel_community']['socks5_listen_ports']
        path = u'tunnel_community~socks5_listen_ports~'
        return [self._get_random_port(path + unicode(index))
                if int(port) < 0 else int(port) for index, port in enumerate(ports)]

    def set_tunnel_community_exitnode_enabled(self, value):
        self.config['tunnel_community']['exitnode_enabled'] = value

    def get_tunnel_community_exitnode_enabled(self):
        return self.config['tunnel_community']['exitnode_enabled']

    # Upgrader

    def set_upgrader_enabled(self, should_upgrade):
        self.config['upgrader']['enabled'] = should_upgrade

    def get_upgrader_enabled(self):
        return self.config['upgrader']['enabled']

    # Torrent store

    def get_torrent_store(self):
        return self.config['torrent_store']['enabled']

    def set_torrent_store(self, value):
        self.config['torrent_store']['enabled'] = value

    def get_torrent_store_dir(self):
        return self.config['torrent_store']['store_dir']

    def set_torrent_store_dir(self, value):
        self.config['torrent_store']['store_dir'] = value

    # Metadata

    def get_metadata_enabled(self):
        return self.config['metadata']['enabled']

    def set_metadata_enabled(self, mode):
        self.config['metadata']['enabled'] = mode

    def get_metadata_store_dir(self):
        return self.config['metadata']['store_dir']

    def set_metadata_store_dir(self, value):
        self.config['metadata']['store_dir'] = value

    # Torrent collecting

    def set_torrent_collecting_enabled(self, value):
        self.config['torrent_collecting']['enabled'] = value

    def get_torrent_collecting_enabled(self):
        return self.config['torrent_collecting']['enabled']

    def set_torrent_collecting_max_torrents(self, value):
        self.config['torrent_collecting']['torrent_collecting_max_torrents'] = value

    def get_torrent_collecting_max_torrents(self):
        return self.config['torrent_collecting']['torrent_collecting_max_torrents']

    def set_torrent_collecting_dir(self, value):
        self.config['torrent_collecting']['torrent_collecting_dir'] = value

    def get_torrent_collecting_dir(self):
        return self.config['torrent_collecting']['torrent_collecting_dir']

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

    # BarterCommunity settings

    def set_barter_community_enabled(self, value):
        self.config['barter_community']['enabled'] = value

    def get_barter_community_enabled(self):
        return self.config['barter_community']['enabled']

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

    # Multichain Community

    def set_multichain_enabled(self, value):
        self.config['multichain']['enabled'] = value

    def get_multichain_enabled(self):
        return self.config['multichain']['enabled']

    # Watch folder

    def set_watch_folder_enabled(self, value):
        self.config['watch_folder']['enabled'] = value

    def get_watch_folder_enabled(self):
        return self.config['watch_folder']['enabled']

    def set_watch_folder_path(self, value):
        self.config['watch_folder']['watch_folder_dir'] = value

    def get_watch_folder_path(self):
        return self.config['watch_folder']['watch_folder_dir']

    # Download state

    def get_download_state(self, infohash):
        if infohash.encode('hex') in self.config["user_download_states"]:
            return self.config["user_download_states"][infohash.encode('hex')]
        return None

    def remove_download_state(self, infohash):
        if infohash.encode('hex') in self.config["user_download_states"]:
            del self.config["user_download_states"][infohash.encode('hex')]

    def set_download_state(self, infohash, value):
        self.config["user_download_states"][infohash.encode('hex')] = value

    def get_download_states(self):
        return dict((key.decode('hex'), value) for key, value in self.config["user_download_states"].iteritems())

    # Credit mining

    def set_credit_mining_enabled(self, value):
        self.config['credit_mining']['enabled'] = value

    def get_credit_mining_enabled(self):
        return self.config['credit_mining']['enabled']

    def set_credit_mining_max_torrents_per_source(self, value):
        self.config['credit_mining']['max_torrents_per_source'] = value

    def get_credit_mining_max_torrents_per_source(self):
        return self.config['credit_mining']['max_torrents_per_source']

    def set_credit_mining_max_torrents_active(self, value):
        self.config['credit_mining']['max_torrents_active'] = value

    def get_credit_mining_max_torrents_active(self):
        return self.config['credit_mining']['max_torrents_active']

    def set_credit_mining_source_interval(self, value):
        self.config['credit_mining']['source_interval'] = value

    def get_credit_mining_source_interval(self):
        return self.config['credit_mining']['source_interval']

    def set_credit_mining_swarm_interval(self, swarm_interval):
        self.config['credit_mining']['swarm_interval'] = swarm_interval

    def get_credit_mining_swarm_interval(self):
        return self.config['credit_mining']['swarm_interval']

    def set_credit_mining_share_mode_target(self, value):
        self.config['credit_mining']['share_mode_target'] = value

    def get_credit_mining_share_mode_target(self):
        return self.config['credit_mining']['share_mode_target']

    def set_credit_mining_tracker_interval(self, value):
        self.config['credit_mining']['tracker_interval'] = value

    def get_credit_mining_tracker_interval(self):
        return self.config['credit_mining']['tracker_interval']

    def set_credit_mining_logging_interval(self, value):
        self.config['credit_mining']['logging_interval'] = value

    def get_credit_mining_logging_interval(self):
        return self.config['credit_mining']['logging_interval']

    def set_credit_mining_sources(self, source_list, key):
        """
        set source list for a chosen key: boosting_sources, boosting_enabled, boosting_disabled, or archive_sources
        """
        self.config['credit_mining']['%s' % key] = source_list

    def get_credit_mining_sources(self):
        return {"boosting_sources": self.config['credit_mining']['boosting_sources'],
                "boosting_enabled": self.config['credit_mining']['boosting_enabled'],
                "boosting_disabled": self.config['credit_mining']['boosting_disabled'],
                "archive_sources": self.config['credit_mining']['archive_sources']}

    def set_credit_mining_policy(self, policy):
        switch_policy = {
            RandomPolicy: "random",
            CreationDatePolicy: "creation",
            SeederRatioPolicy: "seederratio"
        }

        if isinstance(policy, BoostingPolicy):
            policy = switch_policy[type(policy)]

        self.config['credit_mining']['policy'] = policy

    def get_credit_mining_policy(self, as_class=False):
        """
        Get the credit mining policy.
        If as_class True, will return as a class, otherwise, it will return as policy name (a string)
        """
        policy_str = self.config['credit_mining']['policy']

        if as_class:
            switch_policy = {
                "random": RandomPolicy,
                "creation": CreationDatePolicy,
                "seederratio": SeederRatioPolicy
            }

            return switch_policy[policy_str]

        return policy_str

"""
Configure parameters of a Session.

Author(s): Arno Bakker, Egbert Bouman
"""
import logging
import os
import os.path
import sys
from distutils.spawn import find_executable
from shutil import copyfile

from Tribler.Core.CreditMining.BoostingPolicy import CreationDatePolicy, SeederRatioPolicy, RandomPolicy, BoostingPolicy
from Tribler.Core.Utilities.configparser import CallbackConfigParser
from Tribler.Core.Utilities.install_dir import determine_install_dir
from Tribler.Core.Utilities.network_utils import autodetect_socket_style, get_random_port
from Tribler.Core.defaults import sessdefaults
from Tribler.Core.osutils import get_appstate_dir, is_android
from Tribler.Core.simpledefs import STATEDIR_SESSCONFIG


class SessionConfigInterface(object):

    """
    (key,value) pair config of global parameters,
    e.g. PermID keypair, listen port, max upload speed, etc.

    Use SessionStartupConfig from creating and manipulation configurations
    before session startup time. This is just a parent class.
    """

    def __init__(self, sessconfig=None):
        """ Constructor.
        @param sessconfig Optional dictionary used internally
        to make this a copy constructor.
        """
        self._logger = logging.getLogger(self.__class__.__name__)

        self.selected_ports = {}
        self.sessconfig = sessconfig or CallbackConfigParser()

        # Poor man's versioning of SessionConfig, add missing default values.
        for section, sect_dict in sessdefaults.iteritems():
            if not self.sessconfig.has_section(section):
                self.sessconfig.add_section(section)
            for k, v in sect_dict.iteritems():
                if not self.sessconfig.has_option(section, k):
                    self.sessconfig.set(section, k, v)

        if not sessconfig:
            return

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
                self.sessconfig.set(u'general', u'videoanalyserpath', u"vlc/ffmpeg")
            else:
                self.sessconfig.set(u'general', u'videoanalyserpath', os.path.abspath(ffmpegname))
        else:
            self.sessconfig.set(u'general', u'videoanalyserpath', os.path.abspath(ffmpegpath))

        # Set videoplayer path
        if sys.platform == 'win32':
            videoplayerpath = os.path.expandvars('${PROGRAMFILES}') + '\\Windows Media Player\\wmplayer.exe'
        elif sys.platform == 'darwin':
            videoplayerpath = find_executable("vlc") or ("/Applications/VLC.app" if os.path.exists(
                "/Applications/VLC.app") else None) or "/Applications/QuickTime Player.app"
        else:
            videoplayerpath = find_executable("vlc") or "vlc"

        self.sessconfig.set(u'video', u'path', videoplayerpath)

        self.sessconfig.set(u'general', u'ipv6_binds_v4', autodetect_socket_style())

    #
    # Auxiliar functions
    #

    def _obtain_port(self, section, option):
        """ Fetch a port setting from the config file and in case it's set to -1 (random), look for a free port and assign it to
                this particular setting.
        """
        try:
            settings_port = int(self.sessconfig.get(section, option))
        except ValueError:
            self._logger.warning("Invalid port for section %s and option %s, resetting to default", section, option)
            settings_port = sessdefaults[section][option]
            self.sessconfig.set(section, option, settings_port)
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

    def set_state_dir(self, statedir):
        """ Set the directory to store the Session's state in.
        @param statedir  A preferably absolute path name. If the directory
        does not yet exist it will be created at Session create time.
        """
        self.sessconfig.set(u'general', u'state_dir', statedir)

    def get_state_dir(self):
        """ Returns the directory the Session stores its state in.
        @return An absolute path name. """

        in_config_path = self.sessconfig.get(u'general', u'state_dir')
        return in_config_path or self.get_default_state_dir()

    @staticmethod
    def get_default_state_dir(homedirpostfix=u'.Tribler'):
        # Allow override
        statedirvar = u'${TSTATEDIR}'
        statedir = os.path.expandvars(statedirvar)
        if statedir and statedir != statedirvar:
            return statedir

        if os.path.isdir(homedirpostfix):
            return os.path.abspath(homedirpostfix)

        appdir = get_appstate_dir()
        return os.path.join(appdir, homedirpostfix)

    def set_install_dir(self, installdir):
        """ Set the directory in which the Tribler Core software is installed.
        @param installdir An absolute path name
        """
        self.sessconfig.set(u'general', u'install_dir', installdir)

    def get_install_dir(self):
        """ Returns the directory the Tribler Core software is installed in.
        @return An absolute path name. """
        install_dir = self.sessconfig.get(u'general', u'install_dir')
        if install_dir == '.':
            install_dir = determine_install_dir()
            self.set_install_dir(install_dir)
        return install_dir

    def set_permid_keypair_filename(self, keypairfilename):
        """ Set the filename containing the Elliptic Curve keypair to use for
        PermID-based authentication in this Session.

        Note: if a Session is started with a SessionStartupConfig that
        points to an existing state dir and that state dir contains a saved
        keypair, that keypair will be used unless a different keypair is
        explicitly configured via this method.
        """
        self.sessconfig.set(u'general', u'eckeypairfilename', keypairfilename)

    def get_permid_keypair_filename(self):
        """ Returns the filename of the Session's keypair.
        @return An absolute path name. """
        file_name = self.sessconfig.get(u'general', u'eckeypairfilename')
        if not file_name:
            file_name = os.path.join(self.get_state_dir(), 'ec.pem')
            self.set_permid_keypair_filename(file_name)
        return file_name

    def set_multichain_permid_keypair_filename(self, keypairfilename):
        """ Set the filename containing the Elliptic Curve keypair to use for
        PermID-based authentication for multichain in this Session.

        Note: if a Session is started with a SessionStartupConfig that
        points to an existing state dir and that state dir contains a saved
        keypair, that keypair will be used unless a different keypair is
        explicitly configured via this method.
        """
        self.sessconfig.set(u'general', u'ec_keypair_filename_multichain', keypairfilename)

    def get_multichain_permid_keypair_filename(self):
        """ Returns the filename of the Session's multichain keypair.
        @return An absolute path name. """
        file_name = self.sessconfig.get(u'general', u'ec_keypair_filename_multichain')
        if not file_name:
            file_name = os.path.join(self.get_state_dir(), 'ec_multichain.pem')
            self.set_multichain_permid_keypair_filename(file_name)
        return file_name


    def set_listen_port(self, port):
        """ Set the UDP and TCP listen port for this Session.
        @param port A port number.
        """
        self.sessconfig.set(u'general', u'minport', port)
        self.sessconfig.set(u'general', u'maxport', port)

    def set_listen_port_runtime(self, port):
        """ Set the UDP and TCP listen port for this Session. This method is non-persistent.
        @param port A port number.
        """
        self.selected_ports['~'.join(('general', 'minport'))] = port

    #
    # Tunnel Community settings
    #

    def set_tunnel_community_socks5_listen_ports(self, ports):
        self.sessconfig.set(u'tunnel_community', u'socks5_listen_ports', ports)

    def get_tunnel_community_socks5_listen_ports(self):
        ports = self.sessconfig.get(u'tunnel_community', u'socks5_listen_ports')
        path = u'tunnel_community~socks5_listen_ports~'
        return [self._get_random_port(path + unicode(index)) if port < 0 else port for index, port in enumerate(ports)]

    def set_tunnel_community_exitnode_enabled(self, value):
        self.sessconfig.set(u'tunnel_community', u'exitnode_enabled', value)

    def get_tunnel_community_exitnode_enabled(self):
        """ Returns whether being an exitnode is allowed
        @return Boolean. """
        return self.sessconfig.get(u'tunnel_community', u'exitnode_enabled')

    def set_tunnel_community_enabled(self, value):
        """
        Enable or disable the tunnel community.
        :param value: A boolean indicating whether the tunnel community should be enabled
        """
        self.sessconfig.set(u'tunnel_community', u'enabled', value)

    def get_tunnel_community_enabled(self):
        """
        Returns whether the tunnel community is enabled.
        :return: A boolean indicating whether the tunnel community is enabled
        """
        return self.sessconfig.get(u'tunnel_community', u'enabled')

    #
    # Network settings
    #

    def get_listen_port(self):
        """ Returns the current UDP/TCP listen port.
        @return Port number. """
        return self._obtain_port(u'general', u'minport')

    def set_timeout_check_interval(self, timeout):
        self.sessconfig.set(u'general', u'timeout_check_interval', timeout)

    def get_timeout_check_interval(self):
        return self.sessconfig.get(u'general', u'timeout_check_interval')

    def set_timeout(self, timeout):
        self.sessconfig.set(u'general', u'timeout', timeout)

    def get_timeout(self):
        return self.sessconfig.get(u'general', u'timeout')

    def set_ipv6(self, enabled):
        self.sessconfig.set(u'general', u'ipv6_enabled', enabled)

    def get_ipv6(self):
        return self.sessconfig.get(u'general', u'ipv6_enabled')

    def set_ip(self, ip):
        self.sessconfig.set(u'general', u'ip', ip)

    def get_ip(self):
        return self.sessconfig.get(u'general', u'ip')

    #
    # Enable/disable Tribler features
    #
    def set_megacache(self, value):
        """ Enable megacache databases to cache peers, torrent files and
        preferences (default = True).
        @param value Boolean. """
        self.sessconfig.set(u'general', u'megacache', value)

    def get_megacache(self):
        """ Returns whether Megacache is enabled.
        @return Boolean. """
        return self.sessconfig.get(u'general', u'megacache')

    def set_libtorrent(self, value):
        """ Enable or disable LibTorrent (default = True).
        @param value Boolean.
        """
        self.sessconfig.set(u'libtorrent', u'enabled', value)

    def get_libtorrent(self):
        """ Returns whether LibTorrent is enabled.
        @return Boolean.
        """
        return self.sessconfig.get(u'libtorrent', u'enabled')

    def set_libtorrent_max_conn_download(self, value):
        """ Set the maximum amount of connections for each download. By default, this is -1, unlimited.
        @param value Integer.
        """
        self.sessconfig.set(u'libtorrent', u'max_connections_download', value)

    def get_libtorrent_max_conn_download(self):
        """ Returns the maximum amount of connections per download
        @return Integer.
        """
        return self.sessconfig.get(u'libtorrent', u'max_connections_download')

    def set_libtorrent_max_download_rate(self, value):
        """ Set the maximum download bandwidth for the libtorrent session. By default, this is 0, unlimited.
        @param value Integer.
        """
        self.sessconfig.set(u'libtorrent', u'max_download_rate', value)

    def get_libtorrent_max_download_rate(self):
        """ Returns the maximum download bandwidth for the libtorrent session.
        @return Integer.
        """
        return self.sessconfig.get(u'libtorrent', u'max_download_rate')

    def set_libtorrent_max_upload_rate(self, value):
        """ Set the maximum upload bandwidth for the libtorrent session. By default, this is 0, unlimited.
        @param value Integer.
        """
        self.sessconfig.set(u'libtorrent', u'max_upload_rate', value)

    def get_libtorrent_max_upload_rate(self):
        """ Returns the maximum upload bandwidth for the libtorrent session.
        @return Integer.
        """
        return self.sessconfig.get(u'libtorrent', u'max_upload_rate')

    def set_libtorrent_proxy_settings(self, ptype, server=None, auth=None):
        """ Set which proxy LibTorrent should use (default = 0).
        @param ptype Integer (0 = no proxy server, 1 = SOCKS4, 2 = SOCKS5, 3 = SOCKS5 + auth, 4 = HTTP, 5 = HTTP + auth)
        @param server (host, port) tuple or None
        @param auth (username, password) tuple or None
        """
        self.sessconfig.set(u'libtorrent', u'lt_proxytype', ptype)
        self.sessconfig.set(u'libtorrent', u'lt_proxyserver', server if ptype else None)
        self.sessconfig.set(u'libtorrent', u'lt_proxyauth', auth if ptype in [3, 5] else None)

    def get_libtorrent_proxy_settings(self):
        """ Returns which proxy LibTorrent is using.
        @return Tuple containing ptype, server, authentication values (as described in set_libtorrent_proxy_settings)
        """
        return (self.sessconfig.get(u'libtorrent', u'lt_proxytype'),
                self.sessconfig.get(u'libtorrent', u'lt_proxyserver'),
                self.sessconfig.get(u'libtorrent', u'lt_proxyauth'))

    def set_anon_proxy_settings(self, ptype, server=None, auth=None):
        """
        @param ptype Integer (0 = no proxy server, 1 = SOCKS4, 2 = SOCKS5, 3 = SOCKS5 + auth, 4 = HTTP, 5 = HTTP + auth)
        @param server (host, [ports]) tuple or None
        @param auth (username, password) tuple or None
        """
        self.sessconfig.set(u'libtorrent', u'anon_proxytype', ptype)
        self.sessconfig.set(u'libtorrent', u'anon_proxyserver', server if ptype else None)
        self.sessconfig.set(u'libtorrent', u'anon_proxyauth', auth if ptype in [3, 5] else None)

    def get_anon_proxy_settings(self):
        """
        @return: libtorrent anonymous settings
        """
        return (self.sessconfig.get(u'libtorrent', u'anon_proxytype'),
                self.sessconfig.get(u'libtorrent', u'anon_proxyserver'),
                self.sessconfig.get(u'libtorrent', u'anon_proxyauth'))

    def set_anon_listen_port(self, listen_port=None):
        self.sessconfig.set(u'libtorrent', u'anon_listen_port', listen_port)

    def get_anon_listen_port(self):
        return self._obtain_port(u'libtorrent', u'anon_listen_port')

    def set_libtorrent_utp(self, value):
        """ Enable or disable LibTorrent uTP (default = True).
        @param value Boolean.
        """
        self.sessconfig.set(u'libtorrent', u'utp', value)

    def get_libtorrent_utp(self):
        """ Returns whether LibTorrent uTP is enabled.
        @return Boolean.
        """
        return self.sessconfig.get(u'libtorrent', u'utp')

    #
    # Torrent file store
    #
    def get_torrent_store(self):
        """ Returns whether to enable the torrent store.
        @return Boolean. """
        return self.sessconfig.get(u'torrent_store', u'enabled')

    def set_torrent_store(self, value):
        """ Store torrent files in a leveldb database (default = True).
        @param value Boolean.
        """
        self.sessconfig.set(u'torrent_store', u'enabled', value)

    def get_torrent_store_dir(self):
        """ Returns the torrent store directory.
        @return str
        """
        return self.sessconfig.get(u'torrent_store', u'dir')

    def set_torrent_store_dir(self, value):
        """ Store torrent store dir(default = state_dir/collected_torrents).
        @param value str.
        """
        self.sessconfig.set(u'torrent_store', u'dir', value)

    #
    # Torrent file collecting
    #
    def set_torrent_collecting(self, value):
        """ Automatically collect torrents from peers in the network (default =
        True).
        @param value Boolean.
        """
        self.sessconfig.set(u'torrent_collecting', u'enabled', value)

    def get_torrent_collecting(self):
        """ Returns whether to automatically collect torrents.
        @return Boolean. """
        return self.sessconfig.get(u'torrent_collecting', u'enabled')

    def set_dht_torrent_collecting(self, value):
        """ Automatically collect torrents from the dht if peers fail to respond
        @param value Boolean.
        """
        self.sessconfig.set(u'torrent_collecting', u'dht_torrent_collecting', value)

    def get_dht_torrent_collecting(self):
        """ Returns whether to automatically collect torrents from the dht if peers fail
        to respond.
        @return Boolean. """
        return self.sessconfig.get(u'torrent_collecting', u'dht_torrent_collecting')

    def set_torrent_collecting_max_torrents(self, value):
        """ Set the maximum number of torrents to collect from other peers.
        @param value A number of torrents.
        """
        self.sessconfig.set(u'torrent_collecting', u'torrent_collecting_max_torrents', value)

    def get_torrent_collecting_max_torrents(self):
        """ Returns the maximum number of torrents to collect.
        @return A number of torrents. """
        return self.sessconfig.get(u'torrent_collecting', u'torrent_collecting_max_torrents')

    def set_torrent_collecting_dir(self, value):
        """ Where to place collected torrents? (default is state_dir + 'collected_torrent_files')
        @param value An absolute path.
        """
        self.sessconfig.set(u'torrent_collecting', u'torrent_collecting_dir', value)

    def get_torrent_collecting_dir(self):
        """ Returns the directory to save collected torrents.
        @return An absolute path name. """
        return self.sessconfig.get(u'torrent_collecting', u'torrent_collecting_dir')

    def set_torrent_checking(self, value):
        """ Whether to automatically check the health of collected torrents by
        contacting their trackers (default = True).
        @param value Boolean
        """
        self.sessconfig.set(u'torrent_checking', u'enabled', value)

    def get_torrent_checking(self):
        """ Returns whether to check health of collected torrents.
        @return Boolean. """
        return self.sessconfig.get(u'torrent_checking', u'enabled')

    def set_stop_collecting_threshold(self, value):
        """ Stop collecting more torrents if the disk has less than this limit
        @param value A limit in MB.
        """
        self.sessconfig.set(u'torrent_collecting', u'stop_collecting_threshold', value)

    def get_stop_collecting_threshold(self):
        """ Returns the disk-space limit when to stop collecting torrents.
        @return A number of megabytes. """
        return self.sessconfig.get(u'torrent_collecting', u'stop_collecting_threshold')

    #
    # Tribler's social networking feature transmits a nickname and picture
    # to all Tribler peers it meets.
    #

    def set_nickname(self, value):
        """ The nickname you want to show to others.
        @param value A Unicode string.
        """
        self.sessconfig.set(u'general', u'nickname', value)

    def get_nickname(self):
        """ Returns the set nickname.
        @return A Unicode string. """
        return unicode(self.sessconfig.get(u'general', u'nickname'))

    def set_mugshot(self, value, mime='image/jpeg'):
        """ The picture of yourself you want to show to others.
        @param value A string of binary data of your image.
        @param mime A string of the mimetype of the data
        """
        self.sessconfig.set(u'general', u'mugshot', (mime, value))

    def get_mugshot(self):
        """ Returns binary image data and mime-type of your picture.
        @return (String, String) value and mimetype. """
        if self.sessconfig.get(u'general', u'mugshot') is None:
            return None, None
        else:
            return self.sessconfig.get(u'general', u'mugshot')

    def set_peer_icon_path(self, value):
        """ Directory to store received peer icons (Default is statedir +
        STATEDIR_PEERICON_DIR).
        @param value An absolute path. """
        self.sessconfig.set(u'general', u'peer_icon_path', value)

    def get_peer_icon_path(self):
        """ Returns the directory to store peer icons.
        @return An absolute path name. """
        return self.sessconfig.get(u'general', u'peer_icon_path')

    #
    # For Tribler Video-On-Demand
    #
    def set_video_analyser_path(self, value):
        """ Path to video analyser FFMPEG. The analyser is used to guess the
        bitrate of a video if that information is not present in the torrent
        definition. (default = look for it in $PATH)
        @param value An absolute path name.
        """
        self.sessconfig.set(u'general', u'videoanalyserpath', value)

    def get_video_analyser_path(self):
        """ Returns the path of the FFMPEG video analyser.
        @return An absolute path name. """
        return self.sessconfig.get(u'general', u'videoanalyserpath')  # strings immutable

    def set_mainline_dht(self, value):
        """ Enable mainline DHT support (default = True)
        @param value Boolean.
        """
        self.sessconfig.set(u'mainline_dht', u'enabled', value)

    def get_mainline_dht(self):
        """ Returns whether mainline DHT support is enabled.
        @return Boolean. """
        return self.sessconfig.get(u'mainline_dht', u'enabled')

    def set_mainline_dht_listen_port(self, port):
        """ Sets the port that the mainline DHT uses to receive and send UDP
        datagrams.
        @param value int
        """
        self.sessconfig.set(u'mainline_dht', u'mainline_dht_port', port)

    def get_mainline_dht_listen_port(self):
        """ Returns the port that the mainline DHT uses to receive and send
        USP datagrams.
        @return int
        """
        return self._obtain_port(u'mainline_dht', u'mainline_dht_port')

    #
    # Local Peer Discovery using IP Multicast
    #
    def set_multicast_local_peer_discovery(self, value):
        """ Set whether the Session tries to detect local peers
        using a local IP multicast. Only applies to LibTorrent
        @param value Boolean
        """
        self.sessconfig.set(u'general', u'multicast_local_peer_discovery', value)

    def get_multicast_local_peer_discovery(self):
        """
        Returns whether local peer discovery is enabled.
        @return Boolean
        """
        return self.sessconfig.get(u'general', u'multicast_local_peer_discovery')

    #
    # Dispersy
    #
    def set_dispersy(self, value):
        """ Enable or disable Dispersy (default = True).
        @param value Boolean.
        """
        self.sessconfig.set(u'dispersy', u'enabled', value)

    def get_dispersy(self):
        """ Returns whether Dispersy is enabled.
        @return Boolean.
        """
        return self.sessconfig.get(u'dispersy', u'enabled')

    def set_dispersy_port(self, value):
        """ Sets the port that Dispersy uses to receive and send UDP
        datagrams.
        @param value int
        """
        assert isinstance(value, int)
        self.sessconfig.set(u'dispersy', u'dispersy_port', value)

    def get_dispersy_port(self):
        """ Returns the port that Dispersy uses to receive and send
        USP datagrams.
        @return int
        """
        return self._obtain_port(u'dispersy', u'dispersy_port')

    #
    # Config for swift tunneling e.g. dispersy traffic
    #
    def get_videoserver_enabled(self):
        """ Enable or disable VOD functionality (default = True).
        @param value Boolean.
        """
        return self.sessconfig.get(u'video', u'enabled')

    def set_videoserver_enabled(self, value):
        """ Returns whether VOD functionality is enabled.
        @return Boolean.
        """
        self.sessconfig.set(u'video', u'enabled', value)

    def get_videoplayer_path(self):
        """ Get the path of the player that the videoplayer should execute after calling VideoPlayer.play.
        @return path.
        """
        return self.sessconfig.get(u'video', u'path')

    def set_videoplayer_path(self, path):
        """ Set the path of the player that the videoplayer should execute after calling VideoPlayer.play.
        @param path.
        """
        self.sessconfig.set(u'video', u'path', path)

    def get_videoserver_port(self):
        """ Get the port number that the video http server should use.
        @return integer.
        """
        return self._obtain_port(u'video', u'port')

    def set_videoserver_port(self, port):
        """ Set the port number that the video http server should use.
        @param port integer (-1 indicates a random port).
        """
        self.sessconfig.set(u'video', u'port', port)

    def get_preferred_playback_mode(self):
        """ Get the preferred playback mode for videos.
        @return integer.
        """
        return self.sessconfig.get(u'video', u'preferredmode')

    def set_preferred_playback_mode(self, mode):
        """ Set the preferred playback mode for videos.
        @param mode integer (0..2, see Tribler.Core.Video.def).
        """
        self.sessconfig.set(u'video', u'preferredmode', mode)

    #
    # Search Community
    #

    def get_enable_torrent_search(self):
        """ Gets if to enable torrent search (SearchCommunity).
        :return: True or False.
        """
        return self.sessconfig.get(u'search_community', u'enabled')

    def set_enable_torrent_search(self, mode):
        """ Sets if to enable torrent search (SearchCommunity).
        :param mode: True or False.
        """
        self.sessconfig.set(u'search_community', u'enabled', mode)

    #
    # AllChannel Community
    #

    def get_enable_channel_search(self):
        """ Gets if to enable torrent search (AllChannelCommunity).
        :return: True or False.
        """
        return self.sessconfig.get(u'allchannel_community', u'enabled')

    def set_enable_channel_search(self, mode):
        """ Sets if to enable torrent search (AllChannelCommunity).
        :param mode: True or False.
        """
        self.sessconfig.set(u'allchannel_community', u'enabled', mode)

    #
    # Channel Community
    #

    def set_channel_community_enabled(self, value):
        """
        Enable or disable the channel community.
        :param value: A boolean indicating whether the channel community should be enabled
        """
        self.sessconfig.set(u'channel_community', u'enabled', value)

    def get_channel_community_enabled(self):
        """
        Returns whether the channel community is enabled.
        :return: A boolean indicating whether the channel community is enabled
        """
        return self.sessconfig.get(u'channel_community', u'enabled')

    #
    # PreviewChannel Community
    #

    def set_preview_channel_community_enabled(self, value):
        """
        Enable or disable the preview channel community.
        :param value: A boolean indicating whether the preview channel community should be enabled
        """
        self.sessconfig.set(u'preview_channel_community', u'enabled', value)

    def get_preview_channel_community_enabled(self):
        """
        Returns whether the preview channel community is enabled.
        :return: A boolean indicating whether the preview channel community is enabled
        """
        return self.sessconfig.get(u'preview_channel_community', u'enabled')

    def get_enable_metadata(self):
        """
        Gets if to enable metadata.
        :return: True or False.
        """
        return self.sessconfig.get(u'metadata', u'enabled')

    def set_enable_metadata(self, mode):
        """
        Sets if to enable metadata.
        :param mode: True or False.
        """
        return self.sessconfig.set(u'metadata', u'enabled', mode)

    def get_metadata_store_dir(self):
        """
        Gets the metadata_store directory.
        :return: The metadata_store directory.
        """
        return self.sessconfig.get(u'metadata', u'store_dir')

    def set_metadata_store_dir(self, value):
        """
        Sets the metadata_store directory.
        :param store_dir: The metadata_store directory.
        """
        return self.sessconfig.set(u'metadata', u'store_dir', value)

    def set_enable_multichain(self, value):
        """
        Sets if to enable MultiChain
        :param value: True of False
        """
        self.sessconfig.set(u'multichain', u'enabled', value)

    def get_enable_multichain(self):
        """
        Gets if to enable MultiChain.
        :return: (bool) True or False
        """
        return self.sessconfig.get(u'multichain', u'enabled')


    def set_upgrader_enabled(self, should_upgrade):
        """
        Sets if to enable upgrading.
        :param should_upgrade: True or False.
        """
        return self.sessconfig.set(u'upgrader', u'enabled', should_upgrade)

    def get_upgrader_enabled(self):
        """
        Returns if upgrading is enabled
        :return: A boolean indicating if upgrading is enabled.
        """
        return self.sessconfig.get(u'upgrader', u'enabled')

    #
    # Watch folder
    #
    def set_watch_folder_enabled(self, watch_folder_enabled):
        """
        Sets if the watch folder is enabled.
        :param watch_folder_enabled: True or False.
        """
        return self.sessconfig.set(u'watch_folder', u'enabled', watch_folder_enabled)

    def get_watch_folder_enabled(self):
        """
        Returns if the watch folder is enabled.
        :return: A boolean indicating if the watch folder is enabled.
        """
        return self.sessconfig.get(u'watch_folder', u'enabled')

    def set_watch_folder_path(self, value):
        """ Set the location of the watch folder
        @param value An absolute path.
        """
        self.sessconfig.set(u'watch_folder', u'watch_folder_dir', value)

    def get_watch_folder_path(self):
        """ Get the path to the watch folder directory.
        @return An absolute path.
        """
        return self.sessconfig.get(u'watch_folder', u'watch_folder_dir')

    #
    # API
    #
    def set_http_api_enabled(self, http_api_enabled):
        """
        Sets whether the HTTP API is enabled.
        :param http_api_enabled: True or False.
        """
        return self.sessconfig.set(u'http_api', u'enabled', http_api_enabled)

    def get_http_api_enabled(self):
        """
        Returns whether the HTTP API is enabled.
        :return: A boolean indicating whether the HTTP API is enabled.
        """
        return self.sessconfig.get(u'http_api', u'enabled')

    def set_http_api_port(self, http_api_port):
        """
        Sets the HTTP API listen port.
        :param http_api_port: An integer, indicating the port where the HTTP API should listen on.
        """
        return self.sessconfig.set(u'http_api', u'port', http_api_port)

    def get_http_api_port(self):
        """
        Returns the HTTP API listen port.
        :return: An integer indicating the port where the HTPT API listens on.
        """
        return self._obtain_port(u'http_api', u'port')

    #
    # Credit Mining
    #

    def set_creditmining_enable(self, value):
        """
        Sets to enable credit mining
        """
        self.sessconfig.set(u'credit_mining', u'enabled', value)

    def get_creditmining_enable(self):
        """
        Gets if credit mining is enabled
        :return: (bool) True or False
        """
        return self.sessconfig.get(u'credit_mining', u'enabled')

    def set_cm_max_torrents_active(self, max_torrents_active):
        """
        Set credit mining max active torrents in a single session
        """
        return self.sessconfig.set(u'credit_mining', u'max_torrents_active', max_torrents_active)

    def get_cm_max_torrents_active(self):
        """
        get max number of torrents active in a single session
        """
        return self.sessconfig.get(u'credit_mining', u'max_torrents_active')

    def set_cm_max_torrents_per_source(self, max_torrents_per_source):
        """
        set a number of torrent that can be stored in a single source
        """
        return self.sessconfig.set(u'credit_mining', u'max_torrents_per_source', max_torrents_per_source)

    def get_cm_max_torrents_per_source(self):
        """
        get max number of torrent that can be stored in a single source
        """
        return self.sessconfig.get(u'credit_mining', u'max_torrents_per_source')

    def set_cm_source_interval(self, source_interval):
        """
        set interval of looking up new torrent in a swarm
        """
        return self.sessconfig.set(u'credit_mining', u'source_interval', source_interval)

    def get_cm_source_interval(self):
        """
        get interval of looking up new torrent in a swarm
        """
        return self.sessconfig.get(u'credit_mining', u'source_interval')

    def set_cm_swarm_interval(self, swarm_interval):
        """
        set the interval of choosing activity which swarm will be downloaded
        """
        return self.sessconfig.set(u'credit_mining', u'swarm_interval', swarm_interval)

    def get_cm_swarm_interval(self):
        """
        getting the interval of choosing activity which swarm will be downloaded
        """
        return self.sessconfig.get(u'credit_mining', u'swarm_interval')

    def set_cm_tracker_interval(self, tracker_interval):
        """
        set the manual (force) scraping interval.
        """
        return self.sessconfig.set(u'credit_mining', u'tracker_interval', tracker_interval)

    def get_cm_tracker_interval(self):
        """
        get the manual (force) scraping interval.
        """
        return self.sessconfig.get(u'credit_mining', u'tracker_interval')

    def set_cm_logging_interval(self, logging_interval):
        """
        set the credit mining logging interval (INFO,DEBUG)
        """
        return self.sessconfig.set(u'credit_mining', u'logging_interval', logging_interval)

    def get_cm_logging_interval(self):
        """
        get the credit mining logging interval (INFO,DEBUG)
        """
        return self.sessconfig.get(u'credit_mining', u'logging_interval')

    def set_cm_share_mode_target(self, share_mode_target):
        """
        set the share mode target in credit mining. Value can be referenced at :
        http://www.libtorrent.org/reference-Settings.html#share_mode_target
        """
        return self.sessconfig.set(u'credit_mining', u'share_mode_target', share_mode_target)

    def get_cm_share_mode_target(self):
        """
        get the current share mode target that applies in all the swarm
        """
        return self.sessconfig.get(u'credit_mining', u'share_mode_target')

    def set_cm_policy(self, policy_str):
        """
        set the credit mining policy. Input can be policy name or class
        """
        switch_policy = {
            RandomPolicy: "random",
            CreationDatePolicy: "creation",
            SeederRatioPolicy: "seederratio"
        }

        if isinstance(policy_str, BoostingPolicy):
            policy_str = switch_policy[type(policy_str)]

        return self.sessconfig.set(u'credit_mining', u'policy', policy_str)

    def get_cm_policy(self, as_class=False):
        """
        get the credit mining policy. If as_class True, will return as class,
        otherwise will return as policy name (str)
        """
        policy_str = self.sessconfig.get(u'credit_mining', u'policy')

        if as_class:
            switch_policy = {
                "random": RandomPolicy,
                "creation": CreationDatePolicy,
                "seederratio": SeederRatioPolicy
            }

            ret = switch_policy[policy_str]
        else:
            ret = policy_str

        return ret

    def set_cm_sources(self, source_list, key):
        """
        set source list for a chosen key :
        boosting_sources, boosting_enabled, boosting_disabled, or archive_sources
        """
        return self.sessconfig.set(u'credit_mining', u'%s' % key, source_list)

    def get_cm_sources(self):
        """
        get all the lists as list of string in the configuration
        """
        ret = {"boosting_sources": self.sessconfig.get(u'credit_mining', u'boosting_sources'),
               "boosting_enabled": self.sessconfig.get(u'credit_mining', u'boosting_enabled'),
               "boosting_disabled": self.sessconfig.get(u'credit_mining', u'boosting_disabled'),
               "archive_sources": self.sessconfig.get(u'credit_mining', u'archive_sources')}

        return ret

    #
    # Static methods
    #
    @staticmethod
    def get_default_config_filename(state_dir):
        """ Return the name of the file where a session config is saved by default.
        @return A filename
        """
        return os.path.join(state_dir, STATEDIR_SESSCONFIG)


class SessionStartupConfig(SessionConfigInterface):

    """ Class to configure a Session """

    #
    # Class methods
    #
    @staticmethod
    def load(filename=None):
        """
        Load a saved SessionStartupConfig from disk.

        @param filename  An absolute Unicode filename, if None, the default path will be used.
        @return SessionStartupConfig object
        """
        if not filename:
            # Then try to read from default location
            filename = SessionStartupConfig.get_default_config_filename(SessionStartupConfig.get_default_state_dir())
        if not os.path.isfile(filename):
            # No config on the default location, just start from scratch
            return SessionStartupConfig()

        # Class method, no locking required
        sessconfig = CallbackConfigParser()
        try:
            sessconfig.read_file(filename)
        except:
            # Config file seems to be corrupt, backup the file and start from scratch
            copyfile(filename, os.path.join(os.path.dirname(filename), 'corrupt_config.bak'))
            return SessionStartupConfig()

        return SessionStartupConfig(sessconfig)

    #
    # Instance methods
    #

    def save(self, filename):
        """ Save the SessionStartupConfig to disk.
        @param filename  An absolute Unicode filename
        """
        # Called by any thread
        self.sessconfig.write_file(filename)

    def copy(self):
        return SessionStartupConfig(self.sessconfig.copy())

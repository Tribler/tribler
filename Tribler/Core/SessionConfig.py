# Written by Arno Bakker
# Updated by Egbert Bouman, now using ConfigParser
# see LICENSE.txt for license information
""" Controls the operation of a Session """

#
# WARNING: When extending this class:
#
# 1. Add a JavaDoc description for each method you add.
# 2. Also add the methods to APIImplementation/SessionRuntimeConfig.py
# 3. Document your changes in API.py
#
#
import logging
import os.path
import sys
from distutils.spawn import find_executable

from Tribler.Core.Base import Copyable, Serializable
from Tribler.Core.Utilities.configparser import CallbackConfigParser
from Tribler.Core.Utilities.network_utils import get_random_port, autodetect_socket_style
from Tribler.Core.defaults import sessdefaults
from Tribler.Core.osutils import is_android, get_appstate_dir
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

        # Set video_analyser_path
        if sys.platform == 'win32':
            ffmpegname = u"ffmpeg.exe"
        elif sys.platform == 'darwin':
            ffmpegname = u"ffmpeg"
        elif find_executable("avconv"):
            ffmpegname = u"avconv"
        else:
            ffmpegname = u"ffmpeg"

        ffmpegpath = find_executable(ffmpegname)
        if ffmpegpath is None:
            if sys.platform == 'darwin':
                self.sessconfig.set(u'general', u'videoanalyserpath', u"vlc/ffmpeg")
            elif is_android(strict=True):
                self.sessconfig.set(u'general', u'videoanalyserpath', os.path.join(
                    os.environ['ANDROID_PRIVATE'], 'ffmpeg'))
            else:
                self.sessconfig.set(u'general', u'videoanalyserpath', ffmpegname)
        else:
            self.sessconfig.set(u'general', u'videoanalyserpath', ffmpegpath)

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
        settings_port = self.sessconfig.get(section, option)
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
    def get_default_state_dir(homedirpostfix='.Tribler'):
        # Allow override
        statedirvar = '${TSTATEDIR}'
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
        return self.sessconfig.get(u'general', u'install_dir')

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
        return self.sessconfig.get(u'general', u'eckeypairfilename')

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

    def set_tunnel_community_enabled(self, enabled=True):
        self.sessconfig.set(u'tunnel_community', u'enabled', enabled)

    def get_tunnel_community_enabled(self):
        return self.sessconfig.get(u'tunnel_community', u'enabled')

    def set_tunnel_community_optin_dialog_shown(self, shown=True):
        self.sessconfig.set(u'tunnel_community', u'optin_dialog_shown', shown)

    def get_tunnel_community_optin_dialog_shown(self):
        return self.sessconfig.get(u'tunnel_community', u'optin_dialog_shown')

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
    def get_videoplayer(self):
        """ Enable or disable VOD functionality (default = True).
        @param value Boolean.
        """
        return self.sessconfig.get(u'video', u'enabled')

    def set_videoplayer(self, value):
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

    def get_videoplayer_port(self):
        """ Get the port number that the video http server should use.
        @return integer.
        """
        return self._obtain_port(u'video', u'port')

    def set_videoplayer_port(self, port):
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
    # Static methods
    #
    @staticmethod
    def get_default_config_filename(state_dir):
        """ Return the name of the file where a session config is saved by default.
        @return A filename
        """
        return os.path.join(state_dir, STATEDIR_SESSCONFIG)



class SessionStartupConfig(SessionConfigInterface, Copyable, Serializable):

    """ Class to configure a Session """

    def __init__(self, sessconfig=None):
        SessionConfigInterface.__init__(self, sessconfig)

    #
    # Class method
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
            raise IOError, "Failed to open session config file"

        return SessionStartupConfig(sessconfig)

    def save(self, filename):
        """ Save the SessionStartupConfig to disk.
        @param filename  An absolute Unicode filename
        """
        # Called by any thread
        self.sessconfig.write_file(filename)

    #
    # Copyable interface
    #
    def copy(self):
        return SessionStartupConfig(self.sessconfig.copy())

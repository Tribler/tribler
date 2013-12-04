# Written by Arno Bakker
# Updated by George Milescu
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

import ast
import sys
import copy

from ConfigParser import ConfigParser, RawConfigParser

from Tribler.Core.simpledefs import *
from Tribler.Core.defaults import sessdefaults
from Tribler.Core.Base import *
from Tribler.Core.RawServer.RawServer import autodetect_socket_style
from Tribler.Core.Utilities.utilities import find_prog_in_PATH


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
            ffmpegname = "ffmpeg.exe"
        else:
            ffmpegname = "avconv"

        ffmpegpath = find_prog_in_PATH(ffmpegname)
        if ffmpegpath is None:
            if sys.platform == 'win32':
                self.sessconfig.set('general', 'videoanalyserpath', ffmpegname)
            elif sys.platform == 'darwin':
                self.sessconfig.set('general', 'videoanalyserpath', "vlc/ffmpeg")
            else:
                self.sessconfig.set('general', 'videoanalyserpath', ffmpegname)
        else:
            self.sessconfig.set('general', 'videoanalyserpath', ffmpegpath)

        self.sessconfig.set('general', 'ipv6_binds_v4', autodetect_socket_style())

    def set_state_dir(self, statedir):
        """ Set the directory to store the Session's state in.
        @param statedir  A preferably absolute path name. If the directory
        does not yet exist it will be created at Session create time.
        """
        self.sessconfig.set('general', 'state_dir', statedir)

    def get_state_dir(self):
        """ Returns the directory the Session stores its state in.
        @return An absolute path name. """
        return self.sessconfig.get('general', 'state_dir')

    def set_install_dir(self, installdir):
        """ Set the directory in which the Tribler Core software is installed.
        @param installdir An absolute path name
        """
        self.sessconfig.set('general', 'install_dir', installdir)

    def get_install_dir(self):
        """ Returns the directory the Tribler Core software is installed in.
        @return An absolute path name. """
        return self.sessconfig.get('general', 'install_dir')

    def set_permid_keypair_filename(self, keypairfilename):
        """ Set the filename containing the Elliptic Curve keypair to use for
        PermID-based authentication in this Session.

        Note: if a Session is started with a SessionStartupConfig that
        points to an existing state dir and that state dir contains a saved
        keypair, that keypair will be used unless a different keypair is
        explicitly configured via this method.
        """
        self.sessconfig.set('general', 'eckeypairfilename', keypairfilename)

    def get_permid_keypair_filename(self):
        """ Returns the filename of the Session's keypair.
        @return An absolute path name. """
        return self.sessconfig.get('general', 'eckeypairfilename')

    def set_listen_port(self, port):
        """ Set the UDP and TCP listen port for this Session.
        @param port A port number.
        """
        self.sessconfig.set('general', 'minport', port)
        self.sessconfig.set('general', 'maxport', port)

    def get_listen_port(self):
        """ Returns the current UDP/TCP listen port.
        @return Port number. """
        return self.sessconfig.get('general', 'minport')

    def set_timeout_check_interval(self, timeout):
        self.sessconfig.set('general', 'timeout_check_interval', timeout)

    def get_timeout_check_interval(self):
        return self.sessconfig.get('general', 'timeout_check_interval')

    def set_timeout(self, timeout):
        self.sessconfig.set('general', 'timeout', timeout)

    def get_timeout(self):
        return self.sessconfig.get('general', 'timeout')

    def set_ipv6(self, enabled):
        self.sessconfig.set('general', 'ipv6_enabled', enabled)

    def get_ipv6(self):
        return self.sessconfig.get('general', 'ipv6_enabled')

    #
    # Enable/disable Tribler features
    #
    def set_megacache(self, value):
        """ Enable megacache databases to cache peers, torrent files and
        preferences (default = True).
        @param value Boolean. """
        self.sessconfig.set('general', 'megacache', value)

    def get_megacache(self):
        """ Returns whether Megacache is enabled.
        @return Boolean. """
        return self.sessconfig.get('general', 'megacache')

    def set_libtorrent(self, value):
        """ Enable or disable LibTorrent (default = True).
        @param value Boolean.
        """
        self.sessconfig.set('libtorrent', 'enabled', value)

    def get_libtorrent(self):
        """ Returns whether LibTorrent is enabled.
        @return Boolean.
        """
        return self.sessconfig.get('libtorrent', 'enabled')

    def set_libtorrent_proxy_settings(self, ptype, server=None, auth=None):
        """ Set which proxy LibTorrent should use (default = 0).
        @param ptype Integer (0 = no proxy server, 1 = SOCKS4, 2 = SOCKS5, 3 = SOCKS5 + auth, 4 = HTTP, 5 = HTTP + auth)
        @param server (host, port) tuple or None
        @param auth (username, password) tuple or None
        """
        self.sessconfig.set('libtorrent', 'lt_proxytype', ptype)
        self.sessconfig.set('libtorrent', 'lt_proxyserver', server if ptype else None)
        self.sessconfig.set('libtorrent', 'lt_proxyauth', auth if ptype in [3, 5] else None)

    def get_libtorrent_proxy_settings(self):
        """ Returns which proxy LibTorrent is using.
        @return Tuple containing ptype, server, authentication values (as described in set_libtorrent_proxy_settings)
        """
        return (self.sessconfig.get('libtorrent', 'lt_proxytype'), self.sessconfig.get('libtorrent', 'lt_proxyserver'), \
                self.sessconfig.get('libtorrent', 'lt_proxyauth'))

    def set_libtorrent_utp(self, value):
        """ Enable or disable LibTorrent uTP (default = True).
        @param value Boolean.
        """
        self.sessconfig.set('libtorrent', 'utp', value)

    def get_libtorrent_utp(self):
        """ Returns whether LibTorrent uTP is enabled.
        @return Boolean.
        """
        return self.sessconfig.get('libtorrent', 'utp')


    #
    # Torrent file collecting
    #
    def set_torrent_collecting(self, value):
        """ Automatically collect torrents from peers in the network (default =
        True).
        @param value Boolean.
        """
        self.sessconfig.set('torrent_collecting', 'enabled', value)

    def get_torrent_collecting(self):
        """ Returns whether to automatically collect torrents.
        @return Boolean. """
        return self.sessconfig.get('torrent_collecting', 'enabled')

    def set_dht_torrent_collecting(self, value):
        """ Automatically collect torrents from the dht if peers fail to respond
        @param value Boolean.
        """
        self.sessconfig.set('torrent_collecting', 'dht_torrent_collecting', value)

    def get_dht_torrent_collecting(self):
        """ Returns whether to automatically collect torrents from the dht if peers fail
        to respond.
        @return Boolean. """
        return self.sessconfig.get('torrent_collecting', 'dht_torrent_collecting')

    def set_torrent_collecting_max_torrents(self, value):
        """ Set the maximum number of torrents to collect from other peers.
        @param value A number of torrents.
        """
        self.sessconfig.set('torrent_collecting', 'torrent_collecting_max_torrents', value)

    def get_torrent_collecting_max_torrents(self):
        """ Returns the maximum number of torrents to collect.
        @return A number of torrents. """
        return self.sessconfig.get('torrent_collecting', 'torrent_collecting_max_torrents')

    def set_torrent_collecting_dir(self, value):
        """ Where to place collected torrents? (default is state_dir + 'collected_torrent_files')
        @param value An absolute path.
        """
        self.sessconfig.set('torrent_collecting', 'torrent_collecting_dir', value)

    def get_torrent_collecting_dir(self):
        """ Returns the directory to save collected torrents.
        @return An absolute path name. """
        return self.sessconfig.get('torrent_collecting', 'torrent_collecting_dir')

    def set_torrent_checking(self, value):
        """ Whether to automatically check the health of collected torrents by
        contacting their trackers (default = True).
        @param value Boolean
        """
        self.sessconfig.set('torrent_checking', 'enabled', value)

    def get_torrent_checking(self):
        """ Returns whether to check health of collected torrents.
        @return Boolean. """
        return self.sessconfig.get('torrent_checking', 'enabled')

    def set_torrent_checking_period(self, value):
        """ Interval between automatic torrent health checks.
        @param value An interval in seconds.
        """
        self.sessconfig.set('torrent_checking', 'torrent_checking_period', value)

    def get_torrent_checking_period(self):
        """ Returns the check interval.
        @return A number of seconds. """
        return self.sessconfig.get('torrent_checking', 'torrent_checking_period')

    def set_stop_collecting_threshold(self, value):
        """ Stop collecting more torrents if the disk has less than this limit
        @param value A limit in MB.
        """
        self.sessconfig.set('torrent_collecting', 'stop_collecting_threshold', value)

    def get_stop_collecting_threshold(self):
        """ Returns the disk-space limit when to stop collecting torrents.
        @return A number of megabytes. """
        return self.sessconfig.get('torrent_collecting', 'stop_collecting_threshold')

    #
    # Tribler's social networking feature transmits a nickname and picture
    # to all Tribler peers it meets.
    #

    def set_nickname(self, value):
        """ The nickname you want to show to others.
        @param value A Unicode string.
        """
        self.sessconfig.set('general', 'nickname', value)

    def get_nickname(self):
        """ Returns the set nickname.
        @return A Unicode string. """
        return self.sessconfig.get('general', 'nickname')

    def set_mugshot(self, value, mime='image/jpeg'):
        """ The picture of yourself you want to show to others.
        @param value A string of binary data of your image.
        @param mime A string of the mimetype of the data
        """
        self.sessconfig.set('general', 'mugshot', (mime, value))

    def get_mugshot(self):
        """ Returns binary image data and mime-type of your picture.
        @return (String, String) value and mimetype. """
        if self.sessconfig.get('general', 'mugshot') is None:
            return None, None
        else:
            return self.sessconfig.get('general', 'mugshot')

    def set_peer_icon_path(self, value):
        """ Directory to store received peer icons (Default is statedir +
        STATEDIR_PEERICON_DIR).
        @param value An absolute path. """
        self.sessconfig.set('general', 'peer_icon_path', value)

    def get_peer_icon_path(self):
        """ Returns the directory to store peer icons.
        @return An absolute path name. """
        return self.sessconfig.get('general', 'peer_icon_path')

    #
    # For Tribler Video-On-Demand
    #
    def set_video_analyser_path(self, value):
        """ Path to video analyser FFMPEG. The analyser is used to guess the
        bitrate of a video if that information is not present in the torrent
        definition. (default = look for it in $PATH)
        @param value An absolute path name.
        """
        self.sessconfig.set('general', 'videoanalyserpath', value)

    def get_video_analyser_path(self):
        """ Returns the path of the FFMPEG video analyser.
        @return An absolute path name. """
        return self.sessconfig.get('general', 'videoanalyserpath')  # strings immutable

    def set_mainline_dht(self, value):
        """ Enable mainline DHT support (default = True)
        @param value Boolean.
        """
        self.sessconfig.set('mainline_dht', 'enabled', value)

    def get_mainline_dht(self):
        """ Returns whether mainline DHT support is enabled.
        @return Boolean. """
        return self.sessconfig.get('mainline_dht', 'enabled')

    def set_mainline_dht_listen_port(self, port):
        """ Sets the port that the mainline DHT uses to receive and send UDP
        datagrams.
        @param value int
        """
        self.sessconfig.set('mainline_dht', 'mainline_dht_port', port)

    def get_mainline_dht_listen_port(self):
        """ Returns the port that the mainline DHT uses to receive and send
        USP datagrams.
        @return int
        """
        return self.sessconfig.get('mainline_dht', 'mainline_dht_port')

    #
    # Local Peer Discovery using IP Multicast
    #
    def set_multicast_local_peer_discovery(self, value):
        """ Set whether the Session tries to detect local peers
        using a local IP multicast. Only applies to LibTorrent
        @param value Boolean
        """
        self.sessconfig.set('general', 'multicast_local_peer_discovery', value)

    def get_multicast_local_peer_discovery(self):
        """
        Returns whether local peer discovery is enabled.
        @return Boolean
        """
        return self.sessconfig.get('general', 'multicast_local_peer_discovery')

    #
    # Dispersy
    #
    def set_dispersy(self, value):
        """ Enable or disable Dispersy (default = True).
        @param value Boolean.
        """
        self.sessconfig.set('dispersy', 'enabled', value)

    def get_dispersy(self):
        """ Returns whether Dispersy is enabled.
        @return Boolean.
        """
        return self.sessconfig.get('dispersy', 'enabled')

    def set_dispersy_tunnel_over_swift(self, value):
        """ Enable or disable Dispersy tunnelling over libswift.
        @param value Boolean.
        """
        assert isinstance(value, bool)
        self.sessconfig.set('dispersy', 'dispersy-tunnel-over-swift', value)

    def get_dispersy_tunnel_over_swift(self):
        """ Returns whether Dispersy is tunnelling over libswift.
        @return Boolean.
        """
        return self.sessconfig.get('dispersy', 'dispersy-tunnel-over-swift')

    def set_dispersy_port(self, value):
        """ Sets the port that Dispersy uses to receive and send UDP
        datagrams.
        @param value int
        """
        assert isinstance(value, int)
        self.sessconfig.set('dispersy', 'dispersy_port', value)

    def get_dispersy_port(self):
        """ Returns the port that Dispersy uses to receive and send
        USP datagrams.
        @return int
        """
        return self.sessconfig.get('dispersy', 'dispersy_port')

    #
    # SWIFTPROC
    #
    def set_swift_proc(self, value):
        """ Enable/disable support for swift Downloads via an external
        swift C++ process.
        @param value  Boolean
        """
        self.sessconfig.set('swift', 'swiftproc', value)

    def get_swift_proc(self):
        """ Return whether support for swift Downloads via an external
        swift C++ process is enabled.
        @return  Boolean
        """
        return self.sessconfig.get('swift', 'enabled')

    def set_swift_path(self, value):
        """ Path to swift binary (default = None = <installdir>/swift[.exe])
        @param value An absolute path name.
        """
        self.sessconfig.set('swift', 'swiftpath', value)

    def get_swift_path(self):
        """ Returns the path of the swift binary.
        @return An absolute path name. """
        return self.sessconfig.get('swift', 'swiftpath')  # strings immutable

    def set_swift_working_dir(self, value):
        """ Current working directory for swift binary (default = '.')
        @param value A path name.
        """
        self.sessconfig.set('swift', 'swiftworkingdir', value)

    def get_swift_working_dir(self):
        """ Returns the working directory for the swift binary.
        @return A path name. """
        return self.sessconfig.get('swift', 'swiftworkingdir')  # strings immutable

    def set_swift_meta_dir(self, value):
        """ Set the metadir for storing .m* files of downloads.
        @param value An absolutepath.
        """
        self.sessconfig.set('swift', 'swiftmetadir', value)

    def get_swift_meta_dir(self):
        """ Return the metadir for storing .m* files of downloads.
        @return An absolutepath.
        """
        return self.sessconfig.get('swift', 'swiftmetadir')

    def set_swift_cmd_listen_port(self, port):
        """ Set the local TCP listen port for cmd socket communication to
        the swift processes (unused). CMD listen port of swift process itself
        is set via DownloadConfig.set_swift_cmdgw_listen_port() (download-to-process
        mapping permitting)
        @param port A port number.
        """
        self.sessconfig.set('swift', 'swiftcmdlistenport', port)

    def get_swift_cmd_listen_port(self):
        """ Returns the local listen port for swift cmd socket communication.
        @return Port number. """
        return self.sessconfig.get('swift', 'swiftcmdlistenport')

    def set_swift_dht_listen_port(self, port):
        """ Set the local UDP listen port for dht socket communication to
        the swift processes. 
        @param port A port number.
        """
        self.sessconfig.set('swift', 'swiftdhtport', port)

    def get_swift_dht_listen_port(self):
        """ Returns the local dht port for swift communication.
        @return Port number. """
        return self.sessconfig.get('swift', 'swiftdhtport')

    def set_swift_downloads_per_process(self, value):
        """ Number of downloads per swift process. When exceeded, a new swift
        process is created. Only used when the user did not specify ports
        for the swift process via DownloadConfig.set_swift_*_port()
        @param value A number of downloads.
        """
        self.sessconfig.set('swift', 'swiftdlsperproc', value)

    def get_swift_downloads_per_process(self):
        """ Returns the number of downloads per swift process.
        @return A number of downloads. """
        return self.sessconfig.get('swift', 'swiftdlsperproc')

    #
    # Config for swift tunneling e.g. dispersy traffic
    #
    def set_swift_tunnel_listen_port(self, port):
        """ Set the UDP port for the swift process
        (download-to-process mapping permitting).
        @param port A port number.
        """
        self.sessconfig.set('swift', 'swifttunnellistenport', port)

    def get_swift_tunnel_listen_port(self):
        """ Returns the UDP port of the swift process.

        @return Port number. """
        return self.sessconfig.get('swift', 'swifttunnellistenport')

    def set_swift_tunnel_cmdgw_listen_port(self, port):
        """ Set the TCP listen port for the CMDGW of the swift process
        (download-to-process mapping permitting).
        @param port A port number.
        """
        self.sessconfig.set('swift', 'swifttunnelcmdgwlistenport', port)

    def get_swift_tunnel_cmdgw_listen_port(self):
        """ Returns the TCP listen port for the CMDGW of the swift process
        (download-to-process mapping permitting).

        @return Port number. """
        return self.sessconfig.get('swift', 'swifttunnelcmdgwlistenport')

    def set_swift_tunnel_httpgw_listen_port(self, port):
        """ Set the TCP listen port for the CMDGW of the swift process
        (download-to-process mapping permitting).
        @param port A port number.
        """
        self.sessconfig.set('swift', 'swifttunnelhttpgwlistenport', port)

    def get_swift_tunnel_httpgw_listen_port(self):
        """ Returns the TCP listen port for the CMDGW of the swift process.

        @return Port number. """
        return self.sessconfig.get('swift', 'swifttunnelhttpgwlistenport')


class SessionStartupConfig(SessionConfigInterface, Copyable, Serializable):

    """ Class to configure a Session """

    def __init__(self, sessconfig=None):
        SessionConfigInterface.__init__(self, sessconfig)

    #
    # Class method
    #
    def load(filename):
        """
        Load a saved SessionStartupConfig from disk.

        @param filename  An absolute Unicode filename
        @return SessionStartupConfig object
        """
        # Class method, no locking required
        sessconfig = CallbackConfigParser()
        if not sessconfig.read(filename):
            raise IOError, "Failed to open session config file"

        return SessionStartupConfig(sessconfig)

    load = staticmethod(load)

    def save(self, filename):
        """ Save the SessionStartupConfig to disk.
        @param filename  An absolute Unicode filename
        """
        # Called by any thread
        config_file = open(filename, "wb")
        self.sessconfig.write(config_file)
        config_file.close()

    #
    # Copyable interface
    #
    def copy(self):
        return SessionStartupConfig(self.sessconfig.copy())


class CallbackConfigParser(RawConfigParser):

    def __init__(self, *args, **kwargs):
        RawConfigParser.__init__(self, *args, **kwargs)
        self.callback = None

    def set_callback(self, callback):
        self.callback = callback

    def set(self, section, option, new_value):
        if self.callback and self.has_section(section) and self.has_option(section, option):
            old_value = self.get(section, option)
            if not self.callback(section, option, new_value, old_value):
                raise OperationNotPossibleAtRuntimeException
        RawConfigParser.set(self, section, option, new_value)

    def get(self, section, option, literal_eval=True):
        value = RawConfigParser.get(self, section, option) if RawConfigParser.has_option(self, section, option) else None
        if literal_eval:
            try:
                value = ast.literal_eval(value)
            except:
                pass
        return value

    def copy(self):
        copied_config = CallbackConfigParser()
        copied_config._sections = self._sections
        return copied_config

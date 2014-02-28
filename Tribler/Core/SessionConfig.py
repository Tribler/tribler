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

import sys
import codecs
import os.path
import socket
import random
import logging

from Tribler.Core.simpledefs import *
from Tribler.Core.defaults import sessdefaults
from Tribler.Core.Base import *
from Tribler.Core.RawServer.RawServer import autodetect_socket_style
from Tribler.Core.Utilities.utilities import find_prog_in_PATH
from Tribler.Core.Utilities.configparser import CallbackConfigParser


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

        self.randomly_selected_ports = {}
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
        else:
            ffmpegname = u"avconv"

        ffmpegpath = find_prog_in_PATH(ffmpegname)
        if ffmpegpath is None:
            if sys.platform == 'win32':
                self.sessconfig.set(u'general', u'videoanalyserpath', ffmpegname)
            elif sys.platform == 'darwin':
                self.sessconfig.set(u'general', u'videoanalyserpath', u"vlc/ffmpeg")
            else:
                self.sessconfig.set(u'general', u'videoanalyserpath', ffmpegname)
        else:
            self.sessconfig.set(u'general', u'videoanalyserpath', ffmpegpath)

        self.sessconfig.set(u'general', u'ipv6_binds_v4', autodetect_socket_style())

    #
    # Auxiliar functions
    #

    def _obtain_port(self, *keys):
        """ Fetch a port setting from the config file and in case it's set to -1 (random), look for a free port and assign it to
                this particular setting.
        """
        settings_port = self.sessconfig.get(*keys)
        if settings_port == -1:
            path = '~'.join(keys)
            if path not in self.randomly_selected_ports:
                random_port = 0

                while True:
                    s = socket.socket()
                    try:
                        s.bind(('', random_port))
                        random_port = s.getsockname()[1]
                        if random_port in self.randomly_selected_ports.values():
                            raise Exception(u"port already in random-list.")
                        else:
                            # get unique port
                            self.randomly_selected_ports[path] = random_port
                            break
                    except:
                        self._logger.exception(u"Unable to bind port %d", random_port)

                        random_port += 1
                        if random_port < 1000 or random_port > 65535:
                            random_port = random.uniform(5000, 60000)
                    finally:
                        s.close()

                self._logger.debug(u"Get random port %d for [%s]", self.randomly_selected_ports[path], path)
            return self.randomly_selected_ports[path]
        return settings_port

    def set_state_dir(self, statedir):
        """ Set the directory to store the Session's state in.
        @param statedir  A preferably absolute path name. If the directory
        does not yet exist it will be created at Session create time.
        """
        self.sessconfig.set(u'general', u'state_dir', statedir)

    def get_state_dir(self):
        """ Returns the directory the Session stores its state in.
        @return An absolute path name. """
        return self.sessconfig.get(u'general', u'state_dir')

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
        return (self.sessconfig.get(u'libtorrent', u'lt_proxytype'), \
                self.sessconfig.get(u'libtorrent', u'lt_proxyserver'), \
                self.sessconfig.get(u'libtorrent', u'lt_proxyauth'))

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

    def set_torrent_checking_period(self, value):
        """ Interval between automatic torrent health checks.
        @param value An interval in seconds.
        """
        self.sessconfig.set(u'torrent_checking', u'torrent_checking_period', value)

    def get_torrent_checking_period(self):
        """ Returns the check interval.
        @return A number of seconds. """
        return self.sessconfig.get(u'torrent_checking', u'torrent_checking_period')

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
        return self.sessconfig.get(u'general', u'nickname')

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

    def set_dispersy_tunnel_over_swift(self, value):
        """ Enable or disable Dispersy tunnelling over libswift.
        @param value Boolean.
        """
        assert isinstance(value, bool)
        self.sessconfig.set(u'dispersy', u'dispersy-tunnel-over-swift', value)

    def get_dispersy_tunnel_over_swift(self):
        """ Returns whether Dispersy is tunnelling over libswift.
        @return Boolean.
        """
        return self.sessconfig.get(u'dispersy', u'dispersy-tunnel-over-swift')

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
    # SWIFTPROC
    #
    def set_swift_proc(self, value):
        """ Enable/disable support for swift Downloads via an external
        swift C++ process.
        @param value  Boolean
        """
        self.sessconfig.set(u'swift', u'swiftproc', value)

    def get_swift_proc(self):
        """ Return whether support for swift Downloads via an external
        swift C++ process is enabled.
        @return  Boolean
        """
        return self.sessconfig.get(u'swift', u'enabled')

    def set_swift_path(self, value):
        """ Path to swift binary (default = None = <installdir>/swift[.exe])
        @param value An absolute path name.
        """
        self.sessconfig.set(u'swift', u'swiftpath', value)

    def get_swift_path(self):
        """ Returns the path of the swift binary.
        @return An absolute path name. """
        return self.sessconfig.get(u'swift', u'swiftpath')  # strings immutable

    def set_swift_working_dir(self, value):
        """ Current working directory for swift binary (default = '.')
        @param value A path name.
        """
        self.sessconfig.set(u'swift', u'swiftworkingdir', value)

    def get_swift_working_dir(self):
        """ Returns the working directory for the swift binary.
        @return A path name. """
        return self.sessconfig.get(u'swift', u'swiftworkingdir')  # strings immutable

    def set_swift_meta_dir(self, value):
        """ Set the metadir for storing .m* files of downloads.
        @param value An absolutepath.
        """
        self.sessconfig.set(u'swift', u'swiftmetadir', value)

    def get_swift_meta_dir(self):
        """ Return the metadir for storing .m* files of downloads.
        @return An absolutepath.
        """
        return self.sessconfig.get(u'swift', u'swiftmetadir')

    def set_swift_cmd_listen_port(self, port):
        """ Set the local TCP listen port for cmd socket communication to
        the swift processes (unused). CMD listen port of swift process itself
        is set via DownloadConfig.set_swift_cmdgw_listen_port() (download-to-process
        mapping permitting)
        @param port A port number.
        """
        self.sessconfig.set(u'swift', u'swiftcmdlistenport', port)

    def get_swift_cmd_listen_port(self):
        """ Returns the local listen port for swift cmd socket communication.
        @return Port number. """
        return self._obtain_port(u'swift', u'swiftcmdlistenport')

    def set_swift_dht_listen_port(self, port):
        """ Set the local UDP listen port for dht socket communication to
        the swift processes.
        @param port A port number.
        """
        self.sessconfig.set(u'swift', u'swiftdhtport', port)

    def get_swift_dht_listen_port(self):
        """ Returns the local dht port for swift communication.
        @return Port number. """
        return self._obtain_port(u'swift', u'swiftdhtport')

    def set_swift_downloads_per_process(self, value):
        """ Number of downloads per swift process. When exceeded, a new swift
        process is created. Only used when the user did not specify ports
        for the swift process via DownloadConfig.set_swift_*_port()
        @param value A number of downloads.
        """
        self.sessconfig.set(u'swift', u'swiftdlsperproc', value)

    def get_swift_downloads_per_process(self):
        """ Returns the number of downloads per swift process.
        @return A number of downloads. """
        return self.sessconfig.get(u'swift', u'swiftdlsperproc')

    #
    # Config for swift tunneling e.g. dispersy traffic
    #
    def set_swift_tunnel_listen_port(self, port):
        """ Set the UDP port for the swift process
        (download-to-process mapping permitting).
        @param port A port number.
        """
        self.sessconfig.set(u'swift', u'swifttunnellistenport', port)

    def get_swift_tunnel_listen_port(self):
        """ Returns the UDP port of the swift process.

        @return Port number. """
        return self._obtain_port(u'swift', u'swifttunnellistenport')

    def set_swift_tunnel_cmdgw_listen_port(self, port):
        """ Set the TCP listen port for the CMDGW of the swift process
        (download-to-process mapping permitting).
        @param port A port number.
        """
        self.sessconfig.set(u'swift', u'swifttunnelcmdgwlistenport', port)

    def get_swift_tunnel_cmdgw_listen_port(self):
        """ Returns the TCP listen port for the CMDGW of the swift process
        (download-to-process mapping permitting).

        @return Port number. """
        return self._obtain_port(u'swift', u'swifttunnelcmdgwlistenport')

    def set_swift_tunnel_httpgw_listen_port(self, port):
        """ Set the TCP listen port for the CMDGW of the swift process
        (download-to-process mapping permitting).
        @param port A port number.
        """
        self.sessconfig.set(u'swift', u'swifttunnelhttpgwlistenport', port)

    def get_swift_tunnel_httpgw_listen_port(self):
        """ Returns the TCP listen port for the CMDGW of the swift process.

        @return Port number. """
        return self._obtain_port(u'swift', u'swifttunnelhttpgwlistenport')


class SessionStartupConfig(SessionConfigInterface, Copyable, Serializable):

    """ Class to configure a Session """

    def __init__(self, sessconfig=None):
        SessionConfigInterface.__init__(self, sessconfig)


    #
    # Class method
    #
    @staticmethod
    def load(filename):
        """
        Load a saved SessionStartupConfig from disk.

        @param filename  An absolute Unicode filename
        @return SessionStartupConfig object
        """
        # Class method, no locking required
        if not os.path.exists(filename):
            self._logger.warn(u"Config file doesn't exist [%s]", filename)
            raise IOError, u"Failed to open session config file"
        if not os.path.isfile(filename):
            self._logger.warn(u"Config file isn't a file [%s]", filename)
            raise IOError, u"Failed to open session config file"

        try:
            f = codecs.open(filename, 'r', 'utf8')
        except:
            self._logger.exception(u"Failed to decode config file [%s]", filename)
            raise IOError, u"Failed to open session config file"

        sessconfig = CallbackConfigParser()
        sessconfig.readfp(f)

        return SessionStartupConfig(sessconfig)


    def save(self, filename):
        """ Save the SessionStartupConfig to disk.
        @param filename  An absolute Unicode filename
        """
        # Called by any thread
        config_file = codecs.open(filename, 'wb', 'utf8')
        self.sessconfig.write(config_file)
        config_file.close()

    #
    # Copyable interface
    #
    def copy(self):
        return SessionStartupConfig(self.sessconfig.copy())

# Written by Arno Bakker 
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
import copy
import pickle

from Tribler.Core.simpledefs import *
from Tribler.Core.defaults import sessdefaults
from Tribler.Core.Base import *
from Tribler.Core.BitTornado.RawServer import autodetect_socket_style
from Tribler.Core.Utilities.utilities import find_prog_in_PATH


class SessionConfigInterface:
    """ 
    (key,value) pair config of global parameters, 
    e.g. PermID keypair, listen port, max upload speed, etc.
    
    Use SessionStartupConfig from creating and manipulation configurations
    before session startup time. This is just a parent class.
    """
    def __init__(self,sessconfig=None):
        """ Constructor. 
        @param sessconfig Optional dictionary used internally 
        to make this a copy constructor.
        """

        if sessconfig is not None: # copy constructor
            self.sessconfig = sessconfig
            return
        
        self.sessconfig = {}
        
        # Define the built-in default here
        self.sessconfig.update(sessdefaults)
        
        # Set video_analyser_path
        if sys.platform == 'win32':
            ffmpegname = "ffmpeg.exe"
        else:
            ffmpegname = "ffmpeg"
    
        ffmpegpath = find_prog_in_PATH(ffmpegname)
        if ffmpegpath is None:
            if sys.platform == 'win32':
                self.sessconfig['videoanalyserpath'] = ffmpegname
            elif sys.platform == 'darwin':
                self.sessconfig['videoanalyserpath'] = "macbinaries/ffmpeg"
            else:
                self.sessconfig['videoanalyserpath'] = ffmpegname
        else:
            self.sessconfig['videoanalyserpath'] = ffmpegpath

        self.sessconfig['ipv6_binds_v4'] = autodetect_socket_style()



    def set_state_dir(self,statedir):
        """ Set the directory to store the Session's state in.
        @param statedir  A preferably absolute path name. If the directory
        does not yet exist it will be created at Session create time.
        """
        self.sessconfig['state_dir'] = statedir
    
    def get_state_dir(self):
        """ Returns the directory the Session stores its state in. 
        @return An absolute path name. """
        return self.sessconfig['state_dir']
    
    def set_install_dir(self,installdir):
        """ Set the directory in which the Tribler Core software is installed. 
        @param installdir An absolute path name
        """
        self.sessconfig['install_dir'] = installdir
    
    def get_install_dir(self):
        """ Returns the directory the Tribler Core software is installed in.
        @return An absolute path name. """
        return self.sessconfig['install_dir']
    
    
    def set_permid_keypair_filename(self,keypairfilename):
        """ Set the filename containing the Elliptic Curve keypair to use for 
        PermID-based authentication in this Session. 
        
        Note: if a Session is started with a SessionStartupConfig that
        points to an existing state dir and that state dir contains a saved
        keypair, that keypair will be used unless a different keypair is
        explicitly configured via this method.
        """
        self.sessconfig['eckeypairfilename'] = keypairfilename

    def get_permid_keypair_filename(self):
        """ Returns the filename of the Session's keypair.
        @return An absolute path name. """
        return self.sessconfig['eckeypairfilename']
    

    def set_listen_port(self,port):
        """ Set the UDP and TCP listen port for this Session.
        @param port A port number.
        """
        self.sessconfig['minport'] = port
        self.sessconfig['maxport'] = port

    def get_listen_port(self):
        """ Returns the current UDP/TCP listen port.
        @return Port number. """
        return self.sessconfig['minport']
        
    #
    # Advanced network settings
    #
    def set_ip_for_tracker(self,value):
        """ IP address to report to the tracker (default = set automatically).
        @param value  An IP address as string. """
        self.sessconfig['ip'] = value

    def get_ip_for_tracker(self):
        """ Returns the IP address being reported to the tracker.
        @return String """
        return self.sessconfig['ip']

    def set_bind_to_addresses(self,value):
        """ Set the list of IP addresses/hostnames to bind to locally.
        @param value A list of IP addresses as strings. """
        self.sessconfig['bind'] = value

    def get_bind_to_addresses(self):
        """ Returns the list of IP addresses bound to.
        @return list """
        return self.sessconfig['bind']

    def set_upnp_mode(self,value):
        """ Use to autoconfigure a UPnP router to forward the UDP/TCP listen 
        port to this host:
        <pre>
         * UPNPMODE_DISABLED: Autoconfigure turned off.
         * UPNPMODE_WIN32_HNetCfg_NATUPnP: Use Windows COM interface (slow)
         * UPNPMODE_WIN32_UPnP_UPnPDeviceFinder: Use Windows COM interface (faster)
         * UPNPMODE_UNIVERSAL_DIRECT: Talk UPnP directly to the network (best)
        </pre>
        @param value UPNPMODE_* 
        """
        self.sessconfig['upnp_nat_access'] = value

    def get_upnp_mode(self):
        """ Returns the UPnP mode set. 
        @return UPNPMODE_* """
        return self.sessconfig['upnp_nat_access']

    def set_autoclose_timeout(self,value):
        """ Time to wait between closing sockets which nothing has been received
        on.
        @param value A number of seconds.
        """
        self.sessconfig['timeout'] = value

    def get_autoclose_timeout(self):
        """ Returns the autoclose timeout.
        @return A number of seconds. """
        return self.sessconfig['timeout']

    def set_autoclose_check_interval(self,value):
        """ Time to wait between checking if any connections have timed out.
        @param value A number of seconds.
        """
        self.sessconfig['timeout_check_interval'] = value

    def get_autoclose_check_interval(self):
        """ Returns the autoclose check interval.
        @return A number of seconds. """
        return self.sessconfig['timeout_check_interval']

    #
    # Enable/disable Tribler features 
    #
    def set_megacache(self,value):
        """ Enable megacache databases to cache peers, torrent files and 
        preferences (default = True).
        @param value Boolean. """
        self.sessconfig['megacache'] = value

    def get_megacache(self):
        """ Returns whether Megacache is enabled.
        @return Boolean. """
        return self.sessconfig['megacache']

    #
    # Secure Overlay
    #
    def set_overlay(self,value):
        """ Enable overlay swarm to enable Tribler's special features 
        (default = True).
        @param value Boolean. 
        """
        self.sessconfig['overlay'] = value

    def get_overlay(self):
        """ Returns whether overlay-swarm extension is enabled. The overlay
        swarm allows strong authentication of peers and is used for all
        Tribler-specific messages.
        @return Boolean. """
        return self.sessconfig['overlay']

    def set_overlay_max_message_length(self,value):
        """ Maximal message length for messages sent over the secure overlay.
        @param value A number of bytes.
        """
        self.sessconfig['overlay_max_message_length'] = value

    def get_overlay_max_message_length(self):
        """ Returns the maximum overlay-message length.
        @return A number of bytes. """
        return self.sessconfig['overlay_max_message_length']


    #
    # Buddycast
    #
    def set_buddycast(self,value):
        """ Enable buddycast recommendation system at startup (default = True)
        @param value Boolean.
        """
        self.sessconfig['buddycast'] = value

    def get_buddycast(self):
        """ Returns whether buddycast is enabled at startup. 
        @return Boolean."""
        return self.sessconfig['buddycast']

    def set_start_recommender(self,value):
        """ Buddycast can be temporarily disabled via this parameter 
        (default = True). Must have been enabled at startup, see
        set_buddycast().
        @param value Boolean. 
        """
        self.sessconfig['start_recommender'] = value

    def get_start_recommender(self):
        """ Returns whether Buddycast is temporarily enabled. 
        @return Boolean."""
        return self.sessconfig['start_recommender']

    def set_buddycast_interval(self,value):
        """ Number of seconds to pause between exchanging preference with a 
        peer in Buddycast.
        @param value A number of seconds.
        """
        self.sessconfig['buddycast_interval'] = value

    def get_buddycast_interval(self):
        """ Returns the number of seconds between Buddycast pref. exchanges. 
        @return A number of seconds. """
        return self.sessconfig['buddycast_interval']

    def set_buddycast_collecting_solution(self,value):
        """ Set the Buddycast collecting solution. Only one policy implemented
        at the moment:
        <pre>
         * BCCOLPOLICY_SIMPLE: Simplest solution: per torrent/buddycasted peer/4 hours,
         </pre>
        @param value BCCOLPOLICY_* 
        """
        self.sessconfig['buddycast_collecting_solution'] = value

    def get_buddycast_collecting_solution(self):
        """ Returns the Buddycast collecting solution. 
        @return BCOLPOLICY_* """
        return self.sessconfig['buddycast_collecting_solution']

    def set_buddycast_max_peers(self,value):
        """ Set max number of peers to use for Buddycast recommendations """
        self.sessconfig['buddycast_max_peers'] = value

    def get_buddycast_max_peers(self):
        """ Return the max number of peers to use for Buddycast recommendations.
        @return A number of peers.
        """
        return self.sessconfig['buddycast_max_peers']

    #
    # Download helper / cooperative download
    #
    def set_download_help(self,value):
        """ Enable download helping/cooperative download (default = True).
        @param value Boolean. """
        self.sessconfig['download_help'] = value

    def get_download_help(self):
        """ Returns whether download help is enabled. 
        @return Boolean. """
        return self.sessconfig['download_help']

    def set_download_help_dir(self,value):
        """ Set the directory for storing state and content for download
        helping (default = Default destination dir (see get_default_dest_dir()
        +'downloadhelp'.
        @param value An absolute path. """
        self.sessconfig['download_help_dir'] = value

    def get_download_help_dir(self):
        """ Returns the directory for download helping storage. 
        @return An absolute path name. """
        return self.sessconfig['download_help_dir']

    #
    # Torrent file collecting
    #
    def set_torrent_collecting(self,value):
        """ Automatically collect torrents from peers in the network (default = 
        True).
        @param value Boolean. 
        """
        self.sessconfig['torrent_collecting'] = value

    def get_torrent_collecting(self):
        """ Returns whether to automatically collect torrents.
        @return Boolean. """
        return self.sessconfig['torrent_collecting']

    def set_torrent_collecting_max_torrents(self,value):
        """ Set the maximum number of torrents to collect from other peers.
        @param value A number of torrents.
        """
        self.sessconfig['torrent_collecting_max_torrents'] = value

    def get_torrent_collecting_max_torrents(self):
        """ Returns the maximum number of torrents to collect.
        @return A number of torrents. """
        return self.sessconfig['torrent_collecting_max_torrents']

    def set_torrent_collecting_dir(self,value):
        """ Where to place collected torrents? (default is state_dir + 'collected_torrent_files')
        @param value An absolute path.
        """
        self.sessconfig['torrent_collecting_dir'] = value

    def get_torrent_collecting_dir(self):
        """ Returns the directory to save collected torrents.
        @return An absolute path name. """
        return self.sessconfig['torrent_collecting_dir']

    def set_torrent_collecting_rate(self,value):
        """ Maximum download rate to use for torrent collecting.
        @param value A rate in KB/s. """
        self.sessconfig['torrent_collecting_rate'] = value

    def get_torrent_collecting_rate(self):
        """ Returns the download rate to use for torrent collecting.
        @return A rate in KB/s. """
        return self.sessconfig['torrent_collecting_rate']

    def set_torrent_checking(self,value):
        """ Whether to automatically check the health of collected torrents by
        contacting their trackers (default = True).
        @param value Boolean 
        """
        self.sessconfig['torrent_checking'] = value

    def get_torrent_checking(self):
        """ Returns whether to check health of collected torrents.
        @return Boolean. """
        return self.sessconfig['torrent_checking']

    def set_torrent_checking_period(self,value):
        """ Interval between automatic torrent health checks.
        @param value An interval in seconds.
        """
        self.sessconfig['torrent_checking_period'] = value

    def get_torrent_checking_period(self):
        """ Returns the check interval.
        @return A number of seconds. """
        return self.sessconfig['torrent_checking_period']

    def set_stop_collecting_threshold(self,value):
        """ Stop collecting more torrents if the disk has less than this limit 
        @param value A limit in MB.
        """
        self.sessconfig['stop_collecting_threshold'] = value

    def get_stop_collecting_threshold(self):
        """ Returns the disk-space limit when to stop collecting torrents. 
        @return A number of megabytes. """
        return self.sessconfig['stop_collecting_threshold']


    #
    # The Tribler dialback mechanism is used to test whether a Session is
    # reachable from the outside and what its external IP address is.
    #
    def set_dialback(self,value):
        """ Use other peers to determine external IP address (default = True)
        @param value Boolean 
        """
        self.sessconfig['dialback'] = value

    def get_dialback(self):
        """ Returns whether to use the dialback mechanism. 
        @return Boolean. """
        return self.sessconfig['dialback']

    #
    # Tribler's social networking feature transmits a nickname and picture
    # to all Tribler peers it meets.
    #
    def set_social_networking(self,value):
        """ Enable social networking. If enabled, a message containing the
        user's nickname and icon is sent to each Tribler peer met
        (default = True).
        @param value Boolean 
        """
        self.sessconfig['socnet'] = value

    def get_social_networking(self):
        """ Returns whether social network is enabled.
        @return Boolean. """
        return self.sessconfig['socnet']

    def set_nickname(self,value):
        """ The nickname you want to show to others.
        @param value A Unicode string.
        """
        self.sessconfig['nickname'] = value

    def get_nickname(self):
        """ Returns the set nickname.
        @return A Unicode string. """
        return self.sessconfig['nickname']

    def set_mugshot(self,value, mime = 'image/jpeg'):
        """ The picture of yourself you want to show to others.
        @param value A string of binary data of your image.
        @param mime A string of the mimetype of the data
        """
        self.sessconfig['mugshot'] = (mime, value)

    def get_mugshot(self):
        """ Returns binary image data and mime-type of your picture.
        @return (String, String) value and mimetype. """
        if self.sessconfig['mugshot'] is None:
            return None, None
        else:
            return self.sessconfig['mugshot']
    
    def set_peer_icon_path(self,value):
        """ Directory to store received peer icons (Default is statedir +
        STATEDIR_PEERICON_DIR).
        @param value An absolute path. """
        self.sessconfig['peer_icon_path'] = value

    def get_peer_icon_path(self):
        """ Returns the directory to store peer icons.
        @return An absolute path name. """
        return self.sessconfig['peer_icon_path']

    #
    # Tribler remote query: ask other peers when looking for a torrent file 
    # or peer
    #
    def set_remote_query(self,value):
        """ Enable queries from other peers. At the moment peers can ask
        whether this Session has collected or opened a torrent that matches
        a specified keyword query. (default = True)
        @param value Boolean"""
        self.sessconfig['rquery'] = value

    def get_remote_query(self):
        """ Returns whether remote query is enabled. 
        @return Boolean. """
        return self.sessconfig['rquery']

    #
    # BarterCast
    #
    def set_bartercast(self,value):
        """ Exchange upload/download statistics with peers (default = True)
        @param value Boolean
        """
        self.sessconfig['bartercast'] = value

    def get_bartercast(self):
        """ Returns to exchange statistics with peers.
        @return Boolean. """
        return self.sessconfig['bartercast']


    #
    # For Tribler Video-On-Demand
    #
    def set_video_analyser_path(self,value):
        """ Path to video analyser FFMPEG. The analyser is used to guess the
        bitrate of a video if that information is not present in the torrent
        definition. (default = look for it in $PATH)
        @param value An absolute path name.
        """
        self.sessconfig['videoanalyserpath'] = value
    
    def get_video_analyser_path(self):
        """ Returns the path of the FFMPEG video analyser.
        @return An absolute path name. """
        return self.sessconfig['videoanalyserpath'] # strings immutable
    

    #
    # Tribler's internal tracker
    #
    def set_internal_tracker(self,value):
        """ Enable internal tracker (default = True)
        @param value Boolean.
        """
        self.sessconfig['internaltracker'] = value

    def get_internal_tracker(self):
        """ Returns whether the internal tracker is enabled.
        @return Boolean. """
        return self.sessconfig['internaltracker']

    def set_internal_tracker_url(self,value):
        """ Set the internal tracker URL (default = determined dynamically
        from Session's IP+port)
        @param value URL.
        """
        self.sessconfig['tracker_url'] = value

    def get_internal_tracker_url(self):
        """ Returns the URL of the tracker as set by set_internal_tracker_url().
        Overridden at runtime by Session class.
        @return URL. """
        return self.sessconfig['tracker_url']


    def set_mainline_dht(self,value):
        """ Enable mainline DHT support (default = True)
        @param value Boolean.
        """
        self.sessconfig['mainline_dht'] = value

    def get_mainline_dht(self):
        """ Returns whether mainline DHT support is enabled.
        @return Boolean. """
        return self.sessconfig['mainline_dht']


    #
    # Internal tracker access control settings
    #
    def set_tracker_allowed_dir(self,value):
        """ Only accept tracking requests for torrent in this dir (default is
        Session state-dir + STATEDIR_ITRACKER_DIR
        @param value An absolute path name.
        """
        self.sessconfig['tracker_allowed_dir'] = value

    def get_tracker_allowed_dir(self):
        """ Returns the internal tracker's directory of allowed torrents.
        @return An absolute path name. """
        return self.sessconfig['tracker_allowed_dir']

    def set_tracker_allowed_list(self,value):
        """ Only allow peers to register for torrents that appear in the
        specified file. Cannot be used in combination with set_tracker_allowed_dir()
        @param value An absolute filename containing a list of torrent infohashes in hex format, one per 
        line. """
        self.sessconfig['tracker_allowed_list'] = value

    def get_tracker_allowed_list(self):
        """ Returns the filename of the list of allowed torrents.
        @return An absolute path name. """
        return self.sessconfig['tracker_allowed_list']

    def set_tracker_allowed_controls(self,value):
        """ Allow special keys in torrents in the allowed_dir to affect tracker
        access.
        @param value Boolean
        """
        self.sessconfig['tracker_allowed_controls'] = value

    def get_tracker_allowed_controls(self):
        """ Returns whether to allow allowed torrents to control tracker access.
        @return Boolean. """
        return self.sessconfig['tracker_allowed_controls']

    def set_tracker_allowed_ips(self,value):
        """ Only allow connections from IPs specified in the given file; file 
        contains subnet data in the format: aa.bb.cc.dd/len.
        @param value An absolute path name.
        """
        self.sessconfig['tracker_allowed_ips'] = value

    def get_tracker_allowed_ips(self):
        """ Returns the filename containing allowed IP addresses. 
        @return An absolute path name."""
        return self.sessconfig['tracker_allowed_ips']

    def set_tracker_banned_ips(self,value):
        """ Don't allow connections from IPs specified in the given file; file
        contains IP range data in the format: xxx:xxx:ip1-ip2
        @param value An absolute path name.
        """
        self.sessconfig['tracker_banned_ips'] = value

    def get_tracker_banned_ips(self):
        """ Returns the filename containing banned IP addresses. 
        @return An absolute path name. """
        return self.sessconfig['tracker_banned_ips']

    def set_tracker_only_local_override_ip(self,value):
        """ Ignore the 'ip' parameter in the GET announce from machines which 
        aren't on local network IPs.
        <pre>
         * ITRACK_IGNORE_ANNOUNCEIP_NEVER
         * ITRACK_IGNORE_ANNOUNCEIP_ALWAYS
         * ITRACK_IGNORE_ANNOUNCEIP_IFNONATCHECK
        </pre>
        @param value ITRACK_IGNORE_ANNOUNCEIP*
        """
        self.sessconfig['tracker_only_local_override_ip'] = value

    def get_tracker_only_local_override_ip(self):
        """ Returns the ignore policy for 'ip' parameters in announces. 
        @return ITRACK_IGNORE_ANNOUNCEIP_* """
        return self.sessconfig['tracker_only_local_override_ip']

    def set_tracker_parse_dir_interval(self,value):
        """ Seconds between reloading of allowed_dir or allowed_file and 
        allowed_ips and banned_ips lists.
        @param value A number of seconds.
        """
        self.sessconfig['tracker_parse_dir_interval'] = value

    def get_tracker_parse_dir_interval(self):
        """ Returns the number of seconds between refreshes of access control
        info.
        @return A number of seconds. """
        return self.sessconfig['tracker_parse_dir_interval']

    def set_tracker_scrape_allowed(self,value):
        """ Allow scrape access on the internal tracker (with a scrape request
        a BitTorrent client can retrieve information about how many peers are
        downloading the content.
        <pre>
        * ITRACKSCRAPE_ALLOW_NONE: Don't allow scrape requests.
        * ITRACKSCRAPE_ALLOW_SPECIFIC: Allow scrape requests for a specific torrent.
        * ITRACKSCRAPE_ALLOW_FULL: Allow scrape of all torrents at once.
        </pre>
        @param value ITRACKSCRAPE_* 
        """
        self.sessconfig['tracker_scrape_allowed'] = value

    def get_tracker_scrape_allowed(self):
        """ Returns the scrape access policy.
        @return ITRACKSCRAPE_ALLOW_* """
        return self.sessconfig['tracker_scrape_allowed']

    def set_tracker_allow_get(self,value):
        """ Setting this parameter adds a /file?hash={hash} links to the
        overview page that the internal tracker makes available via HTTP
        at hostname:listenport. These links allow users to download the 
        torrent file from the internal tracker. Use with 'allowed_dir' parameter.
        @param value Boolean.
        """
        self.sessconfig['tracker_allow_get'] = value

    def get_tracker_allow_get(self):
        """ Returns whether to allow HTTP torrent-file downloads from the
        internal tracker.
        @return Boolean. """
        return self.sessconfig['tracker_allow_get']


    #
    # Controls for internal tracker's output as Web server
    #
    def set_tracker_favicon(self,value):
        """ File containing image/x-icon data to return when browser requests 
        favicon.ico from the internal tracker. (Default = Tribler/Images/tribler.ico)
        @param value An absolute filename. 
        """
        self.sessconfig['tracker_favicon'] = value

    def get_tracker_favicon(self):
        """ Returns the filename of the internal tracker favicon. 
        @return An absolute path name. """
        return self.sessconfig['tracker_favicon']

    def set_tracker_show_infopage(self,value):
        """ Whether to display an info page when the tracker's root dir is 
        requested via HTTP.
        @param value Boolean
        """
        self.sessconfig['tracker_show_infopage'] = value

    def get_tracker_show_infopage(self):
        """ Returns whether to show an info page on the internal tracker. 
        @return Boolean. """
        return self.sessconfig['tracker_show_infopage']

    def set_tracker_infopage_redirect(self,value):
        """ A URL to redirect the request for an info page to.
        @param value URL.
        """
        self.sessconfig['tracker_infopage_redirect'] = value

    def get_tracker_infopage_redirect(self):
        """ Returns the URL to redirect request for info pages to. 
        @return URL """
        return self.sessconfig['tracker_infopage_redirect']

    def set_tracker_show_names(self,value):
        """ Whether to display names from the 'allowed dir'.
        @param value Boolean.
        """
        self.sessconfig['tracker_show_names'] = value

    def get_tracker_show_names(self):
        """ Returns whether the tracker displays names from the 'allowed dir'. 
        @return Boolean. """
        return self.sessconfig['tracker_show_names']

    def set_tracker_keep_dead(self,value):
        """ Keep dead torrents after they expire (so they still show up on your
        /scrape and web page)
        @param value Boolean.
        """
        self.sessconfig['tracker_keep_dead'] = value

    def get_tracker_keep_dead(self):
        """ Returns whether to keep dead torrents for statistics. 
        @return Boolean. """
        return self.sessconfig['tracker_keep_dead']

    #
    # Controls for internal tracker replies
    #
    def set_tracker_reannounce_interval(self,value):
        """ Seconds downloaders should wait between reannouncing themselves
        to the internal tracker.
        @param value A number of seconds.
        """
        self.sessconfig['tracker_reannounce_interval'] = value

    def get_tracker_reannounce_interval(self):
        """ Returns the reannounce interval for the internal tracker. 
        @return A number of seconds. """
        return self.sessconfig['tracker_reannounce_interval']

    def set_tracker_response_size(self,value):
        """ Number of peers to send to a peer in a reply to its announce
        at the internal tracker (i.e., in the info message)
        @param value A number of peers.
        """
        self.sessconfig['tracker_response_size'] = value

    def get_tracker_response_size(self):
        """ Returns the number of peers to send in a tracker reply. 
        @return A number of peers. """
        return self.sessconfig['tracker_response_size']

    def set_tracker_nat_check(self,value):
        """ How many times the internal tracker should attempt to check if a 
        downloader is behind a  Network Address Translator (NAT) or firewall.
        If it is, the downloader won't be registered at the tracker, as other
        peers can probably not contact it. 
        @param value A number of times, 0 = don't check.
        """
        self.sessconfig['tracker_nat_check'] = value

    def get_tracker_nat_check(self):
        """ Returns the number of times to check for a firewall.
        @return A number of times. """
        return self.sessconfig['tracker_nat_check']


    #
    # Internal tracker persistence
    #
    def set_tracker_dfile(self,value):
        """ File to store recent downloader info in (default = Session state 
        dir + STATEDIR_ITRACKER_DIR + tracker.db
        @param value An absolute path name.
        """
        self.sessconfig['tracker_dfile'] = value

    def get_tracker_dfile(self):
        """ Returns the tracker database file. 
        @return An absolute path name. """
        return self.sessconfig['tracker_dfile']

    def set_tracker_dfile_format(self,value):
        """ Format of the tracker database file. *_PICKLE is needed when Unicode
        filenames may appear in the tracker's state (=default).
        <pre>
         * ITRACKDBFORMAT_BENCODE: Use BitTorrent bencoding to store records.
         * ITRACKDBFORMAT_PICKLE: Use Python pickling to store records.
        </pre>
        @param value ITRACKDBFORFMAT_* 
        """
        self.sessconfig['tracker_dfile_format'] = value

    def get_tracker_dfile_format(self):
        """ Returns the format of the tracker database file. 
        @return ITRACKDBFORMAT_* """
        return self.sessconfig['tracker_dfile_format']

    def set_tracker_save_dfile_interval(self,value):
        """ The interval between saving the internal tracker's state to
        the tracker database (see set_tracker_dfile()).
        @param value A number of seconds.
        """
        self.sessconfig['tracker_save_dfile_interval'] = value

    def get_tracker_save_dfile_interval(self):
        """ Returns the tracker-database save interval. 
        @return A number of seconds. """
        return self.sessconfig['tracker_save_dfile_interval']

    def set_tracker_logfile(self,value):
        """ File to write the tracker logs to (default is NIL: or /dev/null).
        @param value A device name.
        """
        self.sessconfig['tracker_logfile'] = value

    def get_tracker_logfile(self):
        """ Returns the device name to write log messages to. 
        @return A device name. """
        return self.sessconfig['tracker_logfile']

    def set_tracker_min_time_between_log_flushes(self,value):
        """ Minimum time between flushes of the tracker log.
        @param value A number of seconds.
        """
        self.sessconfig['tracker_min_time_between_log_flushes'] = value

    def get_tracker_min_time_between_log_flushes(self):
        """ Returns time between tracker log flushes. 
        @return A number of seconds. """
        return self.sessconfig['tracker_min_time_between_log_flushes']

    def set_tracker_log_nat_checks(self,value):
        """ Whether to add entries to the tracker log for NAT-check results.
        @param value Boolean
        """
        self.sessconfig['tracker_log_nat_checks'] = value

    def get_tracker_log_nat_checks(self):
        """ Returns whether to log NAT-check attempts to the tracker log. 
        @return Boolean. """
        return self.sessconfig['tracker_log_nat_checks']

    def set_tracker_hupmonitor(self,value):
        """ Whether to reopen the tracker log file upon receipt of a SIGHUP 
        signal (Mac/UNIX only).
        @param value Boolean.
        """
        self.sessconfig['tracker_hupmonitor'] = value

    def get_tracker_hupmonitor(self):
        """ Returns whether to reopen the tracker log file upon receipt of a 
        SIGHUP signal. 
        @return Boolean. """
        return self.sessconfig['tracker_hupmonitor']


    #
    # Esoteric tracker config parameters 
    #
    def set_tracker_socket_timeout(self,value):
        """ Set timeout for closing connections to trackers.
        @param value A number of seconds.
        """
        self.sessconfig['tracker_socket_timeout'] = value

    def get_tracker_socket_timeout(self):
        """ Returns the tracker socket timeout. 
        @return A number of seconds. """
        return self.sessconfig['tracker_socket_timeout']

    def set_tracker_timeout_downloaders_interval(self,value):
        """ Interval between checks for expired downloaders, i.e., peers
        no longer in the swarm because they did not reannounce themselves.
        @param value A number of seconds.
        """
        self.sessconfig['tracker_timeout_downloaders_interval'] = value

    def get_tracker_timeout_downloaders_interval(self):
        """ Returns the number of seconds between checks for expired peers. 
        @return A number of seconds. """
        return self.sessconfig['tracker_timeout_downloaders_interval']

    def set_tracker_timeout_check_interval(self,value):
        """ Time to wait between checking if any connections to the internal
        tracker have timed out.
        @param value A number of seconds.
        """
        self.sessconfig['tracker_timeout_check_interval'] = value

    def get_tracker_timeout_check_interval(self):
        """ Returns timeout for connections to the internal tracker. 
        @return A number of seconds. """
        return self.sessconfig['tracker_timeout_check_interval']

    def set_tracker_min_time_between_cache_refreshes(self,value):
        """ Minimum time before a cache is considered stale and is 
        flushed.
        @param value A number of seconds.
        """
        self.sessconfig['tracker_min_time_between_cache_refreshes'] = value

    def get_tracker_min_time_between_cache_refreshes(self):
        """ Return the minimum time between cache refreshes.
        @return A number of seconds. """
        return self.sessconfig['tracker_min_time_between_cache_refreshes']


    #
    # BitTornado's Multitracker feature
    #
    def set_tracker_multitracker_enabled(self,value):
        """ Whether to enable multitracker operation in which multiple
        trackers are used to register the peers for a specific torrent.
        @param value Boolean.
        """
        self.sessconfig['tracker_multitracker_enabled'] = value

    def get_tracker_multitracker_enabled(self):
        """ Returns whether multitracking is enabled. 
        @return Boolean. """
        return self.sessconfig['tracker_multitracker_enabled']

    def set_tracker_multitracker_allowed(self,value):
        """ Whether to allow incoming tracker announces.
        <pre>
         * ITRACKMULTI_ALLOW_NONE: Don't allow.
         * ITRACKMULTI_ALLOW_AUTODETECT: Allow for allowed torrents (see set_tracker_allowed_dir())
         * ITRACKMULTI_ALLOW_ALL: Allow for all. 
        </pre>
        @param value ITRACKMULTI_ALLOW_*
        """
        self.sessconfig['tracker_multitracker_allowed'] = value

    def get_tracker_multitracker_allowed(self):
        """ Returns the multitracker allow policy of the internal tracker. 
        @return ITRACKMULTI_ALLOW_* """
        return self.sessconfig['tracker_multitracker_allowed']

    def set_tracker_multitracker_reannounce_interval(self,value):
        """ Seconds between outgoing tracker announces to the other trackers in
        a multi-tracker setup.
        @param value A number of seconds. 
        """
        self.sessconfig['tracker_multitracker_reannounce_interval'] = value

    def get_tracker_multitracker_reannounce_interval(self):
        """ Returns the multitracker reannouce interval. 
        @return A number of seconds. """
        return self.sessconfig['tracker_multitracker_reannounce_interval']

    def set_tracker_multitracker_maxpeers(self,value):
        """ Number of peers to retrieve from the other trackers in a tracker
         announce in a multi-tracker setup. 
         @param value A number of peers.
         """
        self.sessconfig['tracker_multitracker_maxpeers'] = value

    def get_tracker_multitracker_maxpeers(self):
        """ Returns the number of peers to retrieve from another tracker. 
        @return A number of peers. """
        return self.sessconfig['tracker_multitracker_maxpeers']

    def set_tracker_aggregate_forward(self,value):
        """ Set an URL to which, if set, all non-multitracker requests are
        forwarded, with a password added (optional).
        @param value A 2-item list with format: [<url>,<password>|None]
        """
        self.sessconfig['tracker_aggregate_forward'] = value

    def get_tracker_aggregate_forward(self):
        """ Returns the aggregate forward URL and optional password as a 2-item 
        list. 
        @return URL """
        return self.sessconfig['tracker_aggregate_forward']

    def set_tracker_aggregator(self,value):
        """ Whether to act as a data aggregator rather than a tracker. 
        To enable, set to True or <password>; if password is set, then an 
        incoming password is required for access.
        @param value Boolean or string.
        """
        self.sessconfig['tracker_aggregator'] = value

    def get_tracker_aggregator(self):
        """ Returns the tracker aggregator parameter. 
        @return Boolean or string. """
        return self.sessconfig['tracker_aggregator']

    def set_tracker_multitracker_http_timeout(self,value):
        """ Time to wait before assuming that an HTTP connection
        to another tracker in a multi-tracker setup has timed out. 
        @param value A number of seconds.
        """
        self.sessconfig['tracker_multitracker_http_timeout'] = value

    def get_tracker_multitracker_http_timeout(self):
        """ Returns timeout for inter-multi-tracker HTTP connections. 
        @return A number of seconds. """
        return self.sessconfig['tracker_multitracker_http_timeout']


    #
    # For Tribler superpeer servers
    #
    def set_superpeer(self,value):
        """ Run Session in super peer mode (default = disabled).
        @param value Boolean.
        """
        self.sessconfig['superpeer'] = value

    def get_superpeer(self):
        """ Returns whether the Session runs in superpeer mode. 
        @return Boolean. """
        return self.sessconfig['superpeer']

    def set_superpeer_file(self,value):
        """ File with addresses of superpeers (default = install_dir+
        Tribler/Core/superpeer.txt).
        @param value An absolute path name.
        """
        self.sessconfig['superpeer_file'] = value

    def get_superpeer_file(self):
        """ Returns the superpeer file.
        @return An absolute path name. """
        return self.sessconfig['superpeer_file']

    def set_overlay_log(self,value):
        """ File to log message to in super peer mode (default = No logging)
        @param value An absolute path name.
        """
        self.sessconfig['overlay_log'] = value

    def get_overlay_log(self):
        """ Returns the file to log messages to or None.
        @return An absolute path name. """
        return self.sessconfig['overlay_log']

    def set_coopdlconfig(self,dscfg):
        """ Sets the DownloadStartupConfig with which to start Downloads
        when you are asked to help in a cooperative download.
        """
        c = dscfg.copy()
        self.sessconfig['coopdlconfig'] = c.dlconfig # copy internal dict
        
    def get_coopdlconfig(self):
        """ Return the DownloadStartupConfig that is used when helping others
        in a cooperative download.
        @return DownloadStartupConfig
        """
        dlconfig = self.sessconfig['coopdlconfig']
        if dlconfig is None:
            return None
        else:
            from Tribler.Core.DownloadConfig import DownloadStartupConfig 
            return DownloadStartupConfig(dlconfig)
        

    #
    # NAT Puncturing servers information setting
    #
    def set_nat_detect(self,value):
        """ Whether to try to detect the type of Network Address Translator
        in place.
        @param value Boolean.
        """
        self.sessconfig['nat_detect'] = value
    
    def set_puncturing_internal_port(self, puncturing_internal_port):
        """ The listening port of the puncturing module.
        @param puncturing_internal_port integer. """
        self.sessconfig['puncturing_internal_port'] = puncturing_internal_port

    def set_stun_servers(self, stun_servers):
        """ The addresses of the STUN servers (at least 2)
        @param stun_servers List of (hostname/ip,port) tuples. """
        self.sessconfig['stun_servers'] = stun_servers

    def set_pingback_servers(self, pingback_servers):
        """ The addresses of the pingback servers (at least 1)
        @param pingback_servers List of (hostname/ip,port) tuples. """
        self.sessconfig['pingback_servers'] = pingback_servers

    # Puncturing servers information retrieval
    def get_nat_detect(self):
        """ Whether to try to detect the type of Network Address Translator
        in place.
        @return Boolean
        """
        return self.sessconfig['nat_detect']
    
    def get_puncturing_internal_port(self):
        """ Returns the listening port of the puncturing module.
        @return integer. """
        return self.sessconfig['puncturing_internal_port']

    def get_stun_servers(self):
        """ Returns the addresses of the STUN servers.
        @return List of (hostname/ip,port) tuples. """
        return self.sessconfig['stun_servers']

    def get_pingback_servers(self):
        """ Returns the addresses of the pingback servers.
        @return List of (hostname/ip,port) tuples. """
        return self.sessconfig['pingback_servers']

    #
    # Crawler
    #
    def set_crawler(self, value):
        """ Handle crawler messages when received (default = True)
        @param value Boolean
        """
        self.sessconfig['crawler'] = value

    def get_crawler(self):
        """ Whether crawler messages are processed
        @return Boolean. """
        return self.sessconfig['crawler']
    
    # 
    # Local Peer Discovery using IP Multicast
    #
    def set_multicast_local_peer_discovery(self,value):
        """ Set whether the Session tries to detect local peers
        using a local IP multicast. Overlay swarm (set_overlay()) must
        be enabled as well.
        @param value Boolean
        """
        self.sessconfig['multicast_local_peer_discovery'] = value
        
    def get_multicast_local_peer_discovery(self):
        """
        Returns whether local peer discovery is enabled.
        @return Boolean
        """
        return self.sessconfig['multicast_local_peer_discovery']

    #
    # VoteCast
    #
    def set_votecast_recent_votes(self, value):
        """ Sets the maximum limit for the recent votes by the user, 
        that will be forwarded to connected peers 
        @param value int 
        """
        self.sessconfig['votecast_recent_votes'] = value 

    def get_votecast_recent_votes(self):
        """ Returns the maximum limit for the recent votes by the user, 
        that will be forwarded to connected peers 
        @return int 
        """
        return self.sessconfig['votecast_recent_votes']
    
    def set_votecast_random_votes(self, value):
        """ Sets the maximum limit for the user's votes that are different from recent ones
        but selected randomly; these votes will be forwarded to connected peers along with recent votes 
        @param value int 
        """
        self.sessconfig['votecast_random_votes'] = value

    def get_votecast_random_votes(self):
        """ Returns the maximum limit for the user's votes that are different from recent ones
        but selected randomly; these votes will be forwarded to connected peers along with recent votes 
        @return int 
        """        
        return self.sessconfig['votecast_random_votes']

    #
    # ChannelCast
    #
    def set_channelcast_recent_own_subscriptions(self, value):
        """ Sets the maximum limit for the recent subscriptions by the user, 
        that will be forwarded to connected peers 
        @param value int 
        """
        self.sessconfig['channelcast_recent_own_subscriptions'] = value

    def get_channelcast_recent_own_subscriptions(self):
        """ Returns the maximum limit for the recent subscriptions by the user, 
        that will be forwarded to connected peers 
        @return int 
        """
        return self.sessconfig['channelcast_recent_own_subscriptions']
    
    def set_channelcast_random_own_subscriptions(self, value):
        """ Sets the maximum limit for the user's subscriptions that are different from recent ones
        but selected randomly; these subscriptions will be forwarded to connected peers 
        @param value int 
        """
        self.sessconfig['channelcast_random_own_subscriptions'] = value

    def get_channelcast_random_own_subscriptions(self):
        """ Returns the maximum limit for the user's subscriptions that are different from recent ones
        but selected randomly; these subscriptions will be forwarded to connected peers 
        @return int 
        """
        return self.sessconfig['channelcast_random_own_subscriptions']
    


class SessionStartupConfig(SessionConfigInterface,Copyable,Serializable):  
    """ Class to configure a Session """
    
    def __init__(self,sessconfig=None):
        SessionConfigInterface.__init__(self,sessconfig)

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
        f = open(filename,"rb")
        sessconfig = pickle.load(f)
        sscfg = SessionStartupConfig(sessconfig)
        f.close()
        return sscfg
    load = staticmethod(load)

    def save(self,filename):
        """ Save the SessionStartupConfig to disk.
        @param filename  An absolute Unicode filename
        """
        # Called by any thread
        f = open(filename,"wb")
        pickle.dump(self.sessconfig,f)
        f.close()

    #
    # Copyable interface
    # 
    def copy(self):
        config = copy.copy(self.sessconfig)
        return SessionStartupConfig(config)

# Written by Arno Bakker 
# see LICENSE.txt for license information

import sys
from traceback import print_exc

from Tribler.Core.simpledefs import *
from Tribler.Core.defaults import sessdefaults
from Tribler.Core.Base import *
from Tribler.Core.BitTornado.RawServer import autodetect_socket_style
from Tribler.Core.Utilities.utilities import find_prog_in_PATH,validTorrentFile,isValidURL


class SessionConfigInterface:
    """ 
    (key,value) pair config of global parameters, 
    e.g. PermID keypair, listen port, max upload speed, etc.
    
    Use SessionStartupConfig from creating and manipulation configurations
    before session startup time. This is just a parent class.
    """
    def __init__(self,sessconfig=None):
        
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
                self.sessconfig['videoanalyserpath'] = "lib/ffmpeg"
            else:
                self.sessconfig['videoanalyserpath'] = ffmpegname
        else:
            self.sessconfig['videoanalyserpath'] = ffmpegpath

        self.sessconfig['ipv6_binds_v4'] = autodetect_socket_style()

    def set_state_dir(self,statedir):
        self.sessconfig['state_dir'] = statedir
    
    def get_state_dir(self):
        return self.sessconfig['state_dir']
    
    def set_install_dir(self,installdir):
        self.sessconfig['install_dir'] = installdir
    
    def get_install_dir(self):
        return self.sessconfig['install_dir']
    
    def set_permid(self,keypairfilename):
        self.sessconfig['eckeypairfilename'] = keypairfilename

    def get_permid(self):
        return self.sessconfig['eckeypairfilename']
        
    def set_listen_port(self,port):
        """
        FUTURE: do we allow runtime modification of this param? Theoretically
        possible, a bit hard to implement
        """
        self.sessconfig['minport'] = port
        self.sessconfig['maxport'] = port

    def get_listen_port(self):
        return self.sessconfig['minport']
        
    #
    # Advanced network settings
    #
    def set_ip_for_tracker(self,value):
        """ ip to report you have to the tracker (default = set automatically) """
        self.sessconfig['ip'] = value

    def get_ip_for_tracker(self):
        return self.sessconfig['ip']

    def set_bind_to_address(self,value):
        """ comma-separated list of ips/hostnames to bind to locally """
        self.sessconfig['bind'] = value

    def get_bind_to_address(self):
        return self.sessconfig['bind']

    def set_upnp_mode(self,value):
        """ attempt to autoconfigure a UPnP router to forward a server port 
        (0 = disabled, 1 = mode 1 [fast,win32], 2 = mode 2 [slow,win32], 3 = 
        mode 3 [any platform]) """
        self.sessconfig['upnp_nat_access'] = value

    def get_upnp_mode(self):
        return self.sessconfig['upnp_nat_access']

    def set_autoclose_timeout(self,value):
        """ time to wait between closing sockets which nothing has been received
        on """
        self.sessconfig['timeout'] = value

    def get_autoclose_timeout(self):
        return self.sessconfig['timeout']

    def set_autoclose_check_interval(self,value):
        """ time to wait between checking if any connections have timed out """
        self.sessconfig['timeout_check_interval'] = value

    def get_autoclose_check_interval(self):
        return self.sessconfig['timeout_check_interval']

    #
    # Enable/disable Tribler features 
    #
    def set_megacache(self,value):
        """ Enable megacache databases to cache peers, torrent files and 
        preferences (default = True)"""
        self.sessconfig['megacache'] = value

    def get_megacache(self):
        return self.sessconfig['megacache']

    #
    # Secure Overlay
    #
    def set_overlay(self,value):
        """ Enable overlay swarm to enable Tribler's special features 
        (default = True) """
        self.sessconfig['overlay'] = value

    def get_overlay(self):
        return self.sessconfig['overlay']

    def set_overlay_max_message_length(self,value):
        """ maximal messagelength over the secure overlay """
        self.sessconfig['overlay_max_message_length'] = value

    def get_overlay_max_message_length(self):
        return self.sessconfig['overlay_max_message_length']


    #
    # Buddycast
    #
    def set_buddycast(self,value):
        """ Enable buddycast recommendation system at startup (default = True)
        """
        self.sessconfig['buddycast'] = value

    def get_buddycast(self):
        return self.sessconfig['buddycast']

    def set_start_recommender(self,value):
        """ Buddycast can be temp. disabled via this flag 
        (default = True) """
        self.sessconfig['start_recommender'] = value

    def get_start_recommender(self):
        return self.sessconfig['start_recommender']

    def set_buddycast_interval(self,value):
        """ number of seconds to pause between exchanging preference with a 
        peer in buddycast """
        self.sessconfig['buddycast_interval'] = value

    def get_buddycast_interval(self):
        return self.sessconfig['buddycast_interval']

    def set_buddycast_collecting_solution(self,value):
        """ 1: simplest solution: per torrent/buddycasted peer/4hours, 2: tig for tag on group base """
        self.sessconfig['buddycast_collecting_solution'] = value

    def get_buddycast_collecting_solution(self):
        return self.sessconfig['buddycast_collecting_solution']

    #
    # Download helper / cooperative download
    #
    def set_download_help(self,value):
        """ accept download help request (default = True) """
        self.sessconfig['download_help'] = value

    def get_download_help(self):
        return self.sessconfig['download_help']

    def set_download_help_dir(self,value):
        """ directory from download_help relative to state_dir """
        self.sessconfig['download_help_dir'] = value

    def get_download_help_dir(self):
        return self.sessconfig['download_help_dir']

    #
    # Torrent file collecting
    #
    def set_torrent_collecting(self,value):
        """ automatically collect torrents (default = True)"""
        self.sessconfig['torrent_collecting'] = value

    def get_torrent_collecting(self):
        return self.sessconfig['torrent_collecting']

    def set_max_torrents(self,value):
        """ max number of torrents to collect """
        self.sessconfig['max_torrents'] = value

    def get_max_torrents(self):
        return self.sessconfig['max_torrents']

    def set_torrent_collecting_dir(self,value):
        """ where to place collected torrents? (default is state_dir + 'colltorrents'"""
        self.sessconfig['torrent_collecting_dir'] = value

    def get_torrent_collecting_dir(self):
        return self.sessconfig['torrent_collecting_dir']

    def set_torrent_collecting_rate(self,value):
        """ max rate of torrent collecting (Kbps) """
        self.sessconfig['torrent_collecting_rate'] = value

    def get_torrent_collecting_rate(self):
        return self.sessconfig['torrent_collecting_rate']

    def set_torrent_checking(self,value):
        """ automatically check the health of torrents by contacting tracker
        (default = True) """
        self.sessconfig['torrent_checking'] = value

    def get_torrent_checking(self):
        return self.sessconfig['torrent_checking']

    def set_torrent_checking_period(self,value):
        """ period for auto torrent checking """
        self.sessconfig['torrent_checking_period'] = value

    def get_torrent_checking_period(self):
        return self.sessconfig['torrent_checking_period']

    def set_stop_collecting_threshold(self,value):
        """ stop collecting more torrents if the disk has less than this size 
        (MB) """
        self.sessconfig['stop_collecting_threshold'] = value

    def get_stop_collecting_threshold(self):
        return self.sessconfig['stop_collecting_threshold']


    #
    # The Tribler dialback mechanism is used to test whether a Session is
    # reachable from the outside and what its external IP address is.
    #
    def set_dialback(self,value):
        """ use other peers to determine external IP address (default = True) 
        """
        self.sessconfig['dialback'] = value

    def get_dialback(self):
        return self.sessconfig['dialback']

    def set_dialback_interval(self,value):
        """ number of seconds to wait for consensus """
        self.sessconfig['dialback_interval'] = value

    def get_dialback_interval(self):
        return self.sessconfig['dialback_interval']

    #
    # Tribler's social networking feature transmits a nickname and picture
    # to all Tribler peers it meets.
    #
    def set_social_networking(self,value):
        """ enable social networking (default = True) """
        self.sessconfig['socnet'] = value

    def get_social_networking(self):
        return self.sessconfig['socnet']

    def set_nickname(self,value):  # TODO: put in PeerDBHandler? Add method for setting own pic
        """ the nickname you want to show to others """
        self.sessconfig['nickname'] = value

    def get_nickname(self):
        return self.sessconfig['nickname']

    def set_peer_icon_path(self,value):
        """ directory to store peer icons, relative to statedir """
        self.sessconfig['peer_icon_path'] = value

    def get_peer_icon_path(self):
        return self.sessconfig['peer_icon_path']

    #
    # Tribler remote query: ask other peers when looking for a torrent file 
    # or peer
    #
    def set_remote_query(self,value):
        """ enable remote query (default = True) """
        self.sessconfig['rquery'] = value

    def get_remote_query(self):
        return self.sessconfig['rquery']

    #
    # BarterCast
    #
    def set_bartercast(self,value):
        """ exchange upload/download statistics with peers """
        self.sessconfig['bartercast'] = value

    def get_bartercast(self):
        return self.sessconfig['bartercast']


    #
    # For Tribler Video-On-Demand
    #
    def set_video_analyser_path(self,value):
        """ Path to video analyser (FFMPEG, default is to look for it in $PATH) """
        self.sessconfig['videoanalyserpath'] = value
    
    def get_video_analyser_path(self):
        return self.sessconfig['videoanalyserpath'] # strings immutable
    


    def set_video_player_path(self,value):
        """ Path to default video player. Defaults are
            win32: Windows Media Player
            Mac: QuickTime Player
            Linux: VideoLAN Client (vlc) 
            which are looked for in $PATH """
        self.sessconfig['videoplayerpath'] = value

    def get_video_player_path(self):
        return self.sessconfig['videoplayerpath']


    #
    # Tribler's internal tracker
    #
    def set_internal_tracker(self,value):
        """ enable internal tracker (default = True) """
        self.sessconfig['internaltracker'] = value

    def get_internal_tracker(self):
        return self.sessconfig['internaltracker']

    def set_tracker_allow_get(self,value):
        """ use with allowed_dir; adds a /file?hash={hash} url that allows users
        to download the torrent file """
        self.sessconfig['tracker_allow_get'] = value

    def get_tracker_allow_get(self):
        return self.sessconfig['tracker_allow_get']

    def set_tracker_scrape_allowed(self,value):
        """ scrape access allowed (can be none, specific or full) """
        self.sessconfig['tracker_scrape_allowed'] = value

    def get_tracker_scrape_allowed(self):
        return self.sessconfig['tracker_scrape_allowed']

    def set_tracker_favicon(self,value):
        """ file containing x-icon data to return when browser requests 
        favicon.ico """
        self.sessconfig['tracker_favicon'] = value

    def get_tracker_favicon(self):
        return self.sessconfig['tracker_favicon']

    #
    # Advanced internal tracker settings
    #
    def set_tracker_allowed_dir(self,value):
        """ only allow downloads for .torrents in this dir (default is Session 
        state-dir/itracker/ """
        self.sessconfig['tracker_allowed_dir'] = value

    def get_tracker_allowed_dir(self):
        return self.sessconfig['tracker_allowed_dir']

    def set_tracker_dfile(self,value):
        """ file to store recent downloader info in (default = Session state 
        dir/itracker/tracker.db """
        self.sessconfig['tracker_dfile'] = value

    def get_tracker_dfile(self):
        return self.sessconfig['tracker_dfile']

    def set_tracker_dfile_format(self,value):
        """ format of dfile: either "bencode" or pickle. Pickle is needed when
        Unicode filenames in state (=default) """
        self.sessconfig['tracker_dfile_format'] = value

    def get_tracker_dfile_format(self):
        return self.sessconfig['tracker_dfile_format']

    def set_tracker_multitracker_enabled(self,value):
        """ whether to enable multitracker operation """
        self.sessconfig['tracker_multitracker_enabled'] = value

    def get_tracker_multitracker_enabled(self):
        return self.sessconfig['tracker_multitracker_enabled']

    def set_tracker_multitracker_allowed(self,value):
        """ whether to allow incoming tracker announces (can be none, autodetect
        or all) """
        self.sessconfig['tracker_multitracker_allowed'] = value

    def get_tracker_multitracker_allowed(self):
        return self.sessconfig['tracker_multitracker_allowed']

    def set_tracker_multitracker_reannounce_interval(self,value):
        """ seconds between outgoing tracker announces """
        self.sessconfig['tracker_multitracker_reannounce_interval'] = value

    def get_tracker_multitracker_reannounce_interval(self):
        return self.sessconfig['tracker_multitracker_reannounce_interval']

    def set_tracker_multitracker_maxpeers(self,value):
        """ number of peers to get in a tracker announce """
        self.sessconfig['tracker_multitracker_maxpeers'] = value

    def get_tracker_multitracker_maxpeers(self):
        return self.sessconfig['tracker_multitracker_maxpeers']

    def set_tracker_aggregate_forward(self,value):
        """ format: <url>[,<password>] - if set, forwards all non-multitracker 
        to this url with this optional password """
        self.sessconfig['tracker_aggregate_forward'] = value

    def get_tracker_aggregate_forward(self):
        return self.sessconfig['tracker_aggregate_forward']

    def set_tracker_aggregator(self,value):
        """ whether to act as a data aggregator rather than a tracker. If 
        enabled, may be 1, or <password>; if password is set, then an incoming 
        password is required for access """
        self.sessconfig['tracker_aggregator'] = value

    def get_tracker_aggregator(self):
        return self.sessconfig['tracker_aggregator']

    def set_tracker_socket_timeout(self,value):
        """ timeout for closing connections """
        self.sessconfig['tracker_socket_timeout'] = value

    def get_tracker_socket_timeout(self):
        return self.sessconfig['tracker_socket_timeout']

    def set_tracker_save_dfile_interval(self,value):
        """ seconds between saving dfile """
        self.sessconfig['tracker_save_dfile_interval'] = value

    def get_tracker_save_dfile_interval(self):
        return self.sessconfig['tracker_save_dfile_interval']

    def set_tracker_timeout_downloaders_interval(self,value):
        """ seconds between expiring downloaders """
        self.sessconfig['tracker_timeout_downloaders_interval'] = value

    def get_tracker_timeout_downloaders_interval(self):
        return self.sessconfig['tracker_timeout_downloaders_interval']

    def set_tracker_reannounce_interval(self,value):
        """ seconds downloaders should wait between reannouncements """
        self.sessconfig['tracker_reannounce_interval'] = value

    def get_tracker_reannounce_interval(self):
        return self.sessconfig['tracker_reannounce_interval']

    def set_tracker_response_size(self,value):
        """ number of peers to send in an info message """
        self.sessconfig['tracker_response_size'] = value

    def get_tracker_response_size(self):
        return self.sessconfig['tracker_response_size']

    def set_tracker_timeout_check_interval(self,value):
        """ time to wait between checking if any connections have timed out """
        self.sessconfig['tracker_timeout_check_interval'] = value

    def get_tracker_timeout_check_interval(self):
        return self.sessconfig['tracker_timeout_check_interval']

    def set_tracker_nat_check(self,value):
        """ how many times to check if a downloader is behind a NAT (0 = don't 
        check) """
        self.sessconfig['tracker_nat_check'] = value

    def get_tracker_nat_check(self):
        return self.sessconfig['tracker_nat_check']

    def set_tracker_log_nat_checks(self,value):
        """ whether to add entries to the log for NAT-check results """
        self.sessconfig['tracker_log_nat_checks'] = value

    def get_tracker_log_nat_checks(self):
        return self.sessconfig['tracker_log_nat_checks']

    def set_tracker_min_time_between_log_flushes(self,value):
        """ minimum time it must have been since the last flush to do another 
        one """
        self.sessconfig['tracker_min_time_between_log_flushes'] = value

    def get_tracker_min_time_between_log_flushes(self):
        return self.sessconfig['tracker_min_time_between_log_flushes']

    def set_tracker_min_time_between_cache_refreshes(self,value):
        """ minimum time in seconds before a cache is considered stale and is 
        flushed """
        self.sessconfig['tracker_min_time_between_cache_refreshes'] = value

    def get_tracker_min_time_between_cache_refreshes(self):
        return self.sessconfig['tracker_min_time_between_cache_refreshes']

    def set_tracker_allowed_list(self,value):
        """ only allow downloads for hashes in this list (hex format, one per 
        line) """
        self.sessconfig['tracker_allowed_list'] = value

    def get_tracker_allowed_list(self):
        return self.sessconfig['tracker_allowed_list']

    def set_tracker_allowed_controls(self,value):
        """ allow special keys in torrents in the allowed_dir to affect tracker
        access """
        self.sessconfig['tracker_allowed_controls'] = value

    def get_tracker_allowed_controls(self):
        return self.sessconfig['tracker_allowed_controls']

    def set_tracker_hupmonitor(self,value):
        """ whether to reopen the log file upon receipt of HUP signal """
        self.sessconfig['tracker_hupmonitor'] = value

    def get_tracker_hupmonitor(self):
        return self.sessconfig['tracker_hupmonitor']

    def set_tracker_http_timeout(self,value):
        """ number of seconds to wait before assuming that an HTTP connection
        has timed out """
        self.sessconfig['tracker_http_timeout'] = value

    def get_tracker_http_timeout(self):
        return self.sessconfig['tracker_http_timeout']

    def set_tracker_parse_dir_interval(self,value):
        """ seconds between reloading of allowed_dir or allowed_file and 
        allowed_ips and banned_ips lists """
        self.sessconfig['tracker_parse_dir_interval'] = value

    def get_tracker_parse_dir_interval(self):
        return self.sessconfig['tracker_parse_dir_interval']

    def set_tracker_show_infopage(self,value):
        """ whether to display an info page when the tracker's root dir is 
        loaded """
        self.sessconfig['tracker_show_infopage'] = value

    def get_tracker_show_infopage(self):
        return self.sessconfig['tracker_show_infopage']

    def set_tracker_infopage_redirect(self,value):
        """ a URL to redirect the info page to """
        self.sessconfig['tracker_infopage_redirect'] = value

    def get_tracker_infopage_redirect(self):
        return self.sessconfig['tracker_infopage_redirect']

    def set_tracker_show_names(self,value):
        """ whether to display names from allowed dir """
        self.sessconfig['tracker_show_names'] = value

    def get_tracker_show_names(self):
        return self.sessconfig['tracker_show_names']

    def set_tracker_allowed_ips(self,value):
        """ only allow connections from IPs specified in the given file; file 
        contains subnet data in the format: aa.bb.cc.dd/len """
        self.sessconfig['tracker_allowed_ips'] = value

    def get_tracker_allowed_ips(self):
        return self.sessconfig['tracker_allowed_ips']

    def set_tracker_banned_ips(self,value):
        """ don't allow connections from IPs specified in the given file; file
        contains IP range data in the format: xxx:xxx:ip1-ip2 """
        self.sessconfig['tracker_banned_ips'] = value

    def get_tracker_banned_ips(self):
        return self.sessconfig['tracker_banned_ips']

    def set_tracker_only_local_override_ip(self,value):
        """ ignore the ip GET parameter from machines which aren't on local 
        network IPs (0 = never, 1 = always, 2 = ignore if NAT checking is not 
        enabled) """
        self.sessconfig['tracker_only_local_override_ip'] = value

    def get_tracker_only_local_override_ip(self):
        return self.sessconfig['tracker_only_local_override_ip']

    def set_tracker_logfile(self,value):
        """ file to write the tracker logs, use - for stdout (default is 
        /dev/null) """
        self.sessconfig['tracker_logfile'] = value

    def get_tracker_logfile(self):
        return self.sessconfig['tracker_logfile']

    def set_tracker_keep_dead(self,value):
        """ keep dead torrents after they expire (so they still show up on your /scrape and web page) """
        self.sessconfig['tracker_keep_dead'] = value

    def get_tracker_keep_dead(self):
        return self.sessconfig['tracker_keep_dead']

    #
    # For Tribler superpeer servers
    #
    def set_superpeer(self,value):
        """ run in super peer mode (0 = disabled) """
        self.sessconfig['superpeer'] = value

    def get_superpeer(self):
        return self.sessconfig['superpeer']

    def set_superpeer_file(self,value):
        """ file with addresses of superpeers, relative to install_dir """
        self.sessconfig['superpeer_file'] = value

    def get_superpeer_file(self):
        return self.sessconfig['superpeer_file']

    def set_overlay_log(self,value):
        """ log on super peer mode ('' = disabled) """
        self.sessconfig['overlay_log'] = value

    def get_overlay_log(self):
        return self.sessconfig['overlay_log']

class SessionStartupConfig(SessionConfigInterface,Copyable,Serializable):  
    """ Class to configure a Session """
    
    def __init__(self,sessconfig=None):
        SessionConfigInterface.__init__(self,sessconfig)

    #
    # Copyable interface
    # 
    def copy(self):
        config = copy.copy(self.sessconfig)
        return SessionStartupConfig(config)

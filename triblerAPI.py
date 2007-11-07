# Written by Arno Bakker 
# see LICENSE.txt for license information

"""
triblerAPI v0.0.2rc1
Oct 24, 2007 

Using Python style guide

Simplest download session
=========================
    s = Session()
    tdef = TorrentDef.load('/tmp/bla.torrent')
    d = s.start_download(tdef)
    d.set_state_callback(state_callback)
    
def state_callback(ds):
    d = ds.get_download()
    print `d.get_def().get_name()`,ds.get_status(),ds.get_progress(),ds.get_error(),"up",ds.get_current_speed(UPLOAD),"down",ds.get_current_speed(DOWNLOAD)
    return (5.0,False)


Simpler download session
========================
    s = Session()
    tdef = TorrentDef.load('/tmp/bla.torrent')
    dcfg = DownloadStartupConfig()
    dcfg.set_dest_dir('/tmp')
    d = s.start_download(tdef,dcfg)


Simple VOD download session
===========================
    s = Session()
    tdef = TorrentDef.load('/tmp/bla.torrent')
    dcfg = DownloadStartupConfig()
    dcfg.set_video_on_demand(vod_ready_callback)
    dcfg.set_selected_files('part2.avi') # play this video
    d = s.start_download(tdef,dcfg)
    
def vod_ready_callback(download,mimetype,stream,filename):
    # Called by new thread 
    while True:
        data = stream.read()
        if len(data) == 0:
            break
        outstream.write(data)
    stream.close()
        
ALTERNATIVE: the user passes a block_ready_callback, which we call every time
a new block comes in. This may be less desirable, as the user then has to
concurrency control to balance the writer (the core) and the reader (e.g. HTTP
socket). 

In this vod_ready_callback scenario, we do the producer/consumer problem
inside the stream object, blocking the new thread as desired. Note that it must 
be a new thread and not the network thread that calls vod_ready_callback().        
Another advantage of vod_ready is that users can pass the stream object to an
HTTP server which can then record a (path,stream) tuple, and start reading from
the given stream when the path is requested via GET /path HTTP/1.1). Or 
play the video from the file directly if it is complete. We throw IOExceptions 
when the VOD download is stopped / removed.
        

Simplest seeding session
========================
    s = Session().get_instance()
    # default torrent def is to use internal tracker
    tdef = TorrentDef.get_copy_of_default()
    tdef.add_file('/tmp/homevideo.wmv')
    d = s.start_download(tdef)


Simpler seeding session
=======================
    s = Session().get_instance()
    tdef.add_file('/tmp/homevideo.wmv')
    tdef = TorrentDef.get_default() 
    tdef.add_file('/tmp/homevideo.wmv')
    tdef.set_thumbnail('/tmp/homevideo.jpg')
    d = s.start_download(tdef)



Rationale
=========
The core API is inspired by the libtorrent interface but makes all 
configurations first-class objects such that they can be independently 
manipulated (i.e., loaded, saved, set as default). Making configurations first-
class objects requires special measures because of their dual nature. First, 
when the download engine or individual download has not yet started, 
configurations are more or less (key,value) pairs. Second, when the downloads
have started the configuration represents actual parameters in the download
engine, and when config parameters are changed one expects that
the engine's behaviour also changes directly.

To support configs as first-class objects we therefore distinguish between bound
and unbound configs. A bound config is associated with the download engine via 
a Session or Download object. Changing the values of a bound config will alter
the behaviour of the download in a thread safe way. 

Thread Safety
=============
Unbound configs are not thread safe. To prevent concurrency issues, unbound 
configs passed to a Session/Download object are first copied and the copy is 
then bound. When passing an unbound config to be bound it may not be modified 
concurrently. Bound configs are thread safe, as just mentioned. Setting defaults
is also not thread safe, so you must ensure there are no concurrent calls.

All calls to Session, Download and DownloadState are thread safe.

DONE: Define whether changes to runtime configs is synchronous, i.e., does
dcfg.set_max_upload(100) sets the upload limit before returning, or 
asynchronous. SOL: easiest is async, as network thread does actual changing
2007-10-15: can use Download condition variable for synchronous perhaps?
2007-10-16: It's all async, errors are reported via callbacks (if needed), 
and generally for Downloads via the DownloadState. 

ALTERNATIVE:
Use copy in/out semantics for TorrentDef and DownloadStartupConfig. A 
disadvantage of copy in/out is that people may forget to call the copy in 
method.


Persistence Support
===================
We use the Python pickling mechanism to make objects persistent. We add a
version number to the state before it is saved. To indicate serializability
classes inherit from the Serializable interface.  For a Session there is a 
special checkpointing mechanism. 

ALTERNATIVE: 
We provide save/load methods. An issue then is do we use filenames as args or 
file objects like Java uses Input/OutputStreams. The advantage of the latter is
that we can have simple load()/save() methods on each class which e.g. the 
Download save_resume_file() can use to marshall all its parts and write them 
to a single file. Disadvantage is that the used has to open the file always:

    f = open("bla.torrent","rb")
    tdef = TorrentDef.load(f)
    f.close()
    
instead of

    tdef = TorrentDef.load()
    
Note that using streams is more errorprone, e.g. when the user opens a torrent
file in non-binary mode by mistake (f = open("bla.torrent","r") this causes
troubles for us. Not using streams leads to double methods, i.e. Fileable and
Serializable


Session Object
==============
FUTURE: Theoretically, Session can be a real class with multiple instances. For
implementation purposes making it a Singleton is easier, as a lot of our 
internal stuff are currently singletons (e.g. databases and *MsgHandler, etc.)
SOL: singleton for now, interface should allow more.

Modifiability of parameters
===========================
Many configuration parameters may be modified at runtime. Some parameters may
be theoretically modifiable but implementing this behaviour may be too complex.
The class definitions indicate which parameters are runtime modifiable, and
points of attention.

For example, changing the destination dir of a download a runtime is possible,
but complex to implement.

Note that some parameters should be modified with great care. For example.
the listen = tracker port of a Session can be easily modified, but if the 
Session had been used to create new torrents that have been distributed to Web
sites, you cannot simply change the listening port as it means that all torrent 
files out in the world become invalid.

Push/pull
=========
DownloadState is currently pulled periodically from the BT engine. ALTERNATIVE
is an push-based mechanism, i.e. event driven. Advantage over pull: always 
accurate. Disadv: how does that work? Do we callback for every change in state, 
from peer DL speed to...? Tribler currently does periodic pull. You will want to 
batch things in time (once per sec) and per item (i.e., all events for 1 torrent
in one batch)

        
Alternative names for "Download"
================================
Exchange, i.e. start_exchange()
Replica, i.e. create_replica(), remove_replica() which abstractly is exactly 
what BT does. When you start a seed, you basically create a replica. When you 
start a download you want to create a copy on your local system, i.e. create a
replica there.
"""

"""
TODO:

- queuing of torrents that get activated when others upload low?
    This relates to unsupervised usage: people turn on tribler,
    add a couple of torrents to download and then go away, expecting
    them all to be finished, perhaps with priority.
    Same for seeding: Tribler now allows seeding up to specific ul/dl ratio,
    for a specified period of time.
    
    
    We can leave this up to the API user, just providing the mechanism
    or offer a standard model.
    
    Freek says: leave out of core. My addition: OK, but offer standard
    modules that work on core that use this.
    One implication is that we don't have a set_max_upload() on Session level,
    just Download.
    
- local/global ratelimiter
    What is a good policy here? Dividing a global max over the number of 
    torrents may not be ideal, if some torrents don't achieve their allocated
    speed, perhaps others could have used it.
    
    ABC/Scheduler/ratemanager appears to do this. 2007-10-19: A port of this to
    the triblerAPI failed, funky algorithmics. Added an extensible rate mgmt
    mechanism and a simple rate manager.

- Create a rate manager that gives unused capacity to download that is at max
        See UserDefinedMaxAlwaysOtherwiseDividedOnDemandRateManager. 
        Need to TEST

- Allow VOD when first part of file hashchecked? For faster start of playback

- Is there a state where the file complete but not yet in order on disk?

- Reimplement selected_files with existing 'priority' field

- TorrentDef:
    Should we make this a simple dict interface, or provide user-friendly
    functions for e.g. handling encoding issues for filenames, setting 
    thumbnails, etc. 
    
    My proposal is to have both, so novice users can use the simple ones, and 
    advanced users can still control all fields.


- *Config: some values will be runtime modifiable, others may be as well
    but hard to implement, e.g. destdir or VOD.
    SOL: We throw exceptions when it is not runtime modifiable, and 
    document for each method which currently is. TODO: determine which and 
    document.


- Move all sourcecode to a tribler dir? So we can do:
    import tribler
    s = tribler.Session()
    etc.

- persistence
 
    pstate: save TorrentDef rather than metafinfo? to be consistent?
    Saving internal state is more flex
    Saving objects is easier, but potentially less efficient as all sort of temp
    junk is written as well

- Add ability to run a standalone tracker based on API

- Test VOD quick startup with multi-file torrent. PiecePicker.am_I_complete is
  about whole file.

- BT1/Connecter: if 'cache' in config and config['cache']: # TEMP ARNO: TODO: WE EXPECT A SESSION CONFIG HERE

- BT1/Rerequester: if 'dialback' in self.config and self.config['dialback']: EXPECT SESSION CONFIG AND SEE WHO KNOWS CONNECTABLE

- VOD: Check why prebuf pieces not obtained and implement rerequest of pieces
  if needed.
      See PiecePickerVOD: self.outstanding, need to tweak further

- TODO: determine what are fatal errors for a tracker and move to 
  DLSTATUS_STOPPED_ON_ERROR if they occur. Currently all tracker errors are
  put in log messages, and the download does not change status.

- Document all methods in the API.

- TODO: move API.launchmanycore to API.Impl.LaunchManyCore.py

"""

import sys
import os
import time
import copy
import sha
import pickle
import binascii
import shutil
from UserDict import DictMixin
from threading import RLock,Thread,currentThread
from traceback import print_exc,print_stack
from types import StringType

from BitTornado.__init__ import resetPeerIDs
from BitTornado.bencode import bencode,bdecode
from BitTornado.RawServer import autodetect_socket_style

from Tribler.API.simpledefs import *
from Tribler.API.defaults import *
from Tribler.API.exceptions import *
import Tribler.Overlay.permid
from Tribler.API.launchmanycore import TriblerLaunchMany
from Tribler.API.Impl.UserCallbackHandler import UserCallbackHandler
from Tribler.utilities import find_prog_in_PATH,validTorrentFile
from Tribler.API.Impl.miscutils import *

DEBUG = True

#
# Tribler API base classes
#
class Serializable:
    """
    Interface to signal that the object is pickleable.
    """
    def __init__(self):
        pass

class Copyable:
    """
    Interface for copying an instance (or rather signaling that it can be 
    copied) 
    """
    def copy(self):
        """
        Returns a copy of "self"
        in: self = an unbound instance of the class
        """
        raise NotYetImplementedException()

#
# The API classes
#
    
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
    
        # TEMP TODO: Delegate to Jelle?
        self.sessconfig['overlay'] = 0
        self.sessconfig['dialback'] = 0
        

    def set_state_dir(self,statedir):
        self.sessconfig['state_dir'] = statedir
    
    def get_state_dir(self):
        return self.sessconfig['state_dir']
    
    def set_permid(self,keypairfilename): # TODO: permid right name?
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

    def set_overlay(self,value):
        """ Enable overlay swarm to enable Tribler's special features 
        (default = True) """
        self.sessconfig['overlay'] = value

    def get_overlay(self):
        return self.sessconfig['overlay']

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


    #
    # Download helper / cooperative download
    #
    def set_download_help(self,value):
        """ accept download help request (default = True) """
        self.sessconfig['download_help'] = value

    def get_download_help(self):
        return self.sessconfig['download_help']


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
    # Tribler dialback mechanism is used to test whether a Session is
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
    def set_socnet(self,value):
        """ enable social networking (default = True) """
        self.sessconfig['socnet'] = value

    def get_socnet(self):
        return self.sessconfig['socnet']

    def set_nickname(self,value):  # TODO: put in PeerDBHandler? Add method for setting own pic
        """ the nickname you want to show to others """
        self.sessconfig['nickname'] = value

    def get_nickname(self):
        return self.sessconfig['nickname']

    #
    # Tribler remote query: ask other peers when looking for a torrent file 
    # or peer
    #
    def set_rquery(self,value):
        """ enable remote query (default = True) """
        self.sessconfig['rquery'] = value

    def get_rquery(self):
        return self.sessconfig['rquery']


    #
    # For Tribler superpeer servers
    #
    def set_superpeer(self,value):
        """ run in super peer mode (0 = disabled) """
        self.sessconfig['superpeer'] = value

    def get_superpeer(self):
        return self.sessconfig['superpeer']

    def set_overlay_log(self,value):
        """ log on super peer mode ('' = disabled) """
        self.sessconfig['overlay_log'] = value

    def get_overlay_log(self):
        return self.sessconfig['overlay_log']

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


# Import here to prevent circular dependencies problem
from Tribler.API.Impl.SessionRuntimeConfig import SessionRuntimeConfig

class Session(SessionRuntimeConfig):
    """
    
    A Session implements the SessionConfigInterface which can be used to
    change session parameters are runtime (for selected parameters).
    
    cf. libtorrent session
    """
    __single = None

    
    def __init__(self,scfg=None):
        """
        A Session object is created which is configured following a copy of the
        SessionStartupConfig scfg. (copy constructor used internally)
        
        in: scfg = SessionStartupConfig object or None, in which case we
        look for a saved session in the default location (state dir). If
        we can't find it, we create a new SessionStartupConfig() object to 
        serve as startup config. Next, the config is saved in the directory
        indicated by its 'state_dir' attribute.
        
        In the current implementation only a single session instance can exist
        at a time in a process.
        """
        if Session.__single:
            raise RuntimeError, "Session is singleton"
        Session.__single = self

        
        self.sesslock = RLock()

        # Determine startup config to use
        if scfg is not None: # overrides any saved config
            # Work from copy
            self.sessconfig = copy.copy(scfg.sessconfig)
            state_dir = self.sessconfig['state_dir']
        else:
            state_dir = None

        # Create dir for session state
        if state_dir is None:
            state_dir = Session.get_default_state_dir()
            
        if not os.path.isdir(state_dir):
            os.mkdir(state_dir)

        if scfg is None: # If no override
            try:
                # Then try to read from default location
                scfg = self.load_pstate_sessconfig(state_dir)
            except:
                # If that fails, create a fresh config with factory defaults
                print_exc()
                scfg = SessionStartupConfig()
                scfg.sessconfig['state_dir'] = state_dir
            self.sessconfig = scfg.sessconfig

        # PERHAPS: load default TorrentDef and DownloadStartupConfig from state dir
        # Let user handle that, he's got default_state_dir, etc.

        # Core init
        resetPeerIDs()
        Tribler.Overlay.permid.init()


        #
        # Set params that depend on state_dir
        #
        # 1. keypair
        #
        if self.sessconfig['eckeypairfilename'] is None:
            self.keypair = Tribler.Overlay.permid.generate_keypair()
            pairfilename = os.path.join(self.sessconfig['state_dir'],'ec.pem')
            pubfilename = os.path.join(self.sessconfig['state_dir'],'ecpub.pem')
            self.sessconfig['eckeypairfilename'] = pairfilename
            Tribler.Overlay.permid.save_keypair(self.keypair,pairfilename)
            Tribler.Overlay.permid.save_pub_key(self.keypair,pubfilename)
        else:
            # May throw exceptions
            self.keypair = Tribler.Overlay.permid.read_keypair(self.sessconfig['eckeypairfilename'])
        
        # 2. Downloads persistent state dir
        dlpstatedir = os.path.join(self.sessconfig['state_dir'],STATEDIR_DLPSTATE_DIR)
        if not os.path.isdir(dlpstatedir):
            os.mkdir(dlpstatedir)
        
        # 3. tracker
        trackerdir = os.path.join(self.sessconfig['state_dir'],STATEDIR_ITRACKER_DIR)
        if not os.path.isdir(trackerdir):
            os.mkdir(trackerdir)

        if self.sessconfig['tracker_dfile'] is None:
            self.sessconfig['tracker_dfile'] = os.path.join(trackerdir,'tracker.db')    

        if self.sessconfig['tracker_allowed_dir'] is None:
            self.sessconfig['tracker_allowed_dir'] = trackerdir    
        
        if self.sessconfig['tracker_logfile'] is None:
            if sys.platform == "win32":
                # Not "Nul:" but "nul" is /dev/null on Win32
                sink = 'nul'
            else:
                sink = '/dev/null'
            self.sessconfig['tracker_logfile'] = sink


        # Checkpoint startup config
        sscfg = self.get_current_startup_config_copy()
        self.save_pstate_sessconfig(sscfg)


        # Create handler for calling back the user via separate threads
        self.uch = UserCallbackHandler(self.sesslock,self.sessconfig)

        # Create engine with network thread
        self.lm = TriblerLaunchMany(self,self.sesslock)
        self.lm.start()


    #
    # Class methods
    #
    def get_instance(*args, **kw):
        """ Returns the Session singleton if it exists or otherwise
            creates it first, in which case you need to pass the constructor 
            params """
        if Session.__single is None:
            Session(*args, **kw)
        return Session.__single
    get_instance = staticmethod(get_instance)

    def get_default_state_dir():
        """ Returns the factory default directory for storing session state """
        homedirpostfix = '.Tribler'
        if sys.platform == 'win32':
            homedirvar = '${APPDATA}'
        elif sys.platform == 'darwin':
            homedirvar = '${HOME}'
            # JD wants $HOME/Libray/Preferences/something TODO
            #homedirpostfix = os.path.join('Library)
        else:
            homedirvar = '${HOME}'  
        homedir = os.path.expandvars(homedirvar)
        triblerdir = os.path.join(homedir,homedirpostfix)
        return triblerdir
    get_default_state_dir = staticmethod(get_default_state_dir)


    #
    # Public methods
    #
    def load_checkpoint(self):
        """ Restart Downloads from checkpoint, if any.
        
        This must be manageable by the API user for e.g. a video player
        that wants to start the torrent the user clicked on first, and
        only then restart any sleeping torrents (e.g. seeding) """
        self.lm.load_checkpoint()
    
    
    def start_download(self,tdef,dcfg=None):
        """ 
        Creates a Download object and adds it to the session. The passed 
        TorrentDef and DownloadStartupConfig are copied into the new Download 
        object and the copies become bound. If the tracker is not set in tdef, 
        it is set to the internal tracker (which must have been enabled in the 
        session config). The Download is then started and checkpointed.

        If a checkpointed version of the Download is found, that is restarted
        overriding the saved DownloadStartupConfig is "dcfg" is not None.
        
        in:
        tdef = TorrentDef
        drcfg = DownloadStartupConfig or None, in which case 
        DownloadStartupConfig.get_copy_of_default() is called and the result becomes 
        the config of this Download.
        returns: a Download object
        """
        # locking by lm
        return self.lm.add(tdef,dcfg)

    def resume_download_from_file(self,filename):
        """
        Recreates Download from resume file
        
        returns: a Download object
        
        Note: this cannot be made into a method of Download, as the Download 
        needs to be bound to a session, it cannot exist independently.
        """
        raise NotYetImplementedException()

    def get_downloads(self):
        """
        returns: a copy of the list of Downloads
        """
        # locking by lm
        return self.lm.get_downloads()
    
    
    def remove_download(self,d,removecontent=False):  
        """
        Stops the download and removes it from the session.
        """
        # locking by lm
        self.lm.remove(d,removecontent=removecontent)


    def set_download_states_callback(self,usercallback,getpeerlist=False):
        """
        See Download.set_state_callback. Calls usercallback(dslist) which should
        return > 0.0 to reschedule.
        """
        self.lm.set_download_states_callback(usercallback,getpeerlist)


    def get_internal_tracker_url(self):
        """ Called by any thread """
        ip = self.lm.get_ext_ip() #already thread safe
        port = self.get_listen_port() # already thread safe
        url = 'http://'+ip+':'+str(port)+'/announce/'
        return url

    def checkpoint(self):
        """ Saves the internal session state to the Session's state dir.
        
        Called by any thread """
        self.checkpoint_shutdown(stop=False)
    
    def shutdown(self):
        """ Checkpoints the session and closes it, stopping the download engine. 
        
        Called by any thread """
        self.checkpoint_shutdown(stop=True)

    #
    # Internal persistence methods
    #
    def checkpoint_shutdown(self,stop):
        """ Called by any thread """
        # No locking required
        sscfg = self.get_current_startup_config_copy()
        # Reset unpicklable params
        sscfg.set_permid(None)
        try:
            self.save_pstate_sessconfig(sscfg)
        except Exception,e:
            self.lm.rawserver_nonfatalerrorfunc(e)

        # Checkpoint all Downloads
        print >>sys.stderr,"Session: checkpoint_shutdown"
        self.lm.checkpoint(stop=stop)

    def save_pstate_sessconfig(self,sscfg):
        """ Called by any thread """
        cfgfilename = os.path.join(sscfg.get_state_dir(),STATEDIR_SESSCONFIG)
        f = open(cfgfilename,"wb")
        pickle.dump(sscfg,f)
        f.close()


    def load_pstate_sessconfig(self,state_dir):
        cfgfilename = os.path.join(state_dir,STATEDIR_SESSCONFIG)
        f = open(cfgfilename,"rb")
        sscfg = pickle.load(f)
        f.close()
        return sscfg
        

    def get_downloads_pstate_dir(self):
        """ Returns the directory in which to checkpoint the Downloads in this
        Session.
         
        Called by network thread """
        self.sesslock.acquire()
        try:
            return os.path.join(self.sessconfig['state_dir'],STATEDIR_DLPSTATE_DIR)
        finally:
            self.sesslock.release()
        
        
    def get_current_startup_config_copy(self):
        """ Returns a SessionStartupConfig that is a copy of the current runtime 
        SessionConfig.
         
        Called by any thread """
        self.sesslock.acquire()
        try:
            sessconfig = copy.copy(self.sessconfig)
            return SessionStartupConfig(sessconfig=sessconfig)
        finally:
            self.sesslock.release()
        
        

#class TorrentDef(DictMixin,Serializable):
class TorrentDef(Serializable,Copyable):
    """
    Definition of a torrent, i.e. all params required for a torrent file,
    plus optional params such as thumbnail, playtime, etc.

    cf. libtorrent torrent_info
    """
    def __init__(self,input=None,metainfo=None,infohash=None):
        """ Normal constructor for TorrentDef (copy constructor used internally) """
        
        self.readonly = False
        if input is not None: # copy constructor
            self.input = input
            # self.metainfo_valid set in copy() 
            self.metainfo = metainfo
            self.infohash = infohash
            return
        
        self.input = {} # fields added by user, waiting to be turned into torrent file
        self.input['files'] = []
        self.metainfo_valid = False
        self.metainfo = None # copy of loaded or last saved torrent dict
        self.infohash = None # only valid if metainfo_valid
        
        # Define the built-in default here
        self.input.update(tdefdefaults)
        
        # We cannot set a built-in default for a tracker here, as it depends on
        # a Session. Alternatively, the tracker will be set to the internal
        # tracker by default when Session::start_download() is called, if the
        # 'announce' field is the empty string.

    #
    # Class methods for creating a TorrentDef from a .torrent file
    #
    def load(filename):
        """
        Load a BT .torrent or Tribler .tribe file from disk and convert
        it into a TorrentDef
        
        in: filename = Fully qualified Unicode filename
        returns: a TorrentDef object
        
        throws: IOExceptions,ValueError
        """
        # Class method, no locking required
        f = open(filename,"rb")
        return TorrentDef._read(f)
    load = staticmethod(load)
        
    def _read(stream):
        """ Internal class method that reads a torrent file from stream,
        checks it for correctness and sets self.input and self.metainfo
        accordingly """
        bdata = stream.read()
        stream.close()
        data = bdecode(bdata)
        return TorrentDef._create(data)
    _read = staticmethod(_read)
        
    def _create(metainfo): # TODO: replace with constructor
        # raises ValueErrors if not good
        validTorrentFile(metainfo) 
        
        t = TorrentDef()
        t.metainfo = metainfo
        t.metainfo_valid = True
        t.infohash = sha.sha(bencode(metainfo['info'])).digest()
        
        # copy stuff into self.input 
        t.input = {}
        t.input['announce'] = t.metainfo['announce']
        t.input['name'] = t.metainfo['info']['name']
        
        # TODO: copy rest of fields from metainfo to input
        return t
    _create = staticmethod(_create)

    def load_from_url(url):
        """
        Load a BT .torrent or Tribler .tribe file from the URL and convert
        it into a TorrentDef
        
        in: url = URL
        returns: a TorrentDef object
        
        throws: IOExceptions,ValueError
        """
        # Class method, no locking required
        f = urlTimeoutOpen(url)
        return TorrentDef._read(f)
    load_from_url = staticmethod(load_from_url)

    
    #
    # Convenience instance methods for publishing new content
    #
    def add_file(self,filename,playtime=None):
        """
        Add a file to this torrent definition. The core will not copy the file
        when starting the sharing, but seeds from the passed file directly.
        
        IMPLHINT: do something smart: people can just add files. When they finalize,
        we determine whether it is a single or multi-file torrent. In the latter
        case we determine the common directory name, which becomes the
        torrents's info['name'] field. Hmmm.... won't work if stuff comes
        from different disks, etc. TODO
        
        in:
        filename = Fully-qualified name of file on local filesystem, as Unicode
                   string
        playtime = (optional) String representing the duration of the multimedia
                   file when played, in [hh:]mm:ss format. 
        """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()
        
        s = os.stat(filename)
        d = {'fn':filename,'playtime':playtime,'length':s.st_size}
        self.input['files'].append(d)
        self.metainfo_valid = False

        # TODO: store playtime either as special field or reuse Azureus props

    def get_name(self):
        """ Returns info['name'] field """
        return self.input['name']

    def get_thumbnail(self):
        """
        returns: (MIME type,thumbnail data) if present or (None,None)
        """
        if thumb is None:
            return (None,None)
        else:
            thumb = self.input['thumb'] # buffer/string immutable
            return ('image/jpeg',thumb)
        
        
    def set_thumbnail(self,thumbfilename):
        """
        Reads image from file and turns it into a torrent thumbnail
        The file should contain an image in JPEG format, preferably 171x96
        
        in:
        thumbfilename = Fully qualified name of image file, as Unicode string.
        
        exceptions: ...Error
        """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()
        
        f = open(thumbfilename,"rb")
        data = f.read()
        f.close()
        self.input['thumb'] = data 
        self.metainfo_valid = False
        

    def set_tracker(self,url):
        """ Sets the tracker (i.e. the torrent file's 'announce' field).
        If the tracker is '' (the default) it will be set to the internal
        tracker when Session:start_download() is called. """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        self.input['announce'] = url 

    def get_tracker(self):
        return self.input['announce']

    def set_tracker_hierarchy(self,value):
        """ set hierarchy of trackers (announce-list) """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        self.input['announce-list'] = value

    def get_tracker_hierarchy(self):
        return self.input['announce-list']
        
    def set_comment(self,value):
        """ set comment field """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        self.input['comment'] = value

    def get_comment(self):
        return self.input['comment']

    def set_created_by(self,value):
        """ set 'created by' field """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        self.input['created by'] = value

    def get_created_by(self):
        return self.input['created by']

    def set_httpseeds(self,value):
        """ set list of HTTP seeds """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        self.input['httpseeds'] = value

    def get_httpseeds(self):
        return self.input['httpseeds']

    def set_piece_size(self,value):
        """ piece size as int (0 = automatic = default) """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        self.input['piece_size'] = value

    def get_piece_size(self):
        return self.input['piece_size']

    def set_add_md5hash(self,value):
        """ add end-to-end MD5 checksum """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        self.input['makehash_md5'] = value

    def get_add_md5hash(self):
        return self.input['makehash_md5']

    def set_add_crc32(self,value):
        """ add end-to-end CRC32 checksum """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        self.input['makehash_crc32'] = value

    def get_add_crc32(self):
        return self.input['makehash_crc32']

    def set_add_sha1hash(self,value):
        """ add end-to-end SHA1 checksum """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        self.input['makehash_sha1'] = value

    def get_add_sha1hash(self):
        return self.input['makehash_sha1']

    def set_create_merkle_torrent(self,value):
        """ create a Merkle torrent (.tribe, Tribler only) """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        self.input['createmerkletorrent'] = value

    def get_create_merkle_torrent(self):
        return self.input['createmerkletorrent']

    def set_add_signature(self,value):
        """ whether to add a signature to the torrent """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        self.input['createtorrentsig'] = value

    def get_add_signature(self):
        return self.input['createtorrentsig']

    def set_signature_keypair_filename(self,value):
        """ filename of keypair to be used for signature """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        self.input['torrentsigkeypairfilename'] = value

    def get_signature_keypair_filename(self):
        return self.input['torrentsigkeypairfilename']

        
    #
    def finalize(self):
        """ Create BT torrent file from input and calculate infohash 
        
        returns: (infohash,metainfo) tuple
        """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()
        
        if self.metainfo_valid:
            return (self.infohash,self.metainfo)
        else:
            """
            Read files to calc hashes
            """
            raise NotYetImplementedException()

    #
    # Operations on finalized TorrentDefs
    #
    def get_infohash(self):
        if self.metainfo_valid:
            return self.infohash
        else:
            raise NotYetImplementedException() # must save first

    def get_metainfo(self):
        if self.metainfo_valid:
            return self.metainfo
        else:
            raise NotYetImplementedException() # must save first


    def save(self,filename):
        """
        Finalizes the torrent def and writes a torrent file i.e., bencoded dict 
        following BT spec) to the specified filename.
        
        in:
        filename = Fully qualified Unicode filename
        
        throws: IOError
        """
        if not self.readonly:
            self.finalize()

        bdata = bencode(self.metainfo)
        f = open(filename,"wb")
        f.write(bdata)
        f.close()

    def get_bitrate(self,file=None):
        """ Returns the bitrate of the specified file in bytes/sec.
        If no file is specified, Tribler assumes this is a single-file torrent
        """ 
        if DEBUG:
            print >>sys.stderr,"TorrentDef: get_bitrate called",file
        
        if not self.metainfo_valid:
            raise NotYetImplementedException() # must save first

        info = self.metainfo['info']
        if file is None:
            bitrate = None
            try:
                playtime = None
                if info.has_key('playtime'):
                    print >>sys.stderr,"TorrentDef: get_bitrate: Bitrate in info field"
                    playtime = parse_playtime_to_secs(info['playtime'])
                elif 'playtime' in self.metainfo: # HACK: encode playtime in non-info part of existing torrent
                    print >>sys.stderr,"TorrentDef: get_bitrate: Bitrate in metainfo"
                    playtime = parse_playtime_to_secs(self.metainfo['playtime'])
                elif 'azureus_properties' in self.metainfo:
                    azprop = self.metainfo['azureus_properties']
                    if 'Content' in azprop:
                        content = self.metainfo['azureus_properties']['Content']
                        if 'Speed Bps' in content:
                            bitrate = float(content['Speed Bps'])
                            print >>sys.stderr,"TorrentDef: get_bitrate: Bitrate in Azureus metainfo",bitrate
                if playtime is not None:
                    bitrate = info['length']/playtime
            except:
                print_exc()
    
            return bitrate
    
        if file is not None and 'files' in info:
            for i in range(len(info['files'])):
                x = info['files'][i]
                    
                intorrentpath = ''
                for elem in x['path']:
                    intorrentpath = os.path.join(intorrentpath,elem)
                bitrate = None
                try:
                    playtime = None
                    if x.has_key('playtime'):
                        playtime = parse_playtime_to_secs(x['playtime'])
                    elif 'playtime' in self.metainfo: # HACK: encode playtime in non-info part of existing torrent
                        playtime = parse_playtime_to_secs(self.metainfo['playtime'])
                        
                    if playtime is not None:
                        bitrate = x['length']/playtime
                except:
                    print_exc()
                    
                if intorrentpath == file:
                    return bitrate
                
            raise ValueError("File not found in torrent")
        else:
            raise ValueError("File not found in single-file torrent")
    
    
    def get_video_files(self,videoexts=videoextdefaults):
        if not self.metainfo_valid:
            raise NotYetImplementedException() # must save first

        videofiles = []
        if 'files' in self.metainfo['info']:
            # Multi-file torrent
            files = self.metainfo['info']['files']
            for file in files:
                
                p = file['path']
                print >>sys.stderr,"TorrentDef: get_video_files: file is",p
                filename = ''
                for elem in p:
                    print >>sys.stderr,"TorrentDef: get_video_files: elem is",elem
                    filename = os.path.join(filename,elem)
                print >>sys.stderr,"TorrentDef: get_video_files: composed filename is",filename    
                (prefix,ext) = os.path.splitext(filename)
                if ext[0] == '.':
                    ext = ext[1:]
                print >>sys.stderr,"TorrentDef: get_video_files: ext",ext
                if ext in videoexts:
                    videofiles.append(filename)
        else:
            filename = self.metainfo['info']['name'] # don't think we need fixed name here
            (prefix,ext) = os.path.splitext(filename)
            if ext in videoexts:
                videofiles.append(filename)
        return videofiles

    
    #
    # Internal methods
    #
    def get_index_of_file_in_files(self,file):
        if not self.metainfo_valid:
            raise NotYetImplementedException() # must save first

        info = self.metainfo['info']

        if file is not None and 'files' in info:
            for i in range(len(info['files'])):
                x = info['files'][i]
                    
                intorrentpath = ''
                for elem in x['path']:
                    intorrentpath = os.path.join(intorrentpath,elem)
                    
                if intorrentpath == file:
                    return i
            return ValueError("File not found in torrent")
        else:
            raise ValueError("File not found in single-file torrent")


    #
    # DictMixin
    #

    #
    # Copyable interface
    # 
    def copy(self):
        input = copy.copy(self.input)
        metainfo = copy.copy(self.metainfo)
        infohash = self.infohash
        t = TorrentDef(input,metainfo,infohash)
        t.metainfo_valid = self.metainfo_valid
        return t



class DownloadConfigInterface:
    """
    (key,value) pair config of per-torrent runtime parameters,
    e.g. destdir, file-allocation policy, etc. Also options to advocate
    torrent, e.g. register in DHT, advertise via Buddycast.
    
    Use DownloadStartupConfig to manipulate download configs before download 
    startup time. This is just a parent class.
     
    cf. libtorrent torrent_handle
    """
    def __init__(self,dlconfig=None):
        
        if dlconfig is not None: # copy constructor
            self.dlconfig = dlconfig
            return
        
        self.dlconfig = {}
        
        # Define the built-in default here
        self.dlconfig.update(dldefaults)
       
        if sys.platform == 'win32':
            profiledir = os.path.expandvars('${USERPROFILE}')
            tempdir = os.path.join(profiledir,'Desktop','TriblerDownloads')
            self.dlconfig['saveas'] = tempdir 
        elif sys.platform == 'darwin':
            profiledir = os.path.expandvars('${HOME}')
            tempdir = os.path.join(profiledir,'Desktop','TriblerDownloads')
            self.dlconfig['saveas'] = tempdir
        else:
            self.dlconfig['saveas'] = '/tmp'


    def set_dest_dir(self,path):
        """ Sets the directory where to save this Download """
        self.dlconfig['saveas'] = path

    def set_video_on_demand(self,usercallback):
        """ Download the torrent in Video-On-Demand mode. usercallback is a 
        function that accepts a file-like object as its first argument. 
        To fetch a specific file from a multi-file torrent, use the
        set_selected_files() method. """
        self.dlconfig['mode'] = DLMODE_VOD
        self.dlconfig['vod_usercallback'] = usercallback


    def get_mode(self):
        return self.dlconfig['mode']

    def get_vod_callback(self):
        return self.dlconfig['vod_usercallback']

    def set_selected_files(self,files):
        """ Select which files to download. "files" can be a single filename
        or a list of filenames (e.g. ['harry.avi','sjaak.avi']). The filenames
        must be in print format. TODO explain + add methods """
        # TODO: can't check if files exists, don't have tdef here.... bugger
        if type(files) == StringType: # convenience
            files = [files] 
            
        if self.dlconfig['mode'] == DLMODE_VOD and len(files) > 1:
            raise ValueError("In Video-On-Demand mode only 1 file can be selected for download")
        self.dlconfig['selected_files'] = files
        
        print >>sys.stderr,"DownloadStartupConfig: set_selected_files",files

    def get_selected_files(self):
        return self.dlconfig['selected_files']

    #
    # Common download performance parameters
    #
    def set_max_speed(self,direct,speed):
        """ Sets the maximum upload or download speed for this Download in KB/s """
        if direct == UPLOAD:
            self.dlconfig['max_upload_rate'] = speed
        else:
            self.dlconfig['max_download_rate'] = speed

    def get_max_speed(self,direct):
        if direct == UPLOAD:
            return self.dlconfig['max_upload_rate']
        else:
            return self.dlconfig['max_download_rate']

    def set_max_conns_to_initiate(self,nconns):
        """ Sets the maximum number of connections to initiate for this 
        Download """
        self.dlconfig['max_initiate'] = nconns

    def get_max_conns_to_initiate(self):
        return self.dlconfig['max_initiate']

    def set_max_conns(self,nconns):
        """ Sets the maximum number of connections to connections for this 
        Download """
        self.dlconfig['max_connections'] = nconns

    def get_max_conns(self):
        return self.dlconfig['max_connections']

    #
    # Advanced download parameters
    # 
    def set_max_uploads(self,value):
        """ the maximum number of uploads to allow at once. """
        self.dlconfig['max_uploads'] = value

    def get_max_uploads(self):
        return self.dlconfig['max_uploads']

    def set_keepalive_interval(self,value):
        """ number of seconds to pause between sending keepalives """
        self.dlconfig['keepalive_interval'] = value

    def get_keepalive_interval(self):
        return self.dlconfig['keepalive_interval']

    def set_download_slice_size(self,value):
        """ How many bytes to query for per request. """
        self.dlconfig['download_slice_size'] = value

    def get_download_slice_size(self):
        return self.dlconfig['download_slice_size']

    def set_upload_unit_size(self,value):
        """ when limiting upload rate, how many bytes to send at a time """
        self.dlconfig['upload_unit_size'] = value

    def get_upload_unit_size(self):
        return self.dlconfig['upload_unit_size']

    def set_request_backlog(self,value):
        """ maximum number of requests to keep in a single pipe at once. """
        self.dlconfig['request_backlog'] = value

    def get_request_backlog(self):
        return self.dlconfig['request_backlog']

    def set_max_message_length(self,value):
        """ maximum length prefix encoding you'll accept over the wire - larger values get the connection dropped. """
        self.dlconfig['max_message_length'] = value

    def get_max_message_length(self):
        return self.dlconfig['max_message_length']

    def set_max_slice_length(self,value):
        """ maximum length slice to send to peers, larger requests are ignored """
        self.dlconfig['max_slice_length'] = value

    def get_max_slice_length(self):
        return self.dlconfig['max_slice_length']

    def set_max_rate_period(self,value):
        """ maximum amount of time to guess the current rate estimate represents """
        self.dlconfig['max_rate_period'] = value

    def get_max_rate_period(self):
        return self.dlconfig['max_rate_period']

    def set_upload_rate_fudge(self,value):
        """ time equivalent of writing to kernel-level TCP buffer, for rate adjustment """
        self.dlconfig['upload_rate_fudge'] = value

    def get_upload_rate_fudge(self):
        return self.dlconfig['upload_rate_fudge']

    def set_tcp_ack_fudge(self,value):
        """ how much TCP ACK download overhead to add to upload rate calculations (0 = disabled) """
        self.dlconfig['tcp_ack_fudge'] = value

    def get_tcp_ack_fudge(self):
        return self.dlconfig['tcp_ack_fudge']

    def set_rerequest_interval(self,value):
        """ time to wait between requesting more peers """
        self.dlconfig['rerequest_interval'] = value

    def get_rerequest_interval(self):
        return self.dlconfig['rerequest_interval']

    def set_min_peers(self,value):
        """ minimum number of peers to not do rerequesting """
        self.dlconfig['min_peers'] = value

    def get_min_peers(self):
        return self.dlconfig['min_peers']

    def set_http_timeout(self,value):
        """ number of seconds to wait before assuming that an http connection has timed out """
        self.dlconfig['http_timeout'] = value

    def get_http_timeout(self):
        return self.dlconfig['http_timeout']

    def set_check_hashes(self,value):
        """ whether to check hashes on disk """
        self.dlconfig['check_hashes'] = value

    def get_check_hashes(self):
        return self.dlconfig['check_hashes']

    def set_alloc_type(self,value):
        """ allocation type (may be normal, background, pre-allocate or sparse) """
        self.dlconfig['alloc_type'] = value

    def get_alloc_type(self):
        return self.dlconfig['alloc_type']

    def set_alloc_rate(self,value):
        """ rate (in MiB/s) to allocate space at using background allocation """
        self.dlconfig['alloc_rate'] = value

    def get_alloc_rate(self):
        return self.dlconfig['alloc_rate']

    def set_buffer_reads(self,value):
        """ whether to buffer disk reads """
        self.dlconfig['buffer_reads'] = value

    def get_buffer_reads(self):
        return self.dlconfig['buffer_reads']

    def set_write_buffer_size(self,value):
        """ the maximum amount of space to use for buffering disk writes (in megabytes, 0 = disabled) """
        self.dlconfig['write_buffer_size'] = value

    def get_write_buffer_size(self):
        return self.dlconfig['write_buffer_size']

    def set_breakup_seed_bitfield(self,value):
        """ sends an incomplete bitfield and then fills with have messages, in order to get around stupid ISP manipulation """
        self.dlconfig['breakup_seed_bitfield'] = value

    def get_breakup_seed_bitfield(self):
        return self.dlconfig['breakup_seed_bitfield']

    def set_snub_time(self,value):
        """ seconds to wait for data to come in over a connection before assuming it's semi-permanently choked """
        self.dlconfig['snub_time'] = value

    def get_snub_time(self):
        return self.dlconfig['snub_time']

    def set_rarest_first_cutoff(self,value):
        """ number of downloads at which to switch from random to rarest first """
        self.dlconfig['rarest_first_cutoff'] = value

    def get_rarest_first_cutoff(self):
        return self.dlconfig['rarest_first_cutoff']

    def set_rarest_first_priority_cutoff(self,value):
        """ the number of peers which need to have a piece before other partials take priority over rarest first """
        self.dlconfig['rarest_first_priority_cutoff'] = value

    def get_rarest_first_priority_cutoff(self):
        return self.dlconfig['rarest_first_priority_cutoff']

    def set_min_uploads(self,value):
        """ the number of uploads to fill out to with extra optimistic unchokes """
        self.dlconfig['min_uploads'] = value

    def get_min_uploads(self):
        return self.dlconfig['min_uploads']

    def set_max_files_open(self,value):
        """ the maximum number of files to keep open at a time, 0 means no limit """
        self.dlconfig['max_files_open'] = value

    def get_max_files_open(self):
        return self.dlconfig['max_files_open']

    def set_round_robin_period(self,value):
        """ the number of seconds between the client's switching upload targets """
        self.dlconfig['round_robin_period'] = value

    def get_round_robin_period(self):
        return self.dlconfig['round_robin_period']

    def set_super_seeder(self,value):
        """ whether to use special upload-efficiency-maximizing routines (only for dedicated seeds) """
        self.dlconfig['super_seeder'] = value

    def get_super_seeder(self):
        return self.dlconfig['super_seeder']

    def set_security(self,value):
        """ whether to enable extra security features intended to prevent abuse """
        self.dlconfig['security'] = value

    def get_security(self):
        return self.dlconfig['security']

    def set_max_connections(self,value):
        """ the absolute maximum number of peers to connect with (0 = no limit) """
        self.dlconfig['max_connections'] = value

    def get_max_connections(self):
        return self.dlconfig['max_connections']

    def set_auto_kick(self,value):
        """ whether to allow the client to automatically kick/ban peers that send bad data """
        self.dlconfig['auto_kick'] = value

    def get_auto_kick(self):
        return self.dlconfig['auto_kick']

    def set_double_check(self,value):
        """ whether to double-check data being written to the disk for errors (may increase CPU load) """
        self.dlconfig['double_check'] = value

    def get_double_check(self):
        return self.dlconfig['double_check']

    def set_triple_check(self,value):
        """ whether to thoroughly check data being written to the disk (may slow disk access) """
        self.dlconfig['triple_check'] = value

    def get_triple_check(self):
        return self.dlconfig['triple_check']

    def set_lock_files(self,value):
        """ whether to lock files the client is working with """
        self.dlconfig['lock_files'] = value

    def get_lock_files(self):
        return self.dlconfig['lock_files']

    def set_lock_while_reading(self,value):
        """ whether to lock access to files being read """
        self.dlconfig['lock_while_reading'] = value

    def get_lock_while_reading(self):
        return self.dlconfig['lock_while_reading']

    def set_auto_flush(self,value):
        """ minutes between automatic flushes to disk (0 = disabled) """
        self.dlconfig['auto_flush'] = value

    def get_auto_flush(self):
        return self.dlconfig['auto_flush']

    def set_exclude_ips(self,value):
        """ list of IP addresse to be excluded; comma separated """
        self.dlconfig['exclude_ips'] = value

    def get_exclude_ips(self):
        return self.dlconfig['exclude_ips']

    def set_ut_pex_max_addrs_from_peer(self,value):
        """ maximum number of addresses to accept from peer (0 = disabled PEX) """
        self.dlconfig['ut_pex_max_addrs_from_peer'] = value

    def get_ut_pex_max_addrs_from_peer(self):
        return self.dlconfig['ut_pex_max_addrs_from_peer']



    
class DownloadStartupConfig(DownloadConfigInterface,Serializable,Copyable):
    """
    (key,value) pair config of per-torrent runtime parameters,
    e.g. destdir, file-allocation policy, etc. Also options to advocate
    torrent, e.g. register in DHT, advertise via Buddycast.
    
    cf. libtorrent torrent_handle
    """
    def __init__(self,dlconfig=None):
        """ Normal constructor for DownloadStartupConfig (copy constructor 
        used internally) """
        DownloadConfigInterface.__init__(self,dlconfig)

    #
    # Copyable interface
    # 
    def copy(self):
        config = copy.copy(self.dlconfig)
        return DownloadStartupConfig(config)



class DownloadState(Serializable):
    """
    Contains a snapshot of the state of the Download at a specific
    point in time. Using a snapshot instead of providing live data and 
    protecting access via locking should be faster.
    
    cf. libtorrent torrent_status
    """
    def __init__(self,download,status,error,progress,stats=None,filepieceranges=None,logmsgs=None):
        self.download = download
        self.filepieceranges = filepieceranges # NEED CONC CONTROL IF selected_files RUNTIME SETABLE
        self.logmsgs = logmsgs
        if stats is None:
            self.error = error # readonly access
            self.progress = progress
            if self.error is not None:
                self.status = DLSTATUS_STOPPED_ON_ERROR
            else:
                self.status = status
            self.stats = None
        elif error is not None:
            self.error = error # readonly access
            self.progress = 0.0 # really want old progress
            self.status = DLSTATUS_STOPPED_ON_ERROR
            self.stats = None
        elif status is not None:
            # For HASHCHECKING and WAITING4HASHCHECK
            self.error = error
            self.status = status
            if self.status == DLSTATUS_WAITING4HASHCHECK:
                self.progress = 0.0
            else:
                self.progress = stats['frac']
            self.stats = None
        else:
            # Copy info from stats
            self.error = None
            self.progress = stats['frac']
            if stats['frac'] == 1.0:
                self.status = DLSTATUS_SEEDING
            else:
                self.status = DLSTATUS_DOWNLOADING
            #print >>sys.stderr,"STATS IS",stats
            
            # Safe to store the stats dict. The stats dict is created per
            # invocation of the BT1Download returned statsfunc and contains no
            # pointers.
            #
            self.stats = stats
            
            # for pieces complete
            statsobj = self.stats['stats']
            if self.filepieceranges is None:
                self.haveslice = statsobj.have # is copy of network engine list
            else:
                # Show only pieces complete for the selected ranges of files
                totalpieces =0
                for t,tl,f in self.filepieceranges:
                    diff = tl-t
                    totalpieces += diff
                    
                print >>sys.stderr,"DownloadState: get_pieces_complete",totalpieces
                
                haveslice = [False] * totalpieces
                haveall = True
                index = 0
                for t,tl,f in self.filepieceranges:
                    for piece in range(t,tl):
                        haveslice[index] = statsobj.have[piece]
                        if haveall and haveslice[index] == False:
                            haveall = False
                        index += 1 
                self.haveslice = haveslice
                if haveall:
                    # we have all pieces of the selected files
                    self.status = DLSTATUS_SEEDING
                    self.progress = 1.0

    
    def get_download(self):
        """ returns the Download object of which this is the state """
        return self.download
    
    def get_progress(self):
        """
        returns: percentage of torrent downloaded, as float
        """
        return self.progress
        
    def get_status(self):
        """
        returns: status of the torrent, e.g. DLSTATUS_* 
        """
        return self.status

    def get_error(self):
        """ 
        returns: the Exception that caused the download to be moved to 
        DLSTATUS_STOPPED_ON_ERROR status.
        """
        return self.error

    #
    # Details
    # 
    def get_current_speed(self,direct):
        """
        returns: current up or download speed in KB/s, as float
        """
        if self.stats is None:
            return 0.0
        if direct == UPLOAD:
            return self.stats['up']/1024.0
        else:
            return self.stats['down']/1024.0

    def has_active_connections(self):
        """ 
        returns: whether the download has active connections
        """
        if self.stats is None:
            return False

        # Determine if we need statsobj to be requested, same as for spew
        statsobj = self.stats['stats']
        return statsobj.numSeeds+statsobj.numPeers > 0
        
    def get_pieces_complete(self):
        # Hmm... we currently have the complete overview in statsobj.have,
        # but we want the overview for selected files.
        if self.stats is None:
            return []
        else:
            return self.haveslice

    def get_vod_prebuffering_progress(self):
        if self.stats is None:
            return 0.0
        else:
            return self.stats['vod_prebuf_frac']
    
    def get_vod_playable(self):
        if self.stats is None:
            return False
        else:
            return self.stats['vod_playable']

    def get_vod_playable_after(self):
        if self.stats is None:
            return float(2 ** 31)
        else:
            return self.stats['vod_playable_after']


    def get_log_messages(self):
        """ Returns the last 10 logged non-fatal error messages as a list of 
        (time,msg) tuples """
        if self.logmsgs is None:
            return []
        else:
            return self.logmsgs
    


        
        
# Import here to prevent circular dependencies problem
from Tribler.API.Impl.DownloadRuntimeConfig import DownloadRuntimeConfig
from Tribler.API.Impl.DownloadImpl import DownloadImpl

        
class Download(DownloadRuntimeConfig,DownloadImpl):
    """
    Representation of a running BT download/upload
    
    A Download implements the DownloadConfigInterface which can be used to
    change download parameters are runtime (for selected parameters).
    
    cf. libtorrent torrent_handle
    """
    
    #
    # Internal methods
    #
    def __init__(self,session,tdef):
        self.dllock = RLock()
        # just enough so error saving and get_state() works
        self.error = None
        self.sd = None # hack
        # To be able to return the progress of a stopped torrent, how far it got.
        self.progressbeforestop = 0.0
        self.filepieceranges = []

        # Copy tdef, so we get an infohash
        self.session = session
        self.tdef = tdef.copy()
        # Need to do this before finalize
        tracker = self.tdef.get_tracker()
        itrackerurl = self.session.get_internal_tracker_url()
        if tracker == '':
            self.tdef.set_tracker(itrackerurl)
        self.tdef.finalize()
        self.tdef.readonly = True

    #
    # Public methods
    #
    def get_def(self):
        """
        Returns the read-only TorrentDef
        """
        # No lock because attrib immutable and return value protected
        return self.tdef

    
    def set_state_callback(self,usercallback,getpeerlist=False):
        """ 
        Set a callback for retrieving the state of the download. This callback
        will be called immediately with a DownloadState object as first parameter.
        The callback method must return a tuple (when,getpeerlist) where "when" 
        indicates whether the callback should be called again and represents a
        number of seconds from now. If "when" <= 0.0 the callback will not be
        called again. "getpeerlist" is a boolean that indicates whether the 
        DownloadState passed to the callback on the next invocation should
        contain info about the set of current peers.
                
        in: 
        callback = function that accepts DownloadState as parameter and returns 
        a (float,boolean) tuple.
        """
        self.dllock.acquire()
        try:
            network_get_state_lambda = lambda:self.network_get_state(usercallback,getpeerlist)
            # First time on general rawserver
            self.session.lm.rawserver.add_task(network_get_state_lambda,0.0)
        finally:
            self.dllock.release()
        

    def stop(self):
        """ Called by any thread """
        self.stop_remove(removestate=False,removecontent=False)
        
    def restart(self):
        """ Called by any thread """
        # Must schedule the hash check via lm. In some cases we have batch stops
        # and restarts, e.g. we have stop all-but-one & restart-all for VOD)
        self.dllock.acquire()
        try:
            if self.sd is None:
                self.error = None # assume fatal error is reproducible
                # TODO: if seeding don't rehash check
                self.create_engine_wrapper(self.session.lm.network_engine_wrapper_created_callback,pstate=None)
            # No exception if already started, for convenience
        finally:
            self.dllock.release()

    #
    # Config parameters that only exists at runtime 
    #
    def set_max_desired_speed(self,direct,speed):
        """ Sets the maximum desired upload/download speed for this Download in KB/s """
        
        print >>sys.stderr,"Download: set_max_desired_speed",direct,speed
        #if speed < 10:
        #    print_stack()
        
        self.dllock.acquire()
        if direct == UPLOAD:
            self.dlruntimeconfig['max_desired_upload_rate'] = speed
        else:
            self.dlruntimeconfig['max_desired_download_rate'] = speed
        self.dllock.release()

    def get_max_desired_speed(self,direct):
        """ Returns the maximum desired upload/download speed for this Download in KB/s """
        self.dllock.acquire()
        try:
            if direct == UPLOAD:
                print >>sys.stderr,"Download: get_max_desired_speed: get_max_desired",self.dlruntimeconfig['max_desired_upload_rate']
                return self.dlruntimeconfig['max_desired_upload_rate']
            else:
                return self.dlruntimeconfig['max_desired_download_rate']
        finally:
            self.dllock.release()



    

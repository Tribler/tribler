"""
triblerAPI v0.0.1rc1
oct 9, 2007 

Using Python style guide

Simplest download session
=========================
    s = Session()
    tdef = TorrentDef.load('/tmp/bla.torrent')
    d = s.start_download(tdef)
    while True:
        print d.get_state().get_progress()
        sleep(5)

Simpler download session
========================
    s = Session()
    tdef = TorrentDef.load('/tmp/bla.torrent')
    dcfg = DownloadConfig.get_copy_of_default()
    dcfg.set_dest_dir('/tmp')
    d = s.start_download(tdef,dcfg)


Simple VOD download session
===========================
    s = Session()
    tdef = TorrentDef.load('/tmp/bla.torrent')
    dcfg = DownloadConfig.get_copy_of_default()
    dcfg.set_mode('VOD',vod_ready_callback)
    d = s.start_download(tdef,dcfg)
    
def vod_ready_callback(stream):
    # Called by new thread 
    while True:
        data = stream.read()
        if len(data) == 0:
            break
        outstream.write(data)
        
ALTERNATIVE: the user passes a block_ready_callback, which we call every time
a new block comes in. This may be less desirable, as the user then has to
concurrency control to balance the writer (the core) and the reader (e.g. HTTP
socket). 

In this vod_ready_callback scenario, we do the producer/consumer problem
inside the stream object, blocking the new thread as desired. Note that it must 
be a new thread and not the network thread that calls vod_ready_callback().        
Another advantage of vod_ready is that users can pass the stream object to an
HTTP server which can then record a (path,stream) tuple, and start reading from
the given stream when the path is requested via GET /path HTTP/1.1)
We throw IOExceptions when the VOD download is stopped / removed.
        

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

TODO: Define whether changes to runtime configs is synchronous, i.e., does
dcfg.set_max_upload(100) sets the upload limit before returning, or 
asynchronous.
 

ALTERNATIVE:
Use copy in/out semantics for TorrentDef and DownloadConfig. A disadvantage of 
copy in/out is that people may forget to call the copy in method.


Persistence Support
===================
We use the Python pickling mechanism to make objects persistent. We add a
version number to the state before it is saved. To indicate serializability
classes inherit from the Serializable interface. 

ALTERNATIVE: 
We provide save/load methods. An ISSUE then is do we use filenames as args or 
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
ISSUE: Theoretically, Session can be a real class with multiple instances. For
implementation purposes making it a Singleton is easier, as a lot of our 
internal stuff are currently singletons (e.g. databases and *MsgHandler, etc.)


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

        
Alternative names for "Download"
================================
Exchange, i.e. start_exchange()
Replica, i.e. create_replica(), remove_replica() which abstractly is exactly 
what BT does. When you start a seed, you basically create a replica. When you 
start a download you want to create a copy on your local system, i.e. create a
replica there.
"""
import sys
import os
import time
import copy
import sha
import socket
from UserDict import DictMixin
from threading import RLock,Event,Thread
from traceback import print_exc,print_stack

from BitTornado.__init__ import resetPeerIDs,createPeerID
from BitTornado.RawServer import autodetect_socket_style
from BitTornado.bencode import bencode,bdecode
from BitTornado.download_bt1 import BT1Download
import Tribler.Overlay.permid
from Tribler.NATFirewall.guessip import get_my_wan_ip
from Tribler.utilities import find_prog_in_PATH


from BitTornado.RawServer import RawServer
from BitTornado.ServerPortHandler import MultiHandler
from BitTornado.RateLimiter import RateLimiter
from BitTornado.natpunch import UPnPWrapper, UPnPError
from BitTornado.BT1.track import Tracker
from BitTornado.HTTPHandler import HTTPHandler,DummyHTTPHandler

from Tribler.Overlay.SecureOverlay import SecureOverlay
from Tribler.Overlay.OverlayApps import OverlayApps
from Tribler.NATFirewall.DialbackMsgHandler import DialbackMsgHandler

# TEMP
from Tribler.Dialogs.activities import *


DEBUG = True


DEFAULTPORT=7762  # Arno: see Utility/configreader.py and Utility/utility.py

sessdefaults = [
    ('ip', '',
        "ip to report you have to the tracker."),
    ('minport', DEFAULTPORT, 'minimum port to listen on, counts up if unavailable'),
    ('maxport', DEFAULTPORT, 'maximum port to listen on'),
    ('random_port', 1, 'whether to choose randomly inside the port range ' +
        'instead of counting up linearly'),
    ('bind', '', 
        'comma-separated list of ips/hostnames to bind to locally'),
#    ('ipv6_enabled', autodetect_ipv6(),
    ('ipv6_enabled', 0,
         'allow the client to connect to peers via IPv6'),
    ('ipv6_binds_v4', None,
        "set if an IPv6 server socket won't also field IPv4 connections"),
    ('upnp_nat_access', 3,         # If you change this, look at BitTornado/launchmany/UPnPThread
        'attempt to autoconfigure a UPnP router to forward a server port ' +
        '(0 = disabled, 1 = mode 1 [fast,win32], 2 = mode 2 [slow,win32], 3 = mode 3 [any platform])'),
    ('timeout', 300.0,
        'time to wait between closing sockets which nothing has been received on'),
    ('timeout_check_interval', 60.0,
        'time to wait between checking if any connections have timed out'),
    ('upload_unit_size', 1460,
        "when limiting upload rate, how many bytes to send at a time"),

# Tribler session opts
    ('eckeypair', None, "keypair to use for session"),
    ('cache', 1,
        "use bsddb to cache peers and preferences"),
    ('overlay', 1,
        "create overlay swarm to transfer special messages"),
    ('buddycast', 1,
        "run buddycast recommendation system"),
    ('start_recommender', 1,
        "buddycast can be temp. disabled via this flag"),
    ('download_help', 1,
        "accept download help request"),
    ('torrent_collecting', 1,
        "automatically collect torrents"),
    ('superpeer', 0,
        "run in super peer mode (0 = disabled)"),
    ('overlay_log', '',
        "log on super peer mode ('' = disabled)"),
    ('buddycast_interval', 15,
        "number of seconds to pause between exchanging preference with a peer in buddycast"),
    ('max_torrents', 5000,
        "max number of torrents to collect"),
    ('max_peers', 2000,
        "max number of peers to use for recommender"),
    ('torrent_collecting_rate', 5,
        "max rate of torrent collecting (Kbps)"),
    ('torrent_checking', 1,
        "automatically check the health of torrents"),
    ('torrent_checking_period', 60, 
        "period for auto torrent checking"),
    ('dialback', 1,
        "use other peers to determine external IP address (0 = disabled)"),
    ('dialback_active', 1,
        "do active discovery (needed to disable for testing only) (0 = disabled)"),
    ('dialback_trust_superpeers', 1,
        "trust superpeer replies (needed to disable for testing only) (0 = disabled)"),
    ('dialback_interval', 30,
        "number of seconds to wait for consensus"),
    ('socnet', 1,
        "enable social networking (0 = disabled)"),
    ('rquery', 1,
        "enable remote query (0 = disabled)"),
    ('stop_collecting_threshold', 200,
        "stop collecting more torrents if the disk has less than this size (MB)"),
    ('internaltracker', 1,
        "enable internal tracker (0 = disabled)"),
    ('nickname', '__default_name__',
        'the nickname you want to show to others'),
    ('videoplayerpath', None, 'Path to video analyser (FFMPEG, found automatically if in PATH)')]


# BT per download opts
dldefaults = [
    ('max_uploads', 7,
        "the maximum number of uploads to allow at once."),
    ('keepalive_interval', 120.0,
        'number of seconds to pause between sending keepalives'),
    ('download_slice_size', 2 ** 14,
        "How many bytes to query for per request."),
    ('request_backlog', 10,
        "maximum number of requests to keep in a single pipe at once."),
    ('max_message_length', 2 ** 23,
        "maximum length prefix encoding you'll accept over the wire - larger values get the connection dropped."),
    ('responsefile', '',
        'file the server response was stored in, alternative to url'),
    ('url', '',
        'url to get file from, alternative to responsefile'),
    ('selector_enabled', 1,
        'whether to enable the file selector and fast resume function'),
    ('expire_cache_data', 10,
        'the number of days after which you wish to expire old cache data ' +
        '(0 = disabled)'),
    ('priority', '',
        'a list of file priorities separated by commas, must be one per file, ' +
        '0 = highest, 1 = normal, 2 = lowest, -1 = download disabled'),
    ('saveas', '',
        'local file name to save the file as, null indicates query user'),
    ('max_slice_length', 2 ** 17,
        "maximum length slice to send to peers, larger requests are ignored"),
    ('max_rate_period', 20.0,
        "maximum amount of time to guess the current rate estimate represents"),
    ('upload_rate_fudge', 5.0, 
        'time equivalent of writing to kernel-level TCP buffer, for rate adjustment'),
    ('tcp_ack_fudge', 0.03,
        'how much TCP ACK download overhead to add to upload rate calculations ' +
        '(0 = disabled)'),
    ('rerequest_interval', 5 * 60,
        'time to wait between requesting more peers'),
    ('min_peers', 20, 
        'minimum number of peers to not do rerequesting'),
    ('http_timeout', 60, 
        'number of seconds to wait before assuming that an http connection has timed out'),
    ('max_initiate', 40,
        'number of peers at which to stop initiating new connections'),
    ('check_hashes', 1,
        'whether to check hashes on disk'),
    ('max_upload_rate', 0,
        'maximum kB/s to upload at (0 = no limit, -1 = automatic)'),
    ('max_download_rate', 0,
        'maximum kB/s to download at (0 = no limit)'),
    ('alloc_type', 'normal',
        'allocation type (may be normal, background, pre-allocate or sparse)'),
    ('alloc_rate', 2.0,
        'rate (in MiB/s) to allocate space at using background allocation'),
    ('buffer_reads', 1,
        'whether to buffer disk reads'),
    ('write_buffer_size', 4,
        'the maximum amount of space to use for buffering disk writes ' +
        '(in megabytes, 0 = disabled)'),
    ('breakup_seed_bitfield', 1,
        'sends an incomplete bitfield and then fills with have messages, '
        'in order to get around stupid ISP manipulation'),
    ('snub_time', 30.0,
        "seconds to wait for data to come in over a connection before assuming it's semi-permanently choked"),
    ('spew', 0,
        "whether to display diagnostic info to stdout"),
    ('rarest_first_cutoff', 2,
        "number of downloads at which to switch from random to rarest first"),
    ('rarest_first_priority_cutoff', 5,
        'the number of peers which need to have a piece before other partials take priority over rarest first'),
    ('min_uploads', 4,
        "the number of uploads to fill out to with extra optimistic unchokes"),
    ('max_files_open', 50,
        'the maximum number of files to keep open at a time, 0 means no limit'),
    ('round_robin_period', 30,
        "the number of seconds between the client's switching upload targets"),
    ('super_seeder', 0,
        "whether to use special upload-efficiency-maximizing routines (only for dedicated seeds)"),
    ('security', 1,
        "whether to enable extra security features intended to prevent abuse"),
    ('max_connections', 0,
        "the absolute maximum number of peers to connect with (0 = no limit)"),
    ('auto_kick', 1,
        "whether to allow the client to automatically kick/ban peers that send bad data"),
    ('double_check', 1,
        "whether to double-check data being written to the disk for errors (may increase CPU load)"),
    ('triple_check', 0,
        "whether to thoroughly check data being written to the disk (may slow disk access)"),
    ('lock_files', 1,
        "whether to lock files the client is working with"),
    ('lock_while_reading', 0,
        "whether to lock access to files being read"),
    ('auto_flush', 0,
        "minutes between automatic flushes to disk (0 = disabled)"),
#
# Tribler per-download opts
#
    ('role', '', # 'helper', 'coordinator'
        "role of the peer in the download"),
    ('helpers_file', '',
        "file with the list of friends"),
    ('coordinator_permid', '',
        "PermID of the cooperative download coordinator"),
    ('exclude_ips', '',
        "list of IP addresse to be excluded; comma separated"),
    ('vod', 0,
        "download in video-on-demand mode (0 = disabled)"),
    ('ut_pex_max_addrs_from_peer', 16,
            "maximum number of addresses to accept from peer (0 = disabled PEX)")]


tdefdictdefaults = [ 
    ('comment', '', "comment field"),
    ('created by', '', "created by field"),
    ('announce', '', "default tracker"),
    ('announce-list', '', "default announce list"), 
    ('httpseeds', '',  "default httpseeds") ]

tdefmetadefaults = [
    ('piece_size', 0, "piece size as int (0 = automatic)"), 
    ('makehash_md5', 0, "add end-to-end MD5 checksum"), 
    ('makehash_crc32', 0, "add end-to-end CRC32 checksum"), 
    ('makehash_sha1', 0, "add end-to-end SHA1 checksum"), 
    ('createmerkletorrent', 1, "create a Merkle torrent (.tribe, Tribler only)"),
    ('createtorrentsig', 0, "whether to add a signature to the torrent"),
    ('torrentsigkeypair', None, "keypair for signature"),
    ('thumb', None, "image for video torrents, format: 171x96 JPEG")
    ]

tdefdefaults = tdefdictdefaults + tdefmetadefaults




class Serializable:
    """
    Interface to signal that the object is pickleable.
    """
    def __get_state__(self):
        raise NotYetImplementedException()
    
    def __set_state__(self,state):
        raise NotYetImplementedException()


class Defaultable:
    """
    Interface for setting a default instance for a class
    """
    def get_copy_of_default(*args,**kwargs):
        """
        A class method that returns a copy of the current default.
        """
        raise NotYetImplementedException()
    #get_copy_of_default = staticmethod(get_copy_of_default)
    

    def get_default(*args,**kwargs): 
        """
        A class method that returns the current default (not a copy). Use this
        method to modify the default config once set with set_default()
        """
        raise NotYetImplementedException()
    #get_default = staticmethod(get_default)
    
    def set_default(x): # If not singleton
        """
        A class method that sets the default for this class to "x" (note: x
        is not copied)
        
        in: x = an unbound instance of the class 
        """
        raise NotYetImplementedException()
    #set_default = staticmethod(set_default)


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



class Bindable:

    def __init__(self):
        self.bindlock = BindLock()
        self.configee = None
    
    def bind(self,lock):
        self.bindlock.set(lock)
        
    def set_configee(self,configee):
        self.configee = configee
        
    def is_bound(self):
        return self.bindlock.get()


class BindLock:
    
    def __init__(self):
        self.lock = None
        
    def acquire(self):
        if self.lock is not None:
            self.lock.acquire()
            
    def release(self):
        if self.lock is not None:
            self.lock.release()

    def set(self,lock):
        self.lock = lock
        
    def get(self):
        return self.lock


#
# Exceptions
#
class TriblerException(Exception):
    
    def __init__(self):
        Exception.__init__(self)
        

class OperationNotPermittedWhenBoundException(TriblerException):
    
    def __init__(self):
        TriblerException.__init__(self)
    
class NotYetImplementedException(TriblerException):
    
    def __init__(self):
        TriblerException.__init__(self)


class Session(Serializable):
    """
    cf. libtorrent session
    """
    def __init__(self,scfg=None):
        """
        A Session object is created which is configured following a copy of the
        SessionConfig scfg.
        
        in: scfg = SessionConfig object or None, in which case 
        SessionConfig.get_copy_of_default() is called and the returned config
        becomes the bound config of the session.
        """
        self.lock = RLock()
        
        if scfg is None:
            self.scfg = SessionConfig.get_copy_of_default()
        else:
            self.scfg = scfg.copy()
            
        print >>sys.stderr,"Session: scfg is",self.scfg
        self.scfg.bind(self.lock)
        
        # Core init
        resetPeerIDs()
        Tribler.Overlay.permid.init()
        if self.scfg.config['eckeypair'] is None:
            self.scfg.config['eckeypair'] = Tribler.Overlay.permid.generate_keypair()
        
        self.lm = TriblerLaunchMany(self.scfg,self.lock)
        self.lm.start()
        
        self.scfg.set_configee(self.lm)

    def get_config(self):
        """
        Return the Session's config (note: not a copy)
        
        returns: a bound SessionConfig object
        """
        # no lock, not changable
        return self.scfg
    
    
    def start_download(self,tdef,dcfg=None):
        """ 
        Creates a Download object and adds it to the session. The passed 
        TorrentDef and DownloadConfig are copied into the new Download object
        and the copies become bound.
        
        in:
        tdef = TorrentDef
        drcfg = DownloadConfig or None, in which case 
        DownloadConfig.get_copy_of_default() is called and the result becomes 
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
    
    def remove_download(self,d):  
        """
        Stops the download and removes it from the session.
        """
        # locking by lm
        self.lm.remove(d)


    
class SessionConfig(Defaultable,Copyable,Serializable,Bindable):  
    # Defaultable only if Session is not singleton
    
    _default = None
    
    """ 
    (key,value) pair config of global parameters, 
    e.g. PermID keypair, listen port, max upload, etc.
    """
    def __init__(self,config=None):
        Bindable.__init__(self)
        
        if config is not None: # copy constructor
            self.config = config
            return
        
        self.config = {}
        self.bindlock = BindLock()
        
        # Define the built-in default here
        for key,val,expl in sessdefaults:
            self.config[key] = val
    
        if sys.platform == 'win32':
            self.config['videoanalyserpath'] = self.getPath()+'\\ffmpeg.exe'
        elif sys.platform == 'darwin':
            ffmpegpath = find_prog_in_PATH("ffmpeg")
            if ffmpegpath is None:
                self.config['videoanalyserpath'] = "lib/ffmpeg"
            else:
                self.config['videoanalyserpath'] = ffmpegpath
        else:
            ffmpegpath = find_prog_in_PATH("ffmpeg")
            if ffmpegpath is None:
                self.config['videoanalyserpath'] = "ffmpeg"
            else:
                self.config['videoanalyserpath'] = ffmpegpath

    
        self.config['ipv6_binds_v4'] = autodetect_socket_style()
    
    
        # TEMP ARNO: session max vs download max 
        self.config['max_upload_rate'] = 0
    
        # TEMP TODO
        self.config['overlay'] = 0
    
    
    def set_permid(self,keypair):
        if not self.is_bound():
            self.config['eckeypair'] = keypair
        else:
            raise OperationNotPermittedWhenBoundException()
        
    def set_listen_port(self,port):
        """
        ISSUE: do we allow runtime modification of this param? Theoretically
        possible, a bit hard to implement
        """
        if not self.is_bound():
            self.config['minport'] = port
            self.config['maxport'] = port
            # ISSUE: must raise exception at Session start when port already in use.
        else:
            raise OperationNotPermittedWhenBoundException()

    def get_listen_port(self):
        # Cheap because BindLock won't really lock until bound
        # Lock protects dict, not also minport, as minport is currently not
        # runtime modifiable
        #
        self.bindlock.acquire()
        return self.config['minport']
        self.bindlock.release()
        
        
    def set_max_upload(self,speed):
        if not self.is_bound():
            self.config['max_upload_rate'] = speed
        else:
            def change():
                self.configee.setUploadRate(speed)
                self.config['max_upload_rate'] = speed
            self._change_runtime_param(change)
        
    def set_max_connections(self,nconns):
        if not self.is_bound():
            self.config['max_connections'] = nconns
        else:
            def change():
                self.configee.set_max_connections(speed)
                self.config['max_connections'] = nconns
            self._change_runtime_param(change)

    def get_video_analyser_path(self):
        self.bindlock.acquire()
        return self.config['videoanalyserpath'] # strings immutable
        self.bindlock.release()
    

    #
    # Defaultable interface
    #
    def get_copy_of_default(*args,**kwargs):
        """ Not thread safe """
        print >>sys.stderr,"SessionConfig::get_copy_of_default",SessionConfig._default
        if SessionConfig._default is None:
            SessionConfig._default = SessionConfig()
            print >>sys.stderr,"SessionConfig::get_copy_of_default2",SessionConfig._default
        c = SessionConfig._default.copy()
        print >>sys.stderr,"SessionConfig::get_copy_of_default, copy is",c
        return c
    get_copy_of_default = staticmethod(get_copy_of_default)

    def get_default():
        """ Not thread safe """
        return SessionConfig._default

    def set_default(scfg):
        """ Not thread safe """
        SessionConfig._default = scfg

    #
    # Copyable interface
    # 
    def copy(self):
        if self.is_bound():
            raise OperationNotPermittedWhenBoundException()
        
        config = copy.copy(self.config)
        return SessionConfig(config)

    #
    # Internal method
    #
    def _change_runtime_param(self,func):
        self.bindlock.acquire()
        try:
            func()
        finally:
            self.bindlock.release()
        
        


#class TorrentDef(DictMixin,Defaultable,Copyable,Serializable):
class TorrentDef(Defaultable,Copyable,Serializable,Bindable):
    """
    Definition of a torrent, i.e. all params required for a torrent file,
    plus optional params such as thumbnail, playtime, etc.

    ISSUE: should we make this a simple dict interface, or provide user-friendly
    functions for e.g. handling encoding issues for filenames, setting 
    thumbnails, etc. 
    
    My proposal is to have both, so novice users can use the simple ones, and 
    advanced users can still control all fields.
    
    cf. libtorrent torrent_info
    """
    def __init__(self,config=None,input=None,metainfo=None,infohash=None):
        Bindable.__init__(self)
        
        if config is not None:
            self.config = config
            self.input = input
            self.metainfo = metainfo
            self.infohash = infohash
            return
            
        self.config = {}
        self.input = {} # fields added by user, waiting to be turned into torrent file
        self.input['files'] = []
        self.metainfo_valid = False
        self.metainfo = None # copy of loaded or last saved torrent dict
        self.infohash = None # only valid if metainfo_valid
        
        # Define the built-in default here
        for key,val,expl in tdefmetadefaults:
            self.config[key] = val

        for key,val,expl in tdefdictdefaults:
            self.input[key] = val
        
        self.input['announce'] = 'bla' # Hmmm... this depends on the default SessionConfig ISSUE


    #
    # Class methods for creating a TorrentDef from a .torrent file
    #
    def load(filename):
        """
        ISSUE: We could a single load() method that takes an URL as argument.
        This could be a HTTP URL or a file URL. Problem is that formally a 
        Unicode filename of the local filesystem would have to be encoded 
        according to the URL encoding rules first.
        
        SOLUTION: have load() and load_from_url()
        """
        # Class method, no locking required
        f = open(filename,"rb")
        return TorrentDef._read(f)
    load = staticmethod(load)
        
    def _read(stream):
        bdata = stream.read()
        stream.close()
        data = bdecode(bdata)
        
        t = TorrentDef()
        # TODO: integrity check
        t.metainfo = data
        t.metainfo_valid = True
        t.infohash = sha.sha(bencode(data['info'])).digest()
        # copy stuff into self.input 
        #TODO
        t.input = None # provoke error when used, so we know this is TODO
        return t
    _read = staticmethod(_read)

    def load_from_url(url):
        """
        in:
        torrenturl = URL of file
        """
        # Class method, no locking required
        f = urlTimeoutOpen(url)
        return TorrentDef._read(f)
    load_from_url = staticmethod(load_from_url)

    #
    # Instance methods
    #
    def save(self,filename):
        """
        Writes torrent file data (i.e., bencoded dict following BT spec)
        in:
        filename = Unicode string
        """
        # Lock & write
        self.bindlock.acquire()
        try:
            # TODO: should be possible when bound
            raise NotYetImplementedException()
        finally:
            self.bindlock.releas()
        """
            bn = os.path.basename(filename)
            # How to encode Unicode filename? TODO
            
            # When to read file to calc hashes? TODO (could do now and keep pieces in mem until
            # torrent file / bind time. Update: Need to wait until we know piece size.
        """ 


    #
    # Convenience methods for publishing new content
    #
    def add_file(self,filename,playtime=None):
        """
        Add a file to this torrent definition. The core will not copy the file
        when starting the sharing, but seeds from the passed file directly.
        
        in:
        filename = Fully-qualified name of file on local filesystem, as Unicode
                   string
        playtime = (optional) String representing the duration of the multimedia
                   file when played, in [hh:]mm:ss format. 
        """
        if self.isbound():
            raise OperationNotPermittedWhenBoundException()

        s = os.stat(filename)
        d = {'fn':filename,'playtime':playtime,'length':s.st_size}
        self.input['files'].append(d)
        self.metainfo_valid = False

    def get_thumbnail(self):
        """
        returns: (MIME type,thumbnail data) if present or (None,None)
        """
        # Lock just protects self.config, not also thumb, that is currently
        # not runtime modifiable.
        self.bindlock.acquire()
        if thumb is None:
            ret = (None,None)
        else:
            thumb = self.input['thumb'] # buffer/string immutable
            ret = ('image/jpeg',thumb)
        self.bindlock.releas()
        return ret
        
        
    def set_thumbnail(self,thumbfilename):
        """
        Reads image from file and turns it into a torrent thumbnail
        
        ISSUE: do we do the image manipulation? If so we need extra libs, 
        perhaps wx to do this. It is more convenient for the API user.
        
        in:
        thumbfilename = Fully qualified name of image file, as Unicode string.
        
        exceptions: ...Error
        """
        if self.isbound():
            raise OperationNotPermittedWhenBoundException()
        
        f = open(thumbfilename,"rb")
        data = f.read()
        f.close()
        self.input['thumb'] = data 
        self.metainfo_valid = False
        

        
    def finalize(self):
        """ Create BT torrent file from input and calculate infohash """
        self.bindlock.acquire()
        try:
            if self.metainfo_valid:
                return (self.infohash,self.metainfo)
            else:
                raise NotYetImplementedException()
        finally:
            self.bindlock.release()

    #
    # 
    #
    def get_infohash(self):
        if self.metainfo_valid:
            return self.infohash
        else:
            raise NotYetImplementedException() # must save first


    #
    # DictMixin
    #
    # TODO: make thread safe when bound

    #
    # Defaultable interface can be used to things such as default tracker, which
    # end-to-end checksums to include, etc.
    #


    #
    # Copyable interface
    # 
    def copy(self):
        if self.is_bound():
            raise OperationNotPermittedWhenBoundException()
        
        config = copy.copy(self.config)
        input = copy.copy(self.input)
        metainfo = copy.copy(self.metainfo)
        infohash = self.infohash
        t = TorrentDef(config,input,metainfo,infohash)
        t.metainfo_valid = self.metainfo_valid
        return t

    
class DownloadConfig(Defaultable,Copyable,Serializable,Bindable):
    """
    (key,value) pair config of per-torrent runtime parameters,
    e.g. destdir, file-allocation policy, etc. Also options to advocate
    torrent, e.g. register in DHT, advertise via Buddycast.
    
    ISSUE: some values will be runtime modifiable, others may be as well
    but hard to implement, e.g. destdir or VOD.
    SOL: We throw exceptions when it is not runtime modifiable, and 
    document for each method which currently is.
     
    cf. libtorrent torrent_handle
    """
    _default = None
    
    
    def __init__(self,config=None):
        Bindable.__init__(self)
        
        if config is not None: # copy constructor
            self.config = config
            return

        
        self.config = {}
        
        # Define the built-in default here
        for key,val,expl in dldefaults:
            self.config[key] = val
       
        if sys.platform == 'win32':
            profiledir = os.path.expandvars('${USERPROFILE}')
            tempdir = os.path.join(profiledir,'Desktop','TriblerDownloads')
            self.config['saveas'] = tempdir 
        elif sys.platform == 'darwin':
            profiledir = os.path.expandvars('${HOME}')
            tempdir = os.path.join(profiledir,'Desktop','TriblerDownloads')
            self.config['saveas'] = tempdir
        else:
            self.config['saveas'] = '/tmp'

        # TODO: is now sess param, how to set here?
        self.config['upload_unit_size'] = 1460

    
    def set_max_upload(self,speed):
        """
        ISSUE: How do session maximums and torrent maximums coexist?
        """
        if not self.isbound():
            self.config['max_upload'] = speed
        else:
            def change():
                self.configee.set_max_upload(speed)
                self.config['max_upload'] = speed
            self._change_runtime_param(change)


    #
    # Defaultable interface
    #
    def get_copy_of_default(*args,**kwargs):
        """ Not thread safe """
        print >>sys.stderr,"DownloadConfig::get_copy_of_default",DownloadConfig._default
        if DownloadConfig._default is None:
            DownloadConfig._default = DownloadConfig()
            print >>sys.stderr,"DownloadConfig::get_copy_of_default2",DownloadConfig._default
        c = DownloadConfig._default.copy()
        print >>sys.stderr,"DownloadConfig::get_copy_of_default, copy is",c
        return c
    get_copy_of_default = staticmethod(get_copy_of_default)

    def get_default():
        """ Not thread safe """
        return DownloadConfig._default

    def set_default(scfg):
        """ Not thread safe """
        DownloadConfig._default = scfg


    #
    # Copyable interface
    # 
    def copy(self):
        if self.is_bound():
            raise OperationNotPermittedWhenBoundException()
        
        config = copy.copy(self.config)
        return DownloadConfig(config)


    #
    # Internal method
    #
    def _change_runtime_param(self,func):
        self.bindlock.acquire()
        ex = None
        try:
            func()
        except Exception,e:
            ex = e
        self.bindlock.release()
        if ex is not None:
            raise ex
        
        
class Download:
    """
    Representation of a running BT download/upload
    
    cf. libtorrent torrent_handle
    """
    
    #
    # Internal method
    #
    def __init__(self,lock,scfg,lm,tdef,dcfg=None):
        """
        Create a Download object. Used internally by Session. Copies tdef and 
        dcfg and binds them to this download.
        
        in: 
        tdef = unbound TorrentDef
        dcfg = unbound DownloadConfig or None (in which case DownloadConfig.get_copy_of\
        _default() is called and the result becomes the (bound) config of this
        Download.
        """
        self.tdef = tdef.copy()
        if dcfg is None:
            self.dcfg = DownloadConfig.get_copy_of_default()
        else:
            self.dcfg = dcfg.copy()
        
        self.tdef.bind(lock)
        self.dcfg.bind(lock)
        
        self.lm= lm
        
        
        # TODO: set IP to report to tracker. Make dependeny on DialbackMsg
        # and UPnP results
        self.dcfg.config['ip'] = lm.locally_guessed_wanip
        

        (infohash,metainfo) = self.tdef.finalize()
        kvconfig = self.dcfg.config
        
        self.dldoneflag = Event()
        self.rawserver = self.lm.multihandler.newRawServer(infohash,self.dldoneflag)

        """
        class BT1Download:    
            def __init__(self, statusfunc, finfunc, errorfunc, excfunc, doneflag, 
                 config, response, infohash, id, rawserver, port, play_video,
                 videoinfo, progressinf, videoanalyserpath, appdataobj = None, dht = None):
        """
        self.dow = BT1Download(self._statusfunc,
                        self._finishedfunc,
                        self._errorfunc, 
                        self._exceptionfunc,
                        self.dldoneflag,
                        kvconfig,
                        metainfo, 
                        infohash,
                        createPeerID(),
                        self.rawserver,
                        scfg.get_listen_port(),
                        #config['vod'], Arno: read from kvconfig
                        [],    # TODO: how to set which video in a multi-video torrent to play
                        #None, # = progressinf: now via DownloadState
                        scfg.get_video_analyser_path()
                        # TODO: dht
                        )

        self.dcfg.set_configee(self.dow)
    
        if not self.dow.saveAs(self.save_as):
            # TODO: let saveAs throw exceptions
            return
        self._hashcheckfunc = self.dow.initFiles()
        if not self._hashcheckfunc:
            self.shutdown()
            return

        self.lm.queue_for_hashcheck(self)
        if DEBUG:
            print >>sys.stderr,"engine: start: after hashchecksched"
    
    
    def save_as(self,name,length,saveas,isdir):
        """ Return the local filename to which to save the file 'name' in the torrent """
        print >>sys.stderr,"Download: save_as(",name,length,saveas,isdir,")"
        path = os.path.join(saveas,name)
        if isdir and not os.path.isdir(path):
            os.mkdir(path)
        return path

    def perform_hashcheck(self,complete_callback):
        print >>sys.stderr,"Download: hashcheck()",self._hashcheckfunc
        self._hashcheckfunc(complete_callback)
    
    def hashcheck_done(self):
        """ Called by LaunchMany when hashcheck complete and the Download can be
            resumed
        """
        print >>sys.stderr,"Download: hashcheck_done()"
        if not self.dow.startEngine():
            print >>sys.stderr,"Download: hashcheck_complete: startEngine failed"
            return

        self.dow.startRerequester()
        self.rawserver.start_listening(self.dow.getPortHandler())

    
    #
    # Public methods
    #
    def get_def(self):
        """
        Returns the bound TorrentDef
        """
        # No lock because attrib immutable and return value protected
        return self.tdef
    
    def get_config(self):
        """
        Returns the bound DownloadConfig
        """
        # No lock because attrib immutable and return value protected
        return self.dcfg
        
    def get_state(self):
        """ 
        returns: copy of internal download state (so not live pointers into 
        engine)
        """
        return DownloadState()

    def stop(self):
        self.bindlock.acquire()
        try:
            # TODO: how do we access the BT1Download object?
            raise NotYetImplementedException()
        finally:
            self.bindlock.release()
        
    def restart(self):
        self.bindlock.acquire()
        try:
            raise NotYetImplementedException()
        finally:
            self.bindlock.release()

        
    def pause(self):
        self.bindlock.acquire()
        try:
            raise NotYetImplementedException()
        finally:
            self.bindlock.release()

    #
    # Internal methods
    #
    def _statusfunc(self,activity = '', fractionDone = 0.0):
        print >>sys.stderr,"Session::_statusfunc called",activity,fractionDone

    def _finishedfunc(self):
        print >>sys.stderr,"Session::_finishedfunc called"

    def _errorfunc(self,msg):
        print >>sys.stderr,"Session::_errorfunc called",msg

    def _exceptionfunc(self,e):
        print >>sys.stderr,"Session::_exceptfunc called",e

        

    
class DownloadState:
    """
    Contains a snapshot of the state of the Download at a specific
    point in time. Using a snapshot instead of providing live data and 
    protecting access via locking should be faster.
    
    ALT: callback interface: Advantage over pull: always accurate. Disadv: 
    how does that work? Do we callback for every change in state, from peer 
    DL speed to...? Tribler currently does periodic pull. You will want to 
    batch things in time (once per sec) and per item (i.e., all events for 1 
    torrent in one batch)
    
    I propose that for the initial API we use pull.
    
    cf. libtorrent torrent_status

    ISSUE: some of this state such as piece admin for some file-alloc modes 
    must be savable. It is wise to also save the torrent runtime config along,
    so determine at which level we should offer save/load methods. E.g.
    just let DownloadState and DownloadConfig return data which e.g.
    Download saves in single file.
    
    How do we support this? Copying file alloc admin each time is overhead.
    SOL: have parameter for get_state(), indicating "complete"/"simplestats", 
    etc.
    """
    def __init__(self):
        pass
    
    def get_progress(self):
        """
        returns: percentage of torrent downloaded, as float
        """
        return 10.0
        
    def get_status(self):
        """
        returns: status of the torrent, e.g. stopped, paused, queued, 
        hashchecking, active
        
        ISSUE: what is the status? e.g. is seeding a status value or is that 
        the same as when the torrent is active and progress is 100%?
        """
        return 1



class TriblerLaunchMany(Thread):
    
    def __init__(self,scfg,lock):
        Thread.__init__(self)
        self.setDaemon(True)
        self.setName("Network"+self.getName())
        
        self.scfg = scfg
        self.lock = lock
        
        self.downloads = {}
        config = scfg.config # Should be safe at startup

        self.locally_guessed_wanip = self.get_my_ip()

        # Orig
        self.sessdoneflag = Event()
        self.upnp_type = config['upnp_nat_access'] # TODO: use methods to read values?
        self.hashcheck_queue = []
        self.downloadtohashcheck = None


        self.rawserver = RawServer(self.sessdoneflag,
                                   config['timeout_check_interval'],
                                   config['timeout'],
                                   ipv6_enable = config['ipv6_enabled'],
                                   failfunc = self.failfunc,
                                   errorfunc = self.exceptionfunc)
        self.rawserver.add_task(self.rawserver_keepalive,1)
        
        self.listen_port = self.rawserver.find_and_bind(0, 
                    config['minport'], config['maxport'], config['bind'], 
                    reuse = True,
                    ipv6_socket_style = config['ipv6_binds_v4'], 
                    randomizer = config['random_port'])
        print "Got listen port", self.listen_port
        
        self.ratelimiter = RateLimiter(self.rawserver.add_task, 
                                       config['upload_unit_size'])
        self.ratelimiter.set_upload_rate(config['max_upload_rate'])

        self.multihandler = MultiHandler(self.rawserver, self.sessdoneflag)
        #
        # Arno: disabling out startup of torrents, need to fix this
        # to let text-mode work again.
        #

        # do_cache -> do_overlay -> (do_buddycast, do_download_help)
        if not config['cache']:
            config['overlay'] = 0    # overlay
        if not config['overlay']:
            config['buddycast'] = 0
            config['download_help'] = 0

        if config['overlay']:
            self.secure_overlay = SecureOverlay.getInstance()
            mykeypair = config['eckeypair']
            self.secure_overlay.register(self.rawserver,self.multihandler,self.listen_port,self.config['max_message_length'],mykeypair)
            self.overlay_apps = OverlayApps.getInstance()
            self.overlay_apps.register(self.secure_overlay, self, self.rawserver, config)
            # It's important we don't start listening to the network until
            # all higher protocol-handling layers are properly configured.
            self.secure_overlay.start_listening()
        
        self.internaltracker = None
        if config['internaltracker'] and 'trackerconf' in config:
            # TEMP ARNO TODO: make sure trackerconf also set when using btlaunchmany
            tconfig = config['trackerconf']
            self.internaltracker = Tracker(tconfig, self.rawserver)
            self.httphandler = HTTPHandler(self.internaltracker.get, tconfig['min_time_between_log_flushes'])
        else:
            self.httphandler = DummyHTTPHandler()
        self.multihandler.set_httphandler(self.httphandler)
        
        # APITODO
        #self.torrent_db = TorrentDBHandler()
        #self.mypref_db = MyPreferenceDBHandler()
        
        # add task for tracker checking
        if not config['torrent_checking']:
            self.rawserver.add_task(self.torrent_checking, self.torrent_checking_period)
        

    def add(self,tdef,dcfg):
        self.lock.acquire()
        try:
            d = Download(self.lock,self.scfg,self,tdef,dcfg)
            self.downloads[d.get_def().get_infohash()] = d
        finally:
            self.lock.release()
        return d
        
    def remove(self,d):
        self.lock.acquire()
        try:
            d.stop()
            d._cleanup_disk()
            del self.downloads[d.get_def().get_infohash()]
        finally:
            self.lock.release()

    def get_downloads(self):
        self.lock.acquire()
        try:
            l = self.downloads[:] #copy, is mutable
        finally:
            self.lock.release()
        return l
    
    def failfunc(self,msg):
        print >>sys.stderr,"TriblerLaunchMany: failfunc called",msg

    def exceptionfunc(self,e):
        print >>sys.stderr,"TriblerLaunchmany: exceptfunc called",e


    def run(self):
        try:
            self.start_upnp()
            self.multihandler.listen_forever()
        finally:
            print_exc()
            self.stop_upnp()
            self.rawserver.shutdown()

    def rawserver_keepalive(self):
        """ Hack to prevent rawserver sleeping in select() for a long time, not
        processing any tasks on its queue at startup time """
        self.rawserver.add_task(self.rawserver_keepalive,1)

    def get_my_ip(self):
        ip = get_my_wan_ip()
        if ip is None:
            host = socket.gethostbyname_ex(socket.gethostname())
            ipaddrlist = host[2]
            for ip in ipaddrlist:
                return ip
            return '127.0.0.1'
        else:
            return ip


    def start_upnp(self):
        # Arno: as the UPnP discovery and calls to the firewall can be slow,
        # do it in a separate thread. When it fails, it should report popup
        # a dialog to inform and help the user. Or report an error in textmode.
        #
        # Must save type here, to handle case where user changes the type
        # In that case we still need to delete the port mapping using the old mechanism

        self.upnp_thread = UPnPThread(self.upnp_type,self.locally_guessed_wanip,self.listen_port,self.upnp_failed,self)
        self.upnp_thread.start()

    def stop_upnp(self):
        if self.upnp_type > 0:
            self.upnp_thread.shutdown()

    def upnp_failed(self,upnp_type,listenport,error_type,exc=None,listenproto='TCP'):
        self.failfunc("UPnP mode "+str(upnp_type)+" request to firewall failed with error "+str(error_type)+" Try setting a different mode in Preferences. Listen port was "+str(listenport)+", protocol"+listenproto)


    def set_activity(self,type):
        pass # TODO


    def queue_for_hashcheck(self,d):
        """ Schedule a Download for integrity check of on-disk data"""
        if hash:
            self.hashcheck_queue.append(d)
            # Check smallest torrents first
            self.hashcheck_queue.sort(lambda x, y: cmp(self.downloads[x].dow.datalength, self.downloads[y].dow.datalength))
        if not self.downloadtohashcheck:
            self.dequeue_and_start_hashcheck()

    def dequeue_and_start_hashcheck(self):
        """ Start integriy check for first Download in queue"""
        self.downloadtohashcheck = self.hashcheck_queue.pop(0)
        self.downloadtohashcheck.perform_hashcheck(self.hashcheck_done)

    def hashcheck_done(self):
        """ Integrity check for first Download in queue done """
        self.downloadtohashcheck.hashcheck_done()
        if self.hashcheck_queue:
            self.dequeue_and_start_hashcheck()
        else:
            self.downloadtohashcheck = None




class UPnPThread(Thread):
    """ Thread to run the UPnP code. Moved out of main startup-
        sequence for performance. As you can see this thread won't
        exit until the client exits. This is due to a funky problem
        with UPnP mode 2. That uses Win32/COM API calls to find and
        talk to the UPnP-enabled firewall. This mechanism apparently
        requires all calls to be carried out by the same thread.
        This means we cannot let the final DeletePortMapping(port) 
        (==UPnPWrapper.close(port)) be done by a different thread,
        and we have to make this one wait until client shutdown.

        Arno, 2006-11-12
    """

    def __init__(self,upnp_type,wanip,listen_port,error_func,launchmany):
        Thread.__init__(self)
        self.setDaemon(True)
        self.setName( "UPnP"+self.getName() )
        
        self.upnp_type = upnp_type
        self.locally_guessed_wanip = wanip
        self.listen_port = listen_port
        self.error_func = error_func
        self.launchmany = launchmany
        self.shutdownevent = Event()

    def run(self):
        dmh = DialbackMsgHandler.getInstance()
                
        if self.upnp_type > 0:
            self.upnp_wrap = UPnPWrapper.getInstance()
            self.upnp_wrap.register(self.locally_guessed_wanip)

            self.launchmany.set_activity(ACT_UPNP)
            if self.upnp_wrap.test(self.upnp_type):
                try:
                    shownerror=False
                    # Get external IP address from firewall
                    if self.upnp_type != 1: # Mode 1 doesn't support getting the IP address"
                        ret = self.upnp_wrap.get_ext_ip()
                        if ret == None:
                            shownerror=True
                            self.error_func(self.upnp_type,self.listen_port,0)
                        else:
                            self.handle_ext_ip(ret,dmh)

                    # Do open_port irrespective of whether get_ext_ip()
                    # succeeds, UPnP mode 1 doesn't support get_ext_ip()
                    # get_ext_ip() must be done first to ensure we have the 
                    # right IP ASAP.
                    
                    # Open TCP listen port on firewall
                    ret = self.upnp_wrap.open(self.listen_port,iproto='TCP')
                    if ret == False and not shownerror:
                        self.error_func(self.upnp_type,self.listen_port,0)

                    # Open UDP listen port on firewall
                    ret = self.upnp_wrap.open(self.listen_port,iproto='UDP')
                    if ret == False and not shownerror:
                        self.error_func(self.upnp_type,self.listen_port,0,listenproto='UDP')
                
                except UPnPError,e:
                    self.error_func(self.upnp_type,self.listen_port,1,e)
            else:
                if self.upnp_type != 3:
                    self.error_func(self.upnp_type,self.listen_port,2)
                elif DEBUG:
                    print >>sys.stderr,"upnp: thread: Initialization failed, but didn't report error because UPnP mode 3 is now enabled by default"

        # Now that the firewall is hopefully open, activate other services
        # here. For Buddycast we don't have an explicit notification that it
        # can go ahead. It will start 15 seconds after client startup, which
        # is assumed to be sufficient for UPnP to open the firewall.
        ## dmh.start_active()

        if self.upnp_type > 0:
            if DEBUG:
                print >>sys.stderr,"upnp: thread: Waiting till shutdown"
            self.shutdownevent.wait()
            # Don't write to sys.stderr, that sometimes doesn't seem to exist
            # any more?! Python garbage collection funkiness of module sys import?
            # The GUI is definitely gone, so don't use self.error_func()
            if DEBUG:
                print "upnp: thread: Shutting down, closing port on firewall"
            try:
                self.upnp_wrap.close(self.listen_port,iproto='TCP')
                self.upnp_wrap.close(self.listen_port,iproto='UDP')
            except Exception,e:
                print "upnp: thread: close port at shutdown threw",e
                print_exc()

        # End of UPnPThread

    def handle_ext_ip(self,upnp_ip,dmh):
        # We learned our external IP address via UPnP
        dmh.upnp_got_ext_ip(upnp_ip)
        
        # TODO: safe found IP address somewhere

    def shutdown(self):
        self.shutdownevent.set()




if __name__ == "__main__":
    
    s = Session()
    tdef = TorrentDef.load('/tmp/bla.torrent')
    
    print >>sys.stderr,"main: TorrentDef is",tdef
    d = s.start_download(tdef)
    while True:
        print d.get_state().get_progress()
        time.sleep(5)

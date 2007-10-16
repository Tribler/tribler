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
    dcfg = DownloadStartupConfig.get_copy_of_default()
    dcfg.set_dest_dir('/tmp')
    d = s.start_download(tdef,dcfg)


Simple VOD download session
===========================
    s = Session()
    tdef = TorrentDef.load('/tmp/bla.torrent')
    dcfg = DownloadStartupConfig.get_copy_of_default()
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
asynchronous. SOL: easiest is async, as network thread does actual changing
2007-10-15: can use Download condition variable for synchronous perhaps? 
 

ALTERNATIVE:
Use copy in/out semantics for TorrentDef and DownloadStartupConfig. A disadvantage of 
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
from threading import RLock,Condition,Event,Thread
from traceback import print_exc,print_stack

from BitTornado.__init__ import resetPeerIDs,createPeerID
from BitTornado.RawServer import autodetect_socket_style
from BitTornado.bencode import bencode,bdecode
from BitTornado.download_bt1 import BT1Download
import Tribler.Overlay.permid
from Tribler.NATFirewall.guessip import get_my_wan_ip
from Tribler.utilities import find_prog_in_PATH,validTorrentFile


from BitTornado.RawServer import RawServer
from BitTornado.ServerPortHandler import MultiHandler
from BitTornado.RateLimiter import RateLimiter
from BitTornado.natpunch import UPnPWrapper, UPnPError
from BitTornado.BT1.track import Tracker
from BitTornado.HTTPHandler import HTTPHandler,DummyHTTPHandler

from Tribler.Overlay.SecureOverlay import SecureOverlay
from Tribler.Overlay.OverlayApps import OverlayApps
from Tribler.NATFirewall.DialbackMsgHandler import DialbackMsgHandler
from triblerdefs import *

# TEMP
from Tribler.Dialogs.activities import *

DEBUG = True


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



# Exceptions
#
class TriblerException(Exception):
    
    def __init__(self):
        Exception.__init__(self)
        

class OperationNotPossibleAtRuntimeException(TriblerException):
    
    def __init__(self):
        TriblerException.__init__(self)
    
class NotYetImplementedException(TriblerException):
    
    def __init__(self):
        TriblerException.__init__(self)


class DownloadIsStoppedException(TriblerException):
    
    def __init__(self):
        TriblerException.__init__(self)


#
# API classes
#

    
class SessionConfigInterface:
    """ 
    (key,value) pair config of global parameters, 
    e.g. PermID keypair, listen port, max upload, etc.
    
    Use SessionStartupConfig from creating and manipulation configurations
    before session startup time. This is just a parent class.
    """
    def __init__(self,sessconfig=None):
        
        if sessconfig is not None: # copy constructor
            self.sessconfig = sessconfig
            return
        
        self.sessconfig = {}
        
        # Define the built-in default here
        for key,val,expl in sessdefaults:
            self.sessconfig[key] = val
    
        if sys.platform == 'win32':
            self.sessconfig['videoanalyserpath'] = self.getPath()+'\\ffmpeg.exe'
        elif sys.platform == 'darwin':
            ffmpegpath = find_prog_in_PATH("ffmpeg")
            if ffmpegpath is None:
                self.sessconfig['videoanalyserpath'] = "lib/ffmpeg"
            else:
                self.sessconfig['videoanalyserpath'] = ffmpegpath
        else:
            ffmpegpath = find_prog_in_PATH("ffmpeg")
            if ffmpegpath is None:
                self.sessconfig['videoanalyserpath'] = "ffmpeg"
            else:
                self.sessconfig['videoanalyserpath'] = ffmpegpath

    
        self.sessconfig['ipv6_binds_v4'] = autodetect_socket_style()
    
    
        # TODO TEMP ARNO: session max vs download max 
        self.sessconfig['max_upload_rate'] = 0
    
        # TEMP TODO
        self.sessconfig['overlay'] = 0
        self.sessconfig['dialback'] = 0


    
    def set_permid(self,keypair):
        self.sessconfig['eckeypair'] = keypair
        
    def set_listen_port(self,port):
        """
        FUTURE: do we allow runtime modification of this param? Theoretically
        possible, a bit hard to implement
        """
        self.sessconfig['minport'] = port
        self.sessconfig['maxport'] = port

    def get_listen_port(self):
        return self.sessconfig['minport']
        
    def set_max_upload(self,speed):
        self.sessconfig['max_upload_rate'] = speed
        
    def set_max_connections(self,nconns):
        self.sessconfig['max_connections'] = nconns

    def get_video_analyser_path(self):
        return self.sessconfig['videoanalyserpath'] # strings immutable
    


class SessionStartupConfig(SessionConfigInterface,Defaultable,Copyable,Serializable):  
    # Defaultable only if Session is not singleton
    
    _default = None
    
    def __init__(self,sessconfig=None):
        SessionConfigInterface.__init__(self,sessconfig)

    #
    # Defaultable interface
    #
    def get_copy_of_default(*args,**kwargs):
        """ Not thread safe """
        if SessionStartupConfig._default is None:
            SessionStartupConfig._default = SessionStartupConfig()
        return SessionStartupConfig._default.copy()
    get_copy_of_default = staticmethod(get_copy_of_default)

    def get_default():
        """ Not thread safe """
        return SessionStartupConfig._default

    def set_default(scfg):
        """ Not thread safe """
        SessionStartupConfig._default = scfg

    #
    # Copyable interface
    # 
    def copy(self):
        config = copy.copy(self.sessconfig)
        return SessionStartupConfig(config)



class Session(Serializable,SessionConfigInterface):
    """
    cf. libtorrent session
    """
    def __init__(self,scfg=None):
        """
        A Session object is created which is configured following a copy of the
        SessionStartupConfig scfg.
        
        in: scfg = SessionStartupConfig object or None, in which case 
        SessionStartupConfig.get_copy_of_default() is called and the returned config
        becomes the bound config of the session.
        
        In the current implementation only a single session instance can exist
        at a time in a process.
        """
        self.sesslock = RLock()
        
        if scfg is None:
            cscfg = SessionStartupConfig.get_copy_of_default()
        else:
            cscfg = scfg
            
        self.sessconfig = copy.copy(cscfg.sessconfig)
        
        # Core init
        resetPeerIDs()
        Tribler.Overlay.permid.init()
        if self.sessconfig['eckeypair'] is None:
            self.sessconfig['eckeypair'] = Tribler.Overlay.permid.generate_keypair()
        
        self.lm = TriblerLaunchMany(self,self.sesslock)
        self.lm.start()
        

    def start_download(self,tdef,dcfg=None):
        """ 
        Creates a Download object and adds it to the session. The passed 
        TorrentDef and DownloadStartupConfig are copied into the new Download object
        and the copies become bound. If the tracker is not set in tdef, it
        is set to the internal tracker (which must have been enabled in the 
        session config)
        
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
    
    def remove_download(self,d):  
        """
        Stops the download and removes it from the session.
        """
        # locking by lm
        self.lm.remove(d)


    def get_internal_tracker_url(self):
        """ Called by any thread """
        ip = self.lm.get_ext_ip() #already thread safe
        port = self.get_listen_port() # already thread safe
        url = 'http://'+ip+':'+str(port)+'/announce/'
        return url
    
    #
    # SessionConfigInterface
    #
    # use these to change the session config at runtime
    #
    def set_permid(self,keypair):
        raise OperationNotPossibleAtRuntime()
        
    def set_listen_port(self,port):
        raise OperationNotPossibleAtRuntime()

    def get_listen_port(self):
        self.sesslock.acquire()
        # To protect self.sessconfig
        ret = SessionConfigInterface.get_listen_port(self)
        self.sesslock.release()
        return ret
        
    def set_max_upload(self,speed):
        # TODO: max per session and per download
        raise NotYetImplementedException()
        
    def set_max_connections(self,nconns):
        # TODO: max per session and per download
        raise NotYetImplementedException()

    def get_video_analyser_path(self):
        self.sesslock.acquire()
        # To protect self.sessconfig
        ret = SessionConfigInterface.get_video_analyser_path(self)
        self.sesslock.release()
        return ret


        

#class TorrentDef(DictMixin,Defaultable,Serializable):
class TorrentDef(Defaultable,Serializable):
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
        
        self.readonly = False
        if config is not None: # copy constructor
            self.config = config
            self.input = input
            self.metainfo = metainfo
            self.infohash = infohash
            return
        
        self.tdefconfig = {}
        self.input = {} # fields added by user, waiting to be turned into torrent file
        self.input['files'] = []
        self.metainfo_valid = False
        self.metainfo = None # copy of loaded or last saved torrent dict
        self.infohash = None # only valid if metainfo_valid
        
        # Define the built-in default here
        for key,val,expl in tdefmetadefaults:
            self.tdefconfig[key] = val

        for key,val,expl in tdefdictdefaults:
            self.input[key] = val
        
        self.input['announce'] = 'bla' # Hmmm... this depends on the default SessionStartupConfig ISSUE


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
        """ Internal class method that reads a torrent file from stream,
        checks it for correctness and sets self.input and self.metainfo
        accordingly """
        bdata = stream.read()
        stream.close()
        data = bdecode(bdata)
        
        validTorrentFile(data) # raises ValueErrors if not good
        
        t = TorrentDef()
        t.metainfo = data
        t.metainfo_valid = True
        t.infohash = sha.sha(bencode(data['info'])).digest()
        # copy stuff into self.input 
        t.input = {}
        t.input['announce'] = t.metainfo['announce']
        # TODO: rest
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
    # Convenience instance methods for publishing new content
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
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()
        
        s = os.stat(filename)
        d = {'fn':filename,'playtime':playtime,'length':s.st_size}
        self.input['files'].append(d)
        self.metainfo_valid = False

    def get_thumbnail(self):
        """
        returns: (MIME type,thumbnail data) if present or (None,None)
        """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        if thumb is None:
            return (None,None)
        else:
            thumb = self.input['thumb'] # buffer/string immutable
            return ('image/jpeg',thumb)
        
        
    def set_thumbnail(self,thumbfilename):
        """
        Reads image from file and turns it into a torrent thumbnail
        
        ISSUE: do we do the image manipulation? If so we need extra libs, 
        perhaps wx to do this. It is more convenient for the API user.
        
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
        

    def get_tracker(self):
        """ Returns 'announce' field """
        return self.input['announce']
        
    def set_tracker(self,url):
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        self.input['announce'] = url 
        
        
    def finalize(self):
        """ Create BT torrent file from input and calculate infohash """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()
        
        if self.metainfo_valid:
            return (self.infohash,self.metainfo)
        else:
            raise NotYetImplementedException()

    #
    # 
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
        Writes torrent file data (i.e., bencoded dict following BT spec)
        in:
        filename = Unicode string
        """
        # TODO: should be possible when bound/readonly
        raise NotYetImplementedException()
        """
            bn = os.path.basename(filename)
            # How to encode Unicode filename? TODO
            
            # When to read file to calc hashes? TODO (could do now and keep pieces in mem until
            # torrent file / bind time. Update: Need to wait until we know piece size.
        """ 
        

    #
    # DictMixin
    #


    #
    # Defaultable interface can be used to things such as default tracker, which
    # end-to-end checksums to include, etc.
    #

    #
    # Copyable interface
    # 
    def copy(self):
        config = copy.copy(self.tdefconfig)
        input = copy.copy(self.input)
        metainfo = copy.copy(self.metainfo)
        infohash = self.infohash
        t = TorrentDef(config,input,metainfo,infohash)
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
        for key,val,expl in dldefaults:
            self.dlconfig[key] = val
       
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

        # TODO: is now sess param, how to set here?
        self.dlconfig['upload_unit_size'] = 1460

    
    def set_max_upload(self,speed):
        """
        ISSUE: How do session maximums and torrent maximums coexist?
        """
        self.dlconfig['max_upload'] = speed


    
class DownloadStartupConfig(DownloadConfigInterface,Defaultable,Serializable):
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
    
    
    def __init__(self,dlconfig=None):
        DownloadConfigInterface.__init__(self,dlconfig)

    #
    # Defaultable interface
    #
    def get_copy_of_default(*args,**kwargs):
        """ Not thread safe """
        if DownloadStartupConfig._default is None:
            DownloadStartupConfig._default = DownloadStartupConfig()
        return DownloadStartupConfig._default.copy()
    get_copy_of_default = staticmethod(get_copy_of_default)

    def get_default():
        """ Not thread safe """
        return DownloadStartupConfig._default

    def set_default(dcfg):
        """ Not thread safe """
        DownloadStartupConfig._default = dcfg

    #
    # Copyable interface
    # 
    def copy(self):
        config = copy.copy(self.dlconfig)
        return DownloadStartupConfig(config)

        
        
class Download(DownloadConfigInterface):
    """
    Representation of a running BT download/upload
    
    cf. libtorrent torrent_handle
    """
    
    #
    # Internal method
    #
    def __init__(self,session,tdef,dcfg=None):
        """
        Create a Download object. Used internally by Session. Copies tdef and 
        dcfg and binds them to this download.
        
        in: 
        tdef = unbound TorrentDef
        dcfg = unbound DownloadStartupConfig or None (in which case DownloadStartupConfig.get_copy_of\
        _default() is called and the result becomes the (bound) config of this
        Download.
        """
        self.cond = Condition()

        self.session = session
        # Copy tdef
        self.tdef = tdef.copy()
        tracker = self.tdef.get_tracker()
        if tracker == '':
            self.tdef.set_tracker(itrackerurl)
        self.tdef.finalize()
        self.tdef.readonly = True
        
        
        # Copy dlconfig, from default if not specified
        if dcfg is None:
            cdcfg = DownloadStartupConfig.get_copy_of_default()
        else:
            cdcfg = dcfg
        self.dlconfig = copy.copy(cdcfg.dlconfig)

        # Set IP to report to tracker. 
        self.dlconfig['ip'] = self.session.lm.get_ext_ip()


    def async_create_engine_wrapper(self,lmcallback):
        """ Called by any thread """
        if DEBUG:
            print >>sys.stderr,"Download: async_create_engine_wrapper()"
        
        # all thread safe
        infohash = self.get_def().get_infohash()
        metainfo = self.get_def().get_metainfo()
        multihandler = self.session.lm.multihandler
        listenport = self.session.get_listen_port()
        vapath = self.session.get_video_analyser_path()

        # Note: BT1Download is started with copy of d.dlconfig, not direct access
        self.cond.acquire()
        kvconfig = copy.copy(self.dlconfig)
        self.cond.release()
        
        func = lambda:self.network_create_engine_wrapper(infohash,metainfo,kvconfig,multihandler,listenport,vapath,lmcallback)
        self.session.lm.rawserver.add_task(func,0) 
        

    def network_create_engine_wrapper(self,infohash,metainfo,kvconfig,multihandler,listenport,vapath,lmcallback):
        """ Called by network thread """
        self.cond.acquire()
        self.sd = SingleDownload(infohash,metainfo,kvconfig,multihandler,listenport,vapath)
        self.cond.release()
        if lmcallback is not None:
            lmcallback(self,self.sd)
        
    #
    # Public methods
    #
    def get_def(self):
        """
        Returns the read-only TorrentDef
        """
        # No lock because attrib immutable and return value protected
        return self.tdef

    
    def get_state(self):
        """ 
        returns: copy of internal download state (so not live pointers into 
        engine)
        """
        return DownloadState()

    def stop(self):
        """ Called by any thread """
        self.cond.acquire()
        try:
            if self.sd is None:
                raise DownloadIsStoppedException()
            self.session.lm.rawserver.add_task(self.network_stop,0)
        finally:
            self.cond.release()
        
        # TODO: async or sync stop?
        
    def restart(self):
        """ Called by any thread """
        self.session.lm.rawserver.add_task(self.network_restart,0)

        # TODO: async or sync start?


    #
    # DownloadConfigInterface
    #
    def set_max_upload(self,speed):
        """ Called by any thread """
        self.cond.acquire()
        try:
            if self.sd is None:
                raise DownloadIsStoppedException()
            DownloadConfigInterface.set_max_upload(self,speed)
        finally:
            self.cond.release()


    #
    # Internal methods
    #

    def network_stop(self):
        """ Called by network thread """
        self.cond.acquire()
        try:
            self.sd.shutdown()
        finally:
            self.cond.release()

    def network_restart(self):
        self.async_create_engine_wrapper(None)

    
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
    just let DownloadState and DownloadStartupConfig return data which e.g.
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
    
    def __init__(self,session,sesslock):
        """ Called only once (unless we have multiple Sessions) """
        Thread.__init__(self)
        self.setDaemon(True)
        self.setName("Network"+self.getName())
        
        self.session = session
        self.sesslock = sesslock
        
        self.downloads = {}
        config = session.sessconfig # Should be safe at startup

        self.locally_guessed_ext_ip = self.guess_ext_ip_locally()
        self.upnp_ext_ip = None
        self.dialback_ext_ip = None

        # Orig
        self.sessdoneflag = Event()
        
        # Following two attributes set/get by network thread
        self.hashcheck_queue = []
        self.sdownloadtohashcheck = None
        
        # Following 2 attributes set/get by UPnPThread
        self.upnp_thread = None
        self.upnp_type = config['upnp_nat_access'] # TODO: use methods to read values?


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
        """ Called by any thread """
        self.sesslock.acquire()
        d = Download(self.session,tdef,dcfg)
        
        d.async_create_engine_wrapper(self.network_engine_wrapper_created_callback)

        # make calling thread wait till network thread created object
        d.cond.acquire()
        d.cond.wait()
        d.cond.release()

        # store in list of Downloads
        self.downloads[d.get_def().get_infohash()] = d
        self.sesslock.release()
        return d

    def network_engine_wrapper_created_callback(self,d,sd):
        """ Called by network thread """
        self.queue_for_hashcheck(sd)

        # wake up creator thread
        d.cond.acquire()
        d.cond.notify()
        d.cond.release()
        
    def remove(self,d):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            d.stop()
            d._cleanup_disk()
            del self.downloads[d.get_def().get_infohash()]
        finally:
            self.sesslock.release()

    def get_downloads(self):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            return self.downloads[:] #copy, is mutable
        finally:
            self.sesslock.release()
    
    def failfunc(self,msg):
        """ Called by multiple threads, TODO determine required locking """
        print >>sys.stderr,"TriblerLaunchMany: failfunc called",msg

    def exceptionfunc(self,e):
        """ Called by multiple threads, TODO determine required locking """
        print >>sys.stderr,"TriblerLaunchmany: exceptfunc called",e


    def run(self):
        """ Called only once """
        try:
            try:
                self.start_upnp()
                self.multihandler.listen_forever()
            except:
                print_exc()    
        finally:
            self.stop_upnp()
            self.rawserver.shutdown()

    def rawserver_keepalive(self):
        """ Hack to prevent rawserver sleeping in select() for a long time, not
        processing any tasks on its queue at startup time 
        
        Called by network thread """
        self.rawserver.add_task(self.rawserver_keepalive,1)

    def guess_ext_ip_locally(self):
        """ Called at creation time """
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
        """ Arno: as the UPnP discovery and calls to the firewall can be slow,
        do it in a separate thread. When it fails, it should report popup
        a dialog to inform and help the user. Or report an error in textmode.
        
        Must save type here, to handle case where user changes the type
        In that case we still need to delete the port mapping using the old mechanism
        
        Called by network thread """ 
        
        print >>sys.stderr,"tlm: start_upnp()"
        self.set_activity(ACT_UPNP)
        self.upnp_thread = UPnPThread(self.upnp_type,self.locally_guessed_ext_ip,self.listen_port,self.upnp_failed_callback,self.upnp_got_ext_ip_callback)
        self.upnp_thread.start()

    def stop_upnp(self):
        """ Called by network thread """
        if self.upnp_type > 0:
            self.upnp_thread.shutdown()

    def upnp_failed_callback(self,upnp_type,listenport,error_type,exc=None,listenproto='TCP'):
        """ Called by UPnP thread TODO: make thread safe"""
        self.failfunc("UPnP mode "+str(upnp_type)+" request to firewall failed with error "+str(error_type)+" Try setting a different mode in Preferences. Listen port was "+str(listenport)+", protocol"+listenproto)

    def upnp_got_ext_ip_callback(self,ip):
        """ Called by UPnP thread TODO: make thread safe"""
        self.sesslock.acquire()
        self.upnp_ext_ip = ip
        self.sesslock.release()

    def dialback_got_ext_ip_callback(self,ip):
        """ Called by network thread """
        self.sesslock.acquire()
        self.dialback_ext_ip = ip
        self.sesslock.release()
        
    def get_ext_ip(self):
        """ Called by any thread """
        self.sesslock.acquire()
        if self.dialback_ext_ip is not None:
            ret = self.dialback_ext_ip # string immutable
        elif self.upnp_ext_ip is not None:
            ret = self.upnp_ext_ip 
        else:
            ret = self.locally_guessed_ext_ip
        self.sesslock.release()
        return ret

    def set_activity(self,type):
        pass # TODO


    def queue_for_hashcheck(self,sd):
        """ Schedule a SingleDownload for integrity check of on-disk data
        
        Called by network thread """
        if hash:
            self.hashcheck_queue.append(sd)
            # Check smallest torrents first
            self.hashcheck_queue.sort(lambda x, y: cmp(self.downloads[x].dow.datalength, self.downloads[y].dow.datalength))
        if not self.sdownloadtohashcheck:
            self.dequeue_and_start_hashcheck()

    def dequeue_and_start_hashcheck(self):
        """ Start integriy check for first SingleDownload in queue
        
        Called by network thread """
        self.sdownloadtohashcheck = self.hashcheck_queue.pop(0)
        self.sdownloadtohashcheck.perform_hashcheck(self.hashcheck_done)

    def hashcheck_done(self):
        """ Integrity check for first SingleDownload in queue done
        
        Called by network thread """
        self.sdownloadtohashcheck.hashcheck_done()
        if self.hashcheck_queue:
            self.dequeue_and_start_hashcheck()
        else:
            self.sdownloadtohashcheck = None



class SingleDownload:
    """ This class is accessed solely by the network thread """
    
    def __init__(self,infohash,metainfo,kvconfig,multihandler,listenport,videoanalyserpath):
        self.restart(infohash,metainfo,kvconfig,multihandler,listenport,videoanalyserpath)
        
    def restart(self,infohash,metainfo,kvconfig,multihandler,listenport,videoanalyserpath):
        self.dldoneflag = Event()
        
        # MUST NOT BE DONE MY ANY THREAD!
        self.rawserver = multihandler.newRawServer(infohash,self.dldoneflag)

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
                        listenport,
                        #config['vod'], Arno: read from kvconfig
                        [],    # TODO: how to set which video in a multi-video torrent to play
                        #None, # = progressinf: now via DownloadState
                        videoanalyserpath
                        # TODO: dht
                        )
    
        if not self.dow.saveAs(self.save_as):
            # TODO: let saveAs throw exceptions
            return
        self._hashcheckfunc = self.dow.initFiles()
        if not self._hashcheckfunc:
            self.shutdown()
            return
    
    def save_as(self,name,length,saveas,isdir):
        """ Return the local filename to which to save the file 'name' in the torrent """
        print >>sys.stderr,"Download: save_as(",name,length,saveas,isdir,")"
        path = os.path.join(saveas,name)
        if isdir and not os.path.isdir(path):
            os.mkdir(path)
        return path

    def perform_hashcheck(self,complete_callback):
        """ Called by any thread """
        print >>sys.stderr,"Download: hashcheck()",self._hashcheckfunc
        """ Schedules actually hashcheck on network thread """
        self._hashcheckfunc(complete_callback)
    
    def hashcheck_done(self):
        """ Called by LaunchMany when hashcheck complete and the Download can be
            resumed
            
            Called by network thread
        """
        print >>sys.stderr,"Download: hashcheck_done()"
        if not self.dow.startEngine():
            print >>sys.stderr,"Download: hashcheck_complete: startEngine failed"
            return

        self.dow.startRerequester()
        self.rawserver.start_listening(self.dow.getPortHandler())


    # DownloadConfigInterface methods
    def set_max_upload(self,speed):
        if self.dow is None:
            raise DownloadIsStopped()
        
        self.dow.setUploadRate(speed)


    #
    #
    #
    def shutdown(self):
        if self.dow is not None:
            self.dldoneflag.set()
            self.rawserver.shutdown()
            self.dow.shutdown()
            self.dow = None

    #
    # Internal methods
    #
    def _statusfunc(self,activity = '', fractionDone = 0.0):
        print >>sys.stderr,"SingleDownload::_statusfunc called",activity,fractionDone

    def _finishedfunc(self):
        print >>sys.stderr,"SingleDownload::_finishedfunc called"

    def _errorfunc(self,msg):
        print >>sys.stderr,"SingleDownload::_errorfunc called",msg

    def _exceptionfunc(self,e):
        print >>sys.stderr,"SingleDownload::_exceptfunc called",e





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

    def __init__(self,upnp_type,ext_ip,listen_port,error_func,got_ext_ip_func):
        Thread.__init__(self)
        self.setDaemon(True)
        self.setName( "UPnP"+self.getName() )
        
        self.upnp_type = upnp_type
        self.locally_guessed_ext_ip = ext_ip
        self.listen_port = listen_port
        self.error_func = error_func
        self.got_ext_ip_func = got_ext_ip_func 
        self.shutdownevent = Event()

    def run(self):
        if self.upnp_type > 0:
            self.upnp_wrap = UPnPWrapper.getInstance()
            self.upnp_wrap.register(self.locally_guessed_ext_ip)

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
                            self.got_ext_ip_func(ret)

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

    def shutdown(self):
        self.shutdownevent.set()




if __name__ == "__main__":
    
    s = Session()
    
    tdef = TorrentDef.load('/tmp/bla.torrent')
    
    print >>sys.stderr,"main: TorrentDef is",tdef
    d = s.start_download(tdef)
    d.set_max_upload(100)
    while True:
        print d.get_state().get_progress()
        time.sleep(5)

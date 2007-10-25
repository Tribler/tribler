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
    
def vod_ready_callback(mimetype,stream):
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

- Allow VOD when first part of file hashchecked.

- Is there a state where the file complete but not yet in order on disk?

- Reimplement selected_files with existing 'priority' field

- set/get for all config params

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

"""

import sys
import os
import time
import copy
import sha
import socket
import pickle
import binascii
import shutil
from UserDict import DictMixin
from threading import RLock,Condition,Event,Thread,currentThread
from traceback import print_exc,print_stack
from types import StringType

from BitTornado.__init__ import resetPeerIDs,createPeerID
from BitTornado.RawServer import autodetect_socket_style
from BitTornado.bencode import bencode,bdecode
from BitTornado.download_bt1 import BT1Download
from BitTornado.RawServer import RawServer
from BitTornado.ServerPortHandler import MultiHandler
from BitTornado.RateLimiter import RateLimiter
from BitTornado.BT1.track import Tracker
from BitTornado.HTTPHandler import HTTPHandler,DummyHTTPHandler

import Tribler.Overlay.permid
from Tribler.NATFirewall.guessip import get_my_wan_ip
from Tribler.NATFirewall.UPnPThread import UPnPThread
from Tribler.utilities import find_prog_in_PATH,validTorrentFile
from Tribler.Overlay.SecureOverlay import SecureOverlay
from Tribler.Overlay.OverlayApps import OverlayApps
from Tribler.NATFirewall.DialbackMsgHandler import DialbackMsgHandler
from Tribler.DecentralizedTracking import mainlineDHT
from Tribler.DecentralizedTracking.rsconvert import RawServerConverter
from Tribler.unicode import metainfoname2unicode
from Tribler.API.defaults import *
from Tribler.API.osutils import *
from Tribler.API.miscutils import *


SPECIAL_VALUE=481
from Tribler.API.simpledefs import *


# TEMP
from Tribler.Dialogs.activities import *

DEBUG = True


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



# Exceptions
#
class TriblerException(Exception):
    
    def __init__(self,msg=None):
        Exception.__init__(self,msg)

    def __str__(self):
        return str(self.__class__)+': '+Exception.__str__(self)
 

class OperationNotPossibleAtRuntimeException(TriblerException):
    
    def __init__(self,msg=None):
        TriblerException.__init__(self,msg)
    
class NotYetImplementedException(TriblerException):
    
    def __init__(self,msg=None):
        TriblerException.__init__(self,msg)


class DownloadIsStoppedException(TriblerException):
    
    def __init__(self,msg=None):
        TriblerException.__init__(self,msg)


class TriblerLegacyException(TriblerException):
    """ Wrapper around fatal errors that happen in the download engine,
    but which are not reported as Exception objects for legacy reasons,
    just as text (often containing a stringified Exception).
    Will be phased out.
    """
    
    def __init__(self,msg=None):
        TriblerException.__init__(self,msg)
    

#
# API classes
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
        for key,val,expl in sessdefaults:
            self.sessconfig[key] = val
        
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
    
    def set_permid(self,keypairfilename):
        self.sessconfig['eckeypairfilename'] = keypairfilename
        
    def set_listen_port(self,port):
        """
        FUTURE: do we allow runtime modification of this param? Theoretically
        possible, a bit hard to implement
        """
        self.sessconfig['minport'] = port
        self.sessconfig['maxport'] = port

    def get_listen_port(self):
        return self.sessconfig['minport']
        
    def get_video_analyser_path(self):
        return self.sessconfig['videoanalyserpath'] # strings immutable
    


class SessionStartupConfig(SessionConfigInterface,Copyable,Serializable):  
    # Defaultable only if Session is not singleton
    
    def __init__(self,sessconfig=None):
        SessionConfigInterface.__init__(self,sessconfig)

    #
    # Copyable interface
    # 
    def copy(self):
        config = copy.copy(self.sessconfig)
        return SessionStartupConfig(config)



class Session(SessionConfigInterface):
    """
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
        self.threadcount=1

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

        # Create engine with network thread
        self.lm = TriblerLaunchMany(self,self.sesslock)
        self.lm.start()

        # Restart Downloads from checkpoint, if any
        self.lm.load_checkpoint()

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
    def start_download(self,tdef,dcfg=None):
        """ 
        Creates a Download object and adds it to the session. The passed 
        TorrentDef and DownloadStartupConfig are copied into the new Download 
        object and the copies become bound. If the tracker is not set in tdef, 
        it is set to the internal tracker (which must have been enabled in the 
        session config). The Download is then started and checkpointed.
        
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
    # SessionConfigInterface
    #
    # Use these to change the session config at runtime.
    #
    def set_state_dir(self,statedir):
        raise OperationNotPossibleAtRuntimeExeption()
    
    def get_state_dir(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_state_dir(self)
        finally:
            self.sesslock.release()
    
    def set_permid(self,keypair):
        raise OperationNotPossibleAtRuntimeExeption()
        
    def set_listen_port(self,port):
        raise OperationNotPossibleAtRuntimeExeption()

    def get_listen_port(self):
        # To protect self.sessconfig
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_listen_port(self)
        finally:
            self.sesslock.release()
        
    def get_video_analyser_path(self):
        # To protect self.sessconfig
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_video_analyser_path(self)
        finally:
            self.sesslock.release()

    #
    # Internal methods
    #
    def perform_vod_usercallback(self,usercallback,mimetype,stream):
        """ Called by network thread """
        print >>sys.stderr,"Session: perform_vod_usercallback()"
        def session_vod_usercallback_target():
            try:
                usercallback(mimetype,stream)
            except:
                print_exc()
        self.perform_usercallback(session_vod_usercallback_target)

    def perform_getstate_usercallback(self,usercallback,data,returncallback):
        """ Called by network thread """
        print >>sys.stderr,"Session: perform_getstate_usercallback()"
        def session_getstate_usercallback_target():
            try:
                (when,getpeerlist) = usercallback(data)
                returncallback(usercallback,when,getpeerlist)
            except:
                print_exc()
        self.perform_usercallback(session_getstate_usercallback_target)


    def perform_removestate_callback(self,infohash,correctedinfoname,removecontent,dldestdir):
        """ Called by network thread """
        print >>sys.stderr,"Session: perform_removestate_callback()"
        def session_removestate_callback_target():
            print >>sys.stderr,"Session: session_removestate_callback_target called",currentThread().getName()
            try:
                self.sesscb_removestate(infohash,correctedinfoname,removecontent,dldestdir)
            except:
                print_exc()
        self.perform_usercallback(session_removestate_callback_target)
        
        
    def perform_usercallback(self,target):
        self.sesslock.acquire()
        try:
            # TODO: thread pool, etc.
            name = "SessionCallbackThread-"+str(self.threadcount)
            self.threadcount += 1
            t = Thread(target=target,name=name)
            t.setDaemon(True)
            t.start()
        finally:
            self.sesslock.release()


    def sesscb_removestate(self,infohash,correctedinfoname,removecontent,dldestdir):
        """ Called by SessionCallbackThread """
        print >>sys.stderr,"Session: sesscb_removestate called",`infohash`,`correctedinfoname`,removecontent,dldestdir
        self.sesslock.acquire()
        try:
            dlpstatedir = os.path.join(self.sessconfig['state_dir'],STATEDIR_DLPSTATE_DIR)
            trackerdir = os.path.join(self.sessconfig['state_dir'],STATEDIR_ITRACKER_DIR)
        finally:
            self.sesslock.release()

        # See if torrent uses internal tracker
        hexinfohash = binascii.hexlify(infohash)
        try:
            basename = hexinfohash+'.torrent'
            filename = os.path.join(trackerdir,basename)
            print >>sys.stderr,"Session: sesscb_removestate: removing itracker entry",filename
            if os.access(filename,os.F_OK):
                os.remove(filename)
        except:
            # Show must go on
            print_exc()

        # Remove checkpoint
        try:
            basename = hexinfohash+'.pickle'
            filename = os.path.join(dlpstatedir,basename)
            print >>sys.stderr,"Session: sesscb_removestate: removing dlcheckpoint entry",filename
            if os.access(filename,os.F_OK):
                os.remove(filename)
        except:
            # Show must go on
            print_exc()

        # Remove downloaded content from disk
        if removecontent:
            filename = os.path.join(dldestdir,correctedinfoname)
            print >>sys.stderr,"Session: sesscb_removestate: removing saved content",filename
            if not os.path.isdir(filename):
                # single-file torrent
                os.remove(filename)
            else:
                # multi-file torrent
                shutil.rmtree(filename,True) # ignore errors

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
    def __init__(self,config=None,input=None,metainfo=None,infohash=None):
        """ Normal constructor for TorrentDef (copy constructor used internally) """
        
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
        """ Returns the bitrate of the specified file in bytes/sec """ 
        if not self.metainfo_valid:
            raise NotYetImplementedException() # must save first

        info = self.metainfo['info']
        if file is None:
            bitrate = None
            try:
                playtime = None
                if info.has_key('playtime'):
                    playtime = parse_playtime_to_secs(info['playtime'])
                elif 'playtime' in self.metainfo: # HACK: encode playtime in non-info part of existing torrent
                    playtime = parse_playtime_to_secs(self.metainfo['playtime'])
                """
                elif 'azureus_properties' in metainfo:
                    if 'Speed Bps' in metainfo['azureus_properties']:
                        bitrate = float(metainfo['azureus_properties']['Speed Bps'])/8.0
                        playtime = file_length / bitrate
                """
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

        
        
class Download(DownloadConfigInterface):
    """
    Representation of a running BT download/upload
    
    cf. libtorrent torrent_handle
    """
    
    #
    # Internal methods
    #
    def __init__(self):
        self.dllock = RLock()
        # just enough so error saving and get_state() works
        self.error = None
        self.sd = None # hack
        # To be able to return the progress of a stopped torrent, how far it got.
        self.progressbeforestop = 0.0
        self.filepieceranges = []
    
    def setup(self,session,tdef,dcfg=None,pstate=None,lmcallback=None):
        """
        Create a Download object. Used internally by Session. Copies tdef and 
        dcfg and binds them to this download.
        
        in: 
        tdef = unbound TorrentDef
        dcfg = unbound DownloadStartupConfig or None (in which case 
        DownloadStartupConfig.get_copy_of_default() is called and the result 
        becomes the (bound) config of this Download.
        """
        try:
            self.dllock.acquire() # not really needed, no other threads know of it
            self.session = session
            
            # Copy tdef
            self.tdef = tdef.copy()
            tracker = self.tdef.get_tracker()
            itrackerurl = self.session.get_internal_tracker_url()
            if tracker == '':
                self.tdef.set_tracker(itrackerurl)
            self.tdef.finalize()
            self.tdef.readonly = True
            
            # See if internal tracker used
            infohash = self.tdef.get_infohash()
            metainfo = self.tdef.get_metainfo()
            usingitracker = False
            if metainfo['announce'] == itrackerurl:
                usingitracker = True
            elif 'announce-list' in metainfo:
                for tier in metainfo['announce-list']:
                    if itrackerurl in tier:
                         usingitracker = True
                         break
                     
            if usingitracker:
                # Copy .torrent to state_dir/itracker so the tracker thread 
                # finds it and accepts peer registrations for it.
                # 
                trackerdir = os.path.join(self.sessconfig['state_dir'],STATEDIR_ITRACKER_DIR)
                basename = binascii.hexlify(infohash)+'.torrent' # ignore .tribe stuff, not vital
                filename = os.path.join(trackerdir,basename)
                self.tdef.save(filename)
                # Bring to attention of Tracker thread
                session.lm.tracker_rescan_dir()
            
            # Copy dlconfig, from default if not specified
            if dcfg is None:
                cdcfg = DownloadStartupConfig.get_copy_of_default()
            else:
                cdcfg = dcfg
            self.dlconfig = copy.copy(cdcfg.dlconfig)
    
            # TODO: copy sessconfig into dlconfig?
    
    
            self.set_filepieceranges()
    
            # Things that only exist at runtime
            self.dlruntimeconfig= {}
            # We want to remember the desired rates and the actual assigned quota
            # rates by the RateManager
            self.dlruntimeconfig['max_desired_upload_rate'] = self.dlconfig['max_upload_rate'] 
            self.dlruntimeconfig['max_desired_download_rate'] = self.dlconfig['max_download_rate']
    
    
            print >>sys.stderr,"Download: setup: get_max_desired",self.dlruntimeconfig['max_desired_upload_rate']

            if pstate is None or pstate['dlstate']['status'] != DLSTATUS_STOPPED:
                # Also restart on STOPPED_ON_ERROR, may have been transient
                self.create_engine_wrapper(lmcallback,pstate)
                
            self.dllock.release()
        except Exception,e:
            print_exc()
            self.set_error(e)
            self.dllock.release()

    def create_engine_wrapper(self,lmcallback,pstate):
        """ Called by any thread, assume dllock already acquired """
        if DEBUG:
            print >>sys.stderr,"Download: create_engine_wrapper()"
        
        # all thread safe
        infohash = self.get_def().get_infohash()
        metainfo = copy.deepcopy(self.get_def().get_metainfo())
        
        # H4xor this so the 'name' field is safe
        namekey = metainfoname2unicode(metainfo)
        self.correctedinfoname = fix_filebasename(metainfo['info'][namekey])
        metainfo['info'][namekey] = metainfo['info']['name'] = self.correctedinfoname 
        
        multihandler = self.session.lm.multihandler
        listenport = self.session.get_listen_port()
        vapath = self.session.get_video_analyser_path()

        # Note: BT1Download is started with copy of d.dlconfig, not direct access
        # Set IP to report to tracker. 
        self.dlconfig['ip'] = self.session.lm.get_ext_ip()
        kvconfig = copy.copy(self.dlconfig)

        # Define which file to DL in VOD mode
        if self.dlconfig['mode'] == DLMODE_VOD:
            vod_usercallback_wrapper = lambda mimetype,stream:self.session.perform_vod_usercallback(self.dlconfig['vod_usercallback'],mimetype,stream)
            if len(self.dlconfig['selected_files']) == 0:
                # single-file torrent
                file = self.get_def().get_name()
                idx = -1
                bitrate = self.get_def().get_bitrate(None)
            else:
                # multi-file torrent
                file = self.dlconfig['selected_files'][0]
                idx = self.get_def().get_index_of_file_in_files(file)
                bitrate = self.get_def().get_bitrate(file)
            vodfileindex = [idx,file,bitrate,None,vod_usercallback_wrapper]
        else:
            vodfileindex = [-1,None,0.0,None,None]
        
        # Delegate creation of engine wrapper to network thread
        network_create_engine_wrapper_lambda = lambda:self.network_create_engine_wrapper(infohash,metainfo,kvconfig,multihandler,listenport,vapath,vodfileindex,lmcallback,pstate)
        self.session.lm.rawserver.add_task(network_create_engine_wrapper_lambda,0) 
        

    def network_create_engine_wrapper(self,infohash,metainfo,kvconfig,multihandler,listenport,vapath,vodfileindex,lmcallback,pstate):
        """ Called by network thread """
        self.dllock.acquire()
        try:
            self.sd = SingleDownload(infohash,metainfo,kvconfig,multihandler,listenport,vapath,vodfileindex,self.set_error,pstate)
            sd = self.sd
            exc = self.error
            if lmcallback is not None:
                lmcallback(self,sd,exc,pstate)
        finally:
            self.dllock.release()


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
    # DownloadConfigInterface
    #
    def set_max_speed(self,direct,speed):
        """ Called by any thread """
        
        print >>sys.stderr,"Download: set_max_speed",`self.get_def().get_metainfo()['info']['name']`,direct,speed
        #print_stack()
        
        self.dllock.acquire()
        try:
            # Don't need to throw an exception when stopped, we then just save the new value and
            # use it at (re)startup.
            if self.sd is not None:
                set_max_speed_lambda = lambda:self.sd.set_max_speed(direct,speed,self.network_set_max_speed)
                self.session.lm.rawserver.add_task(set_max_speed_lambda,0)
            else:
                DownloadConfigInterface.set_max_speed(self,direct,speed)
        finally:
            self.dllock.release()

    def get_max_speed(self,direct):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_max_speed(self,direct)
        finally:
            self.dllock.release()

    def set_saveas(self,path):
        raise OperationNotPossibleAtRuntimeException()

    def set_video_on_demand(self,usercallback):
        raise NotYetImplementedException()

    def set_selected_files(self,files):
        raise NotYetImplementedException()


    #
    # Runtime Config 
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


    #
    # Internal methods
    #
    def set_error(self,e):
        self.dllock.acquire()
        self.error = e
        self.dllock.release()


    def set_filepieceranges(self):
        """ Determine which file maps to which piece ranges for progress info """
        
        print >>sys.stderr,"Download: set_filepieceranges:",self.dlconfig['selected_files']
        
        if len(self.dlconfig['selected_files']) > 0:
            if 'files' not in self.tdef.metainfo['info']:
                raise ValueError("Selected more than 1 file, but torrent is single-file torrent")
            
            files = self.tdef.metainfo['info']['files']
            piecesize = self.tdef.metainfo['info']['piece length']
            
            total = 0L
            for i in xrange(len(files)):
                path = files[i]['path']
                length = files[i]['length']
                filename = pathlist2filename(path)
                
                print >>sys.stderr,"Download: set_filepieceranges: Torrent file",filename,"in",self.dlconfig['selected_files']

                if filename in self.dlconfig['selected_files'] and length > 0:
                    
                    range = (offset2piece(total,piecesize), offset2piece(total + length,piecesize),filename)
                    
                    print >>sys.stderr,"Download: set_filepieceranges: Torrent file range append",range
                    
                    self.filepieceranges.append(range)
                total += length
        else:
            self.filepieceranges = None 


    def stop_remove(self,removestate=False,removecontent=False):
        self.dllock.acquire()
        try:
            if self.sd is not None:
                network_stop_lambda = lambda:self.network_stop(removestate,removecontent)
                self.session.lm.rawserver.add_task(network_stop_lambda,0.0)
            # No exception if already stopped, for convenience
        finally:
            self.dllock.release()


    def network_get_state(self,usercallback,getpeerlist,sessioncalling=False):
        """ Called by network thread """
        self.dllock.acquire()
        try:
            if self.sd is None:
                ds = DownloadState(self,DLSTATUS_STOPPED,self.error,self.progressbeforestop)
            else:
                (status,stats) = self.sd.get_stats(getpeerlist)
                ds = DownloadState(self,status,self.error,None,stats=stats,filepieceranges=self.filepieceranges)
                self.progressbeforestop = ds.get_progress()
            
                #print >>sys.stderr,"STATS",stats
            
            if sessioncalling:
                return ds

            # Invoke the usercallback function via a new thread.
            # After the callback is invoked, the return values will be passed to
            # the returncallback for post-callback processing.
            self.session.perform_getstate_usercallback(usercallback,ds,self.sesscb_get_state_returncallback)
        finally:
            self.dllock.release()


    def sesscb_get_state_returncallback(self,usercallback,when,newgetpeerlist):
        """ Called by SessionCallbackThread """
        self.dllock.acquire()
        try:
            if when > 0.0:
                # Schedule next invocation, either on general or DL specific
                # TODO: ensure this continues when dl is stopped. Should be OK.
                network_get_state_lambda = lambda:self.network_get_state(usercallback,newgetpeerlist)
                if self.sd is None:
                    self.session.lm.rawserver.add_task(network_get_state_lambda,when)
                else:
                    self.sd.dlrawserver.add_task(network_get_state_lambda,when)
        finally:
            self.dllock.release()

    def network_stop(self,removestate,removecontent):
        """ Called by network thread """
        self.dllock.acquire()
        try:
            infohash = self.tdef.get_infohash() 
            pstate = self.network_get_persistent_state() 
            pstate['engineresumedata'] = self.sd.shutdown()
            
            # Offload the removal of the content and other disk cleanup to another thread
            if removestate:
                self.session.perform_removestate_callback(infohash,self.correctedinfoname,removecontent,self.dlconfig['saveas'])
            
            return (infohash,pstate)
        finally:
            self.dllock.release()


    def network_checkpoint(self):
        """ Called by network thread """
        self.dllock.acquire()
        try:
            pstate = self.network_get_persistent_state() 
            pstate['engineresumedata'] = self.sd.checkpoint()
            return (self.tdef.get_infohash(),pstate)
        finally:
            self.dllock.release()
        

    def network_get_persistent_state(self):
        """ Assume dllock already held """
        pstate = {}
        pstate['version'] = PERSISTENTSTATE_CURRENTVERSION
        pstate['metainfo'] = self.tdef.get_metainfo() # assumed immutable
        dlconfig = copy.copy(self.dlconfig)
        # Reset unpicklable params
        dlconfig['vod_usercallback'] = None
        dlconfig['dlmode'] = DLMODE_NORMAL # no callback, no VOD
        pstate['dscfg'] = DownloadStartupConfig(dlconfig=dlconfig)

        pstate['dlstate'] = {}
        ds = self.network_get_state(None,False,sessioncalling=True)
        pstate['dlstate']['status'] = ds.get_status()
        pstate['dlstate']['progress'] = ds.get_progress()
        
        print >>sys.stderr,"Download: netw_get_pers_state: status",dlstatus_strings[ds.get_status()],"progress",ds.get_progress()
        
        pstate['engineresumedata'] = None
        return pstate

    def network_set_max_speed(self,direct,speed):
        """ Called by network thread """
        self.dllock.acquire()
        try:
            DownloadConfigInterface.set_max_speed(self,direct,speed)
        finally:
            self.dllock.release()
        

    
class DownloadState(Serializable):
    """
    Contains a snapshot of the state of the Download at a specific
    point in time. Using a snapshot instead of providing live data and 
    protecting access via locking should be faster.
    
    cf. libtorrent torrent_status
    """
    def __init__(self,download,status,error,progress,stats=None,filepieceranges=None):
        self.download = download
        self.filepieceranges = filepieceranges # NEED CONC CONTROL IF selected_files RUNTIME SETABLE
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


#
# Internal classes
#

class TriblerLaunchMany(Thread):
    
    def __init__(self,session,sesslock):
        """ Called only once (unless we have multiple Sessions) """
        Thread.__init__(self)
        self.setDaemon(True)
        self.setName("Network"+self.getName())
        
        self.session = session
        self.sesslock = sesslock
        
        self.downloads = []
        config = session.sessconfig # Should be safe at startup

        self.locally_guessed_ext_ip = self.guess_ext_ip_from_local_info()
        self.upnp_ext_ip = None
        self.dialback_ext_ip = None

        # Orig
        self.sessdoneflag = Event()
        
        # Following two attributes set/get by network thread
        self.hashcheck_queue = []
        self.sdownloadtohashcheck = None
        
        # Following 2 attributes set/get by UPnPThread
        self.upnp_thread = None
        self.upnp_type = config['upnp_nat_access']


        self.rawserver = RawServer(self.sessdoneflag,
                                   config['timeout_check_interval'],
                                   config['timeout'],
                                   ipv6_enable = config['ipv6_enabled'],
                                   failfunc = self.rawserver_fatalerrorfunc,
                                   errorfunc = self.rawserver_nonfatalerrorfunc)
        self.rawserver.add_task(self.rawserver_keepalive,1)
        
        self.listen_port = self.rawserver.find_and_bind(0, 
                    config['minport'], config['maxport'], config['bind'], 
                    reuse = True,
                    ipv6_socket_style = config['ipv6_binds_v4'], 
                    randomizer = config['random_port'])
        print "Got listen port", self.listen_port
        
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
            mykeypair = session.keypair
            self.secure_overlay.register(self.rawserver,self.multihandler,self.listen_port,self.config['max_message_length'],mykeypair)
            self.overlay_apps = OverlayApps.getInstance()
            self.overlay_apps.register(self.secure_overlay, self, self.rawserver, config)
            # It's important we don't start listening to the network until
            # all higher protocol-handling layers are properly configured.
            self.secure_overlay.start_listening()
        
        self.internaltracker = None
        if config['internaltracker']:
            self.internaltracker = Tracker(config, self.rawserver)
            self.httphandler = HTTPHandler(self.internaltracker.get, config['tracker_min_time_between_log_flushes'])
        else:
            self.httphandler = DummyHTTPHandler()
        self.multihandler.set_httphandler(self.httphandler)
        
        
        # Start up mainline DHT
        # Arno: do this in a try block, as khashmir gives a very funky
        # error when started from a .dmg (not from cmd line) on Mac. In particular
        # it complains that it cannot find the 'hex' encoding method when
        # hstr.encode('hex') is called, and hstr is a string?!
        #
        try:
            rsconvert = RawServerConverter(self.rawserver)
            # '' = host, TODO: when local bind set
            mainlineDHT.init('',self.listen_port,config['state_dir'],rawserver=rsconvert)
        except:
            print_exc()
        
        
        # APITODO
        #self.torrent_db = TorrentDBHandler()
        #self.mypref_db = MyPreferenceDBHandler()
        
        # add task for tracker checking
        if not config['torrent_checking']:
            self.rawserver.add_task(self.torrent_checking, self.torrent_checking_period)
        

    def add(self,tdef,dcfg,pstate=None):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            d = Download()
            # store in list of Downloads, always. 
            self.downloads.append(d)
            d.setup(self.session,tdef,dcfg,pstate,self.network_engine_wrapper_created_callback)
            return d
        finally:
            self.sesslock.release()


    def network_engine_wrapper_created_callback(self,d,sd,exc,pstate):
        """ Called by network thread """
        if exc is None:
            # Always need to call the hashcheck func, even if we're restarting
            # a download that was seeding, this is just how the BT engine works
            # We've provided the BT engine with its resumedata, so this should
            # be fast.
            #
            self.queue_for_hashcheck(sd)
            if pstate is None:
                # Checkpoint at startup
                (infohash,pstate) = d.network_checkpoint()
                self.save_download_pstate(infohash,pstate)
        
    def remove(self,d,removecontent=False):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            d.stop_remove(removestate=True,removecontent=removecontent)
            self.downloads.remove(d)
        finally:
            self.sesslock.release()

    def get_downloads(self):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            return self.downloads[:] #copy, is mutable
        finally:
            self.sesslock.release()
    
    def rawserver_fatalerrorfunc(self,e):
        """ Called by network thread """
        if DEBUG:
            print >>sys.stderr,"TriblerLaunchMany: RawServer fatal error func called",e
        print_exc

    def rawserver_nonfatalerrorfunc(self,e):
        """ Called by network thread """
        if DEBUG:
            print >>sys.stderr,"TriblerLaunchmany: RawServer non fatal error func called",e
            print_exc()
        # Could log this somewhere, or phase it out

    def run(self):
        """ Called only once by network thread """
        try:
            try:
                self.start_upnp()
                self.multihandler.listen_forever()
            except:
                print_exc()    
        finally:
            if self.internaltracker is not None:
                self.internaltracker.save_state()
            
            self.stop_upnp()
            self.rawserver.shutdown()

    def rawserver_keepalive(self):
        """ Hack to prevent rawserver sleeping in select() for a long time, not
        processing any tasks on its queue at startup time 
        
        Called by network thread """
        self.rawserver.add_task(self.rawserver_keepalive,1)

    #
    # TODO: called by TorrentMaker when new torrent added to itracker dir
    # Make it such that when Session.add_torrent() is called and the internal
    # tracker is used that we write a metainfo to itracker dir and call this.
    #
    def tracker_rescan_dir(self):
        if self.internaltracker is not None:
            self.internaltracker.parse_allowed(source='TorrentMaker')

    def set_activity(self,type):
        pass # TODO Jelle

    #
    # Torrent hash checking
    #
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


    #
    # State retrieval
    #
    def set_download_states_callback(self,usercallback,getpeerlist,when=0.0):
        """ Called by any thread """
        network_set_download_states_callback_lambda = lambda:self.network_set_download_states_callback(usercallback,getpeerlist)
        self.rawserver.add_task(network_set_download_states_callback_lambda,when)
        
    def network_set_download_states_callback(self,usercallback,getpeerlist):
        """ Called by network thread """
        self.sesslock.acquire()
        try:
            # Even if the list of Downloads changes in the mean time this is
            # no problem. For removals, dllist will still hold a pointer to the
            # Download, and additions are no problem (just won't be included 
            # in list of states returned via callback.
            #
            dllist = self.downloads[:]
        finally:
            self.sesslock.release()

        dslist = []
        for d in dllist:
            ds = d.network_get_state(None,getpeerlist,sessioncalling=True)
            dslist.append(ds)
            
        # Invoke the usercallback function via a new thread.
        # After the callback is invoked, the return values will be passed to
        # the returncallback for post-callback processing.
        self.session.perform_getstate_usercallback(usercallback,dslist,self.sesscb_set_download_states_returncallback)
        
    def sesscb_set_download_states_returncallback(self,usercallback,when,newgetpeerlist):
        """ Called by SessionCallbackThread """
        if when > 0.0:
            # reschedule
            self.set_download_states_callback(usercallback,newgetpeerlist,when=when)

    #
    # Persistence methods
    #
    def load_checkpoint(self):
        """ Called by any thread """
        dir = self.session.get_downloads_pstate_dir()
        filelist = os.listdir(dir)
        for basename in filelist:
            # Make this go on when a torrent fails to start
            try:
                filename = os.path.join(dir,basename)
                pstate = self.load_download_pstate(filename)
                
                print >>sys.stderr,"tlm: load_checkpoint: pstate is",dlstatus_strings[pstate['dlstate']['status']],pstate['dlstate']['progress']
                tdef = TorrentDef._create(pstate['metainfo'])
                
                # Resume download
                self.add(tdef,pstate['dscfg'],pstate)
            except Exception,e:
                self.rawserver_nonfatalerrorfunc(e)

    
    def checkpoint(self,stop=False):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            # Even if the list of Downloads changes in the mean time this is
            # no problem. For removals, dllist will still hold a pointer to the
            # Download, and additions are no problem (just won't be included 
            # in list of states returned via callback.
            #
            dllist = self.downloads[:]
            print >>sys.stderr,"tlm: checkpointing",len(dllist)
            
            network_checkpoint_callback_lambda = lambda:self.network_checkpoint_callback(dllist,stop)
            self.rawserver.add_task(network_checkpoint_callback_lambda,0.0)
        finally:
            self.sesslock.release()
        
    def network_checkpoint_callback(self,dllist,stop):
        """ Called by network thread """
        psdict = {'version':PERSISTENTSTATE_CURRENTVERSION}
        for d in dllist:
            # Tell all downloads to stop, and save their persistent state
            # in a infohash -> pstate dict which is then passed to the user
            # for storage.
            #
            print >>sys.stderr,"tlm: network checkpointing:",`d.get_def().get_name()`
            if stop:
                (infohash,pstate) = d.network_stop(False,False)
            else:
                (infohash,pstate) = d.network_checkpoint()
            psdict[infohash] = pstate

        try:
            for infohash,pstate in psdict.iteritems():
                self.save_download_pstate(infohash,pstate)
        except Exception,e:
            self.rawserver_nonfatalerrorfunc(e)

        if stop:
            # Stop network thread
            self.sessdoneflag.set()


    def save_download_pstate(self,infohash,pstate):
        """ Called by network thread """
        basename = binascii.hexlify(infohash)+'.pickle'
        filename = os.path.join(self.session.get_downloads_pstate_dir(),basename)
        
        print >>sys.stderr,"tlm: network checkpointing: to file",filename
        f = open(filename,"wb")
        pickle.dump(pstate,f)
        f.close()


    def load_download_pstate(self,filename):
        """ Called by any thread """
        f = open(filename,"rb")
        pstate = pickle.load(f)
        f.close()
        return pstate

    #
    # External IP address methods
    #
    def guess_ext_ip_from_local_info(self):
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
        """ Called by UPnP thread TODO: determine how to pass to API user 
            In principle this is a non fatal error. But it is one we wish to
            show to the user """
        print >>sys.stderr,"UPnP mode "+str(upnp_type)+" request to firewall failed with error "+str(error_type)+" Try setting a different mode in Preferences. Listen port was "+str(listenport)+", protocol"+listenproto

    def upnp_got_ext_ip_callback(self,ip):
        """ Called by UPnP thread """
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
        try:
            if self.dialback_ext_ip is not None: # best
                return self.dialback_ext_ip # string immutable
            elif self.upnp_ext_ip is not None: # good
                return self.upnp_ext_ip 
            else: # slighly wild guess
                return self.locally_guessed_ext_ip
        finally:
            self.sesslock.release()




class SingleDownload:
    """ This class is accessed solely by the network thread """
    
    def __init__(self,infohash,metainfo,kvconfig,multihandler,listenport,videoanalyserpath,vodfileindex,set_error_func,pstate):
        
        self.dow = None
        self.set_error_func = set_error_func
        try:
            self.dldoneflag = Event()
            
            self.dlrawserver = multihandler.newRawServer(infohash,self.dldoneflag)
    
            """
            class BT1Download:    
                def __init__(self, statusfunc, finfunc, errorfunc, excfunc, doneflag, 
                     config, response, infohash, id, rawserver, port, play_video,
                     videoinfo, progressinf, videoanalyserpath, appdataobj = None, dht = None):
            """
            self.dow = BT1Download(self.hashcheckprogressfunc,
                            self.finishedfunc,
                            self.fatalerrorfunc, 
                            self.nonfatalerrorfunc,
                            self.dldoneflag,
                            kvconfig,
                            metainfo, 
                            infohash,
                            createPeerID(),
                            self.dlrawserver,
                            listenport,
                            videoanalyserpath
                            )
        
            file = self.dow.saveAs(self.save_as)
            
            # Set local filename in vodfileindex
            if vodfileindex is not None:
                index = vodfileindex[0]
                if index == -1:
                    index = 0
                vodfileindex[3] = self.dow.get_dest(index)
            self.dow.set_videoinfo(vodfileindex)

            print >>sys.stderr,"SingleDownload: setting vodfileindex",vodfileindex
            
            self._hashcheckfunc = None
            if pstate is None:
                resumedata = None
            else:
                # Restarting download
                resumedata=pstate['engineresumedata']
            self._hashcheckfunc = self.dow.initFiles(resumedata=resumedata)
            self._getstatsfunc = None
            if pstate is not None:
                self.hashcheckfrac = pstate['dlstate']['progress']
            else:
                self.hashcheckfrac = 0.0
            
        except Exception,e:
            self.fatalerrorfunc(e)
    
    
    def save_as(self,name,length,saveas,isdir):
        """ Return the local filename to which to save the file 'name' in the torrent """
        print >>sys.stderr,"Download: save_as(",name,length,saveas,isdir,")"
        try:
            path = os.path.join(saveas,name)
            if isdir and not os.path.isdir(path):
                os.mkdir(path)
            return path
        except Exception,e:
            self.fatalerrorfunc(e)

    def perform_hashcheck(self,complete_callback):
        """ Called by any thread """
        print >>sys.stderr,"Download: hashcheck()",self._hashcheckfunc
        try:
            """ Schedules actually hashcheck on network thread """
            self._getstatsfunc = SPECIAL_VALUE # signal we're hashchecking
            self._hashcheckfunc(complete_callback)
        except Exception,e:
            self.fatalerrorfunc(e)
            
    def hashcheck_done(self):
        """ Called by LaunchMany when hashcheck complete and the Download can be
            resumed
            
            Called by network thread
        """
        print >>sys.stderr,"Download: hashcheck_done()"
        try:
            self.dow.startEngine()
            self._getstatsfunc = self.dow.startStats() # not possible earlier
            ## TEMP ARNO self.dow.startRerequester()
            self.dlrawserver.start_listening(self.dow.getPortHandler())
        except Exception,e:
            self.fatalerrorfunc(e)


    # DownloadConfigInterface methods
    def set_max_speed(self,direct,speed,callback):
        if self.dow is not None:
            #print >>sys.stderr,"SingleDownload: set_max_speed",`self.dow.response['info']['name']`,direct,speed
            if direct == UPLOAD:
                self.dow.setUploadRate(speed)
            else:
                self.dow.setDownloadRate(speed)
        callback(direct,speed)


    def get_stats(self,getpeerlist):  
        if self._getstatsfunc is None:
            return (DLSTATUS_WAITING4HASHCHECK,None)
        elif self._getstatsfunc == SPECIAL_VALUE:
            stats = {}
            stats['frac'] = self.hashcheckfrac
            return (DLSTATUS_HASHCHECKING,stats)
        else:
            return (None,self._getstatsfunc(getpeerlist=getpeerlist))

    #
    #
    #
    def checkpoint(self):
        if self.dow is not None:
            return self.dow.checkpoint()
        else:
            return None
    
    def shutdown(self):
        resumedata = None
        if self.dow is not None:
            self.dldoneflag.set()
            self.dlrawserver.shutdown()
            resumedata = self.dow.shutdown()
            self.dow = None
        return resumedata

    #
    # Internal methods
    #
    def hashcheckprogressfunc(self,activity = '', fractionDone = 0.0):
        """ Allegedly only used by StorageWrapper during hashchecking """
        #print >>sys.stderr,"SingleDownload::statusfunc called",activity,fractionDone
        self.hashcheckfrac = fractionDone

    def finishedfunc(self):
        """ Download is complete """
        print >>sys.stderr,"SingleDownload::finishedfunc called *******************************"

    def fatalerrorfunc(self,data):
        print >>sys.stderr,"SingleDownload::fatalerrorfunc called",data
        if type(data) == StringType:
            print >>sys.stderr,"LEGACY CORE FATAL ERROR",data
            print_stack()
            self.set_error_func(TriblerLegacyException(data))
        else:
            print_exc()
            self.set_error_func(data)
        self.shutdown()

    def nonfatalerrorfunc(self,e):
        print >>sys.stderr,"SingleDownload::nonfatalerrorfunc called",e
        # Could log this somewhere, or phase it out (only used in Rerequester)
        

def offset2piece(offset,piecesize):
    
    p = offset / piecesize 
    if offset % piecesize > 0:
        p += 1
    return p



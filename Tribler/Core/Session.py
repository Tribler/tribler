# Written by Arno Bakker 
# see LICENSE.txt for license information
""" A Session is a running instance of the Tribler Core and the Core's central class. """

import sys
import pickle
import copy
from traceback import print_exc
from threading import RLock,currentThread

from Tribler.Core.simpledefs import *
from Tribler.Core.defaults import sessdefaults
from Tribler.Core.Base import *
from Tribler.Core.SessionConfig import *
import Tribler.Core.Overlay.permid
from Tribler.Core.DownloadConfig import get_default_dest_dir
from Tribler.Core.Utilities.utilities import find_prog_in_PATH,validTorrentFile,isValidURL
from Tribler.Core.APIImplementation.SessionRuntimeConfig import SessionRuntimeConfig
from Tribler.Core.APIImplementation.LaunchManyCore import TriblerLaunchMany
from Tribler.Core.APIImplementation.UserCallbackHandler import UserCallbackHandler


class Session(SessionRuntimeConfig):
    """
    
    A Session is a running instance of the Tribler Core and the Core's central
    class. It implements the SessionConfigInterface which can be used to change
    session parameters at runtime (for selected parameters).
    
    cf. libtorrent session
    """
    __single = None

    
    def __init__(self,scfg=None,ignore_singleton=False):
        """
        A Session object is created which is configured following a copy of the
        SessionStartupConfig scfg. (copy constructor used internally)
        
        @param scfg SessionStartupConfig object or None, in which case we
        look for a saved session in the default location (state dir). If
        we can't find it, we create a new SessionStartupConfig() object to 
        serve as startup config. Next, the config is saved in the directory
        indicated by its 'state_dir' attribute.
        
        In the current implementation only a single session instance can exist
        at a time in a process. The ignore_singleton flag is used for testing.
        """
        if not ignore_singleton:
            if Session.__single:
                raise RuntimeError, "Session is singleton"
            Session.__single = self
        
        self.sesslock = RLock()

        # Determine startup config to use
        if scfg is None: # If no override
            try:
                # Then try to read from default location
                scfg = self.load_pstate_sessconfig(state_dir)
            except:
                # If that fails, create a fresh config with factory defaults
                print_exc()
                scfg = SessionStartupConfig()
            self.sessconfig = scfg.sessconfig
        else: # overrides any saved config
            # Work from copy
            self.sessconfig = copy.copy(scfg.sessconfig)
        
        # Create dir for session state, if not exist    
        state_dir = self.sessconfig['state_dir']
        if state_dir is None:
            state_dir = Session.get_default_state_dir()
            self.sessconfig['state_dir'] = state_dir
            
        if not os.path.isdir(state_dir):
            os.mkdir(state_dir)

        if not self.sessconfig['torrent_collecting_dir']:
            self.sessconfig['torrent_collecting_dir'] = os.path.join(self.sessconfig['state_dir'], STATEDIR_TORRENTCOLL_DIR)
            
        if not self.sessconfig['peer_icon_path']:
            self.sessconfig['torrent_collecting_dir'] = os.path.join(self.sessconfig['state_dir'], STATEDIR_PEERICON_DIR)
            
        # PERHAPS: load default TorrentDef and DownloadStartupConfig from state dir
        # Let user handle that, he's got default_state_dir, etc.

        # Core init
        Tribler.Core.Overlay.permid.init()

        #print 'Session: __init__ config is', self.sessconfig
        
        #
        # Set params that depend on state_dir
        #
        # 1. keypair
        #
        if self.sessconfig['eckeypairfilename'] is None:
            self.keypair = Tribler.Core.Overlay.permid.generate_keypair()
            pairfilename = os.path.join(self.sessconfig['state_dir'],'ec.pem')
            pubfilename = os.path.join(self.sessconfig['state_dir'],'ecpub.pem')
            self.sessconfig['eckeypairfilename'] = pairfilename
            Tribler.Core.Overlay.permid.save_keypair(self.keypair,pairfilename)
            Tribler.Core.Overlay.permid.save_pub_key(self.keypair,pubfilename)
        else:
            # May throw exceptions
            self.keypair = Tribler.Core.Overlay.permid.read_keypair(self.sessconfig['eckeypairfilename'])
        
        # 2. Downloads persistent state dir
        dlpstatedir = os.path.join(self.sessconfig['state_dir'],STATEDIR_DLPSTATE_DIR)
        if not os.path.isdir(dlpstatedir):
            os.mkdir(dlpstatedir)
        
        # 3. tracker
        trackerdir = self.get_internal_tracker_dir()
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

        # 4. superpeer.txt
        if self.sessconfig['superpeer_file'] is None:
            self.sessconfig['superpeer_file'] = os.path.join(self.sessconfig['install_dir'],'Tribler','Core','superpeer.txt')

        # 5. download_help_dir
        if self.sessconfig['download_help_dir'] is None:
            self.sessconfig['download_help_dir'] = os.path.join(get_default_dest_dir(),DESTDIR_COOPDOWNLOAD)

        # 6. peer_icon_path
        if self.sessconfig['peer_icon_path'] is None:
            self.sessconfig['peer_icon_path'] = os.path.join(self.sessconfig['state_dir'],STATEDIR_PEERICON_DIR)

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
        """ Returns he Session singleton if it exists or otherwise
            creates it first, in which case you need to pass the constructor 
            params. 
            @return Session."""
        if Session.__single is None:
            Session(*args, **kw)
        return Session.__single
    get_instance = staticmethod(get_instance)

    def get_default_state_dir():
        """ Returns the factory default directory for storing session state.
        @return An absolute path name. """
        homedirpostfix = '.Tribler'
        if sys.platform == 'win32':
            homedirpostfix = 'Tribler' # i.e. C:\Documents and Settings\user\Application Data\Tribler
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
        object. The Download is then started and checkpointed.

        If a checkpointed version of the Download is found, that is restarted
        overriding the saved DownloadStartupConfig is "dcfg" is not None.
        
        @param tdef  A finalized TorrentDef
        @param dcfg DownloadStartupConfig or None, in which case 
        a new DownloadStartupConfig() is created with its default settings
        and the result becomes the runtime config of this Download.
        @return Download
        """
        # locking by lm
        return self.lm.add(tdef,dcfg)

    def resume_download_from_file(self,filename):
        """
        Recreates Download from resume file
        
        @return a Download object.
        
        Note: this cannot be made into a method of Download, as the Download 
        needs to be bound to a session, it cannot exist independently.
        """
        raise NotYetImplementedException()

    def get_downloads(self):
        """
        Returns a copy of the list of Downloads.
        @return A list of Download objects.
        """
        # locking by lm
        return self.lm.get_downloads()
    
    
    def remove_download(self,d,removecontent=False):  
        """
        Stops the download and removes it from the session.
        @param d The Download to remove
        @param removecontent Whether to delete the already downloaded content
        from disk.
        """
        # locking by lm
        self.lm.remove(d,removecontent=removecontent)


    def set_download_states_callback(self,usercallback,getpeerlist=False):
        """
        See Download.set_state_callback. Calls usercallback with a list of
        DownloadStates, one for each Download in the Session as first argument.
        The usercallback must return a tuple (when,getpeerlist) that indicates
        when to reinvoke the callback again (as a number of seconds from now,
        or < 0.0 if not at all) and whether to also include the details of
        the connected peers in the DownloadStates on that next call.
        
        The callback will be called by a popup thread which can be used
        indefinitely (within reason) by the higher level code.
        
        @param usercallback A function adhering to the above spec. 
        """
        self.lm.set_download_states_callback(usercallback,getpeerlist)


    #
    # Config parameters that only exist at runtime
    #
    def get_permid(self):
        """ Returns the PermID of the Session, as determined by the
        SessionConfig.set_permid() parameter. A PermID is a public key 
        @return The PermID encoded in a string in DER format. """
        self.sesslock.acquire()
        try:
            return str(self.keypair.pub().get_der())
        finally:
            self.sesslock.release()

    def get_external_ip(self):
        """ Returns the external IP address of this Session, i.e., by which
        it is reachable from the Internet. This address is determined via
        various mechanisms such as the UPnP protocol, our dialback mechanism,
        and an inspection of the local network configuration.
        @return A string. """
        # locking done by lm
        return self.lm.get_ext_ip()
        

    def get_current_startup_config_copy(self):
        """ Returns a SessionStartupConfig that is a copy of the current runtime 
        SessionConfig.
        @return SessionStartupConfig
        """
        # Called by any thread
        self.sesslock.acquire()
        try:
            sessconfig = copy.copy(self.sessconfig)
            return SessionStartupConfig(sessconfig=sessconfig)
        finally:
            self.sesslock.release()
            
    #
    # Internal tracker 
    #
    def get_internal_tracker_url(self):
        """ Returns the announce URL for the internal tracker. 
        @return URL """
        # Called by any thread
        ip = self.lm.get_ext_ip() #already thread safe
        port = self.get_listen_port() # already thread safe
        url = 'http://'+ip+':'+str(port)+'/announce/'
        return url

    def get_internal_tracker_dir(self):
        """ Returns the directory containing the torrents tracked by the internal 
        tracker (and associated databases).
        @return An absolute path. """
        if self.sessconfig['state_dir'] is None:
            return None
        else:
            return os.path.join(self.sessconfig['state_dir'],STATEDIR_ITRACKER_DIR)

    def add_to_internal_tracker(self,tdef):
        """ Add a torrent def to the list of torrents tracked by the internal
        tracker. Use this method to use the Session as a standalone tracker. 
        @param tdef A finalized TorrentDef. 
        """
        raise NotYetImplementedException()
        
    def remove_from_internal_tracker(self,tdef):
        """ Remove a torrent def from the list of torrents tracked by the 
        internal tracker. Use this method to use the Session as a standalone 
        tracker. 
        @param tdef A finalized TorrentDef.
        """
        raise NotYetImplementedException()


    #
    # Notification of events in the Session
    #
    def add_observer(self, func, subject, changeTypes = [NTFY_UPDATE, NTFY_INSERT, NTFY_DELETE], objectID = None):
        """ Add an observer function function to the Session. The observer 
        function will be called when one of the specified events (changeTypes)
        occurs on the specified subject.
        
        The function will be called by a popup thread which can be used
        indefinitely (within reason) by the higher level code.
        
        @param func The observer function. It should accept as its first argument
        the subject, as second argument the changeType, as third argument an
        objectID (e.g. the primary key in the observed database) and an 
        optional list of arguments.
        @param subject The subject to observe, one of NTFY_* subjects (see 
        simpledefs).
        @param changeTypes The list of events to be notified of one of NTFY_* 
        events.
        @param objectID The specific object in the subject to monitor (e.g. a
        specific primary key in a database to monitor for updates.)
        
        
        TODO: Jelle will add per-subject/event description here ;o)
        
        """
        #Called by any thread
        self.uch.notifier.add_observer(func, subject, changeTypes, objectID) # already threadsafe
        
    def remove_observer(self, func):
        """ Remove observer function. No more callbacks will be made.
        @param func The observer function to remove. """
        #Called by any thread
        self.uch.notifier.remove_observer(func) # already threadsafe


    #
    # Access control
    #
    def set_overlay_request_policy(self, reqpol):
        """
        Set a function which defines which overlay requests (e.g. dl_helper, rquery msg) 
        will be answered or will be denied.
        
        The function will be called by a network thread and must return 
        as soon as possible to prevent performance problems.
        
        @param reqpol is a Tribler.Core.RequestPolicy.AbstractRequestPolicy 
        object.
        """
        # Called by any thread
        # to protect self.sessconfig
        self.sesslock.acquire()
        try:
            overlay_loaded = self.sessconfig['overlay']
        finally:
            self.sesslock.release()
        if overlay_loaded:
            self.lm.overlay_apps.setRequestPolicy(reqpol) # already threadsafe
        elif DEBUG:
            print >>sys.stderr,"Session: overlay is disabled, so no overlay request policy needed"


    #
    # Persistence and shutdown 
    #
    def load_checkpoint(self):
        """ Restart Downloads from checkpoint, if any.
        
        This method allows the API user to manage restoring downloads. 
        E.g. a video player that wants to start the torrent the user clicked 
        on first, and only then restart any sleeping torrents (e.g. seeding).
        """
        self.lm.load_checkpoint()
    
    
    def checkpoint(self):
        """ Saves the internal session state to the Session's state dir. """
        #Called by any thread
        self.checkpoint_shutdown(stop=False)
    
    def shutdown(self):
        """ Checkpoints the session and closes it, stopping the download engine. """ 
        # Called by any thread
        self.checkpoint_shutdown(stop=True)
        self.uch.shutdown()
        
    def get_downloads_pstate_dir(self):
        """ Returns the directory in which to checkpoint the Downloads in this
        Session. """
        # Called by network thread
        self.sesslock.acquire()
        try:
            return os.path.join(self.sessconfig['state_dir'],STATEDIR_DLPSTATE_DIR)
        finally:
            self.sesslock.release()

    #
    # Internal persistence methods
    #
    def checkpoint_shutdown(self,stop):
        """ Checkpoints the Session and optionally shuts down the Session.
        @param stop Whether to shutdown the Session as well. """
        # Called by any thread
        # No locking required
        sscfg = self.get_current_startup_config_copy()
        try:
            self.save_pstate_sessconfig(sscfg)
        except Exception,e:
            self.lm.rawserver_nonfatalerrorfunc(e)

        # Checkpoint all Downloads
        print >>sys.stderr,"Session: checkpoint_shutdown"
        self.lm.checkpoint(stop=stop)

    def save_pstate_sessconfig(self,sscfg):
        """ Save the runtime SessionConfig to disk """
        # Called by any thread
        cfgfilename = os.path.join(sscfg.get_state_dir(),STATEDIR_SESSCONFIG)
        f = open(cfgfilename,"wb")
        pickle.dump(sscfg,f)
        f.close()


    def load_pstate_sessconfig(self,state_dir):
        """ Load the runtime SessionConfig from disk """
        cfgfilename = os.path.join(state_dir,STATEDIR_SESSCONFIG)
        f = open(cfgfilename,"rb")
        sscfg = pickle.load(f)
        f.close()
        return sscfg
        

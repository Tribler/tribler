# Written by Arno Bakker 
# see LICENSE.txt for license information

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
from Tribler.Core.BitTornado.RawServer import autodetect_socket_style
from Tribler.Core.Utilities.utilities import find_prog_in_PATH,validTorrentFile,isValidURL
from Tribler.Core.APIImplementation.SessionRuntimeConfig import SessionRuntimeConfig
from Tribler.Core.APIImplementation.LaunchManyCore import TriblerLaunchMany
from Tribler.Core.APIImplementation.UserCallbackHandler import UserCallbackHandler


class Session(SessionRuntimeConfig):
    """
    
    A Session implements the SessionConfigInterface which can be used to
    change session parameters are runtime (for selected parameters).
    
    cf. libtorrent session
    """
    __single = None

    
    def __init__(self,scfg=None,ignore_singleton=False):
        """
        A Session object is created which is configured following a copy of the
        SessionStartupConfig scfg. (copy constructor used internally)
        
        in: scfg = SessionStartupConfig object or None, in which case we
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
            self.sessconfig = scfg.sessconfig
            self.sessconfig['state_dir'] = state_dir

        if not self.sessconfig['torrent_collecting_dir']:
            self.sessconfig['torrent_collecting_dir'] = os.path.join(self.sessconfig['state_dir'], 'torrentcoll')
            
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
        object. The Download is then started and checkpointed.

        If a checkpointed version of the Download is found, that is restarted
        overriding the saved DownloadStartupConfig is "dcfg" is not None.
        
        in:
        tdef = a finalized TorrentDef
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
        """ Return the announce URL for the internal tracker """
        # Called by any thread
        ip = self.lm.get_ext_ip() #already thread safe
        port = self.get_listen_port() # already thread safe
        url = 'http://'+ip+':'+str(port)+'/announce/'
        return url

    def get_internal_tracker_dir(self):
        """ Return the directory containing the torrents tracked by the internal 
        tracker (and associated databases) """
        return os.path.join(self.sessconfig['state_dir'],STATEDIR_ITRACKER_DIR)

    def add_to_internal_tracker(self,tdef):
        """ Add a torrent def to the list of torrents tracked by the internal
        tracker. Use this method to use the Session as a standalone tracker. """
        raise NotYetImplementedException()
        
    def remove_from_internal_tracker(self,tdef):
        """ Remove a torrent def from the list of torrents tracked by the 
        internal tracker. Use this method to use the Session as a standalone 
        tracker. """
        raise NotYetImplementedException()


    def checkpoint(self):
        """ Saves the internal session state to the Session's state dir.
        
        Called by any thread """
        self.checkpoint_shutdown(stop=False)
    
    def shutdown(self):
        """ Checkpoints the session and closes it, stopping the download engine. 
        
        Called by any thread """
        self.checkpoint_shutdown(stop=True)
        self.uch.shutdown()
    
    def get_user_permid(self):
        self.sesslock.acquire()
        try:
            return str(self.keypair.pub().get_der())
        finally:
            self.sesslock.release()
        
    def set_overlay_request_policy(self, requestPolicy):
        """
        Set a function which defines which overlay requests (e.g. dl_helper, rquery msg) 
        will be answered or will be denied.
        
        requestPolicy is a Tribler.API.RequestPolicy.AbstractRequestPolicy object
        
        Called by any thread
        """
        # to protect self.sessconfig
        self.sesslock.acquire()
        try:
            overlay_loaded = self.sessconfig['overlay']
        finally:
            self.sesslock.release()
        if overlay_loaded:
            self.lm.overlay_apps.setRequestPolicy(requestPolicy) # already threadsafe
        else:
            print >>sys.stderr,"Session: overlay is disabled, so no overlay request policy needed"

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
            
    def add_observer(self, func, subject, changeTypes = [NTFY_UPDATE, NTFY_INSERT, NTFY_DELETE], id = None):
        """ Add function as an observer. It will receive callbacks if the respective data
        changes.
        
        Called by any thread
        """
        self.uch.notifier.add_observer(func, subject, changeTypes, id) # already threadsafe
        
    def remove_observer(self, func):
        """ Remove observer function. No more callbacks will be made.
        
        Called by any thread
        """
        self.uch.notifier.remove_observer(func) # already threadsafe

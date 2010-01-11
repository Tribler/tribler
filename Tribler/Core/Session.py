# Written by Arno Bakker 
# see LICENSE.txt for license information
""" A Session is a running instance of the Tribler Core and the Core's central class. """

import os
import sys
import copy
import binascii
from traceback import print_exc
from threading import RLock

from Tribler.__init__ import LIBRARYNAME
from Tribler.Core.simpledefs import *
from Tribler.Core.defaults import sessdefaults
from Tribler.Core.Base import *
from Tribler.Core.SessionConfig import *
from Tribler.Core.DownloadConfig import get_default_dest_dir
from Tribler.Core.Utilities.utilities import find_prog_in_PATH
from Tribler.Core.APIImplementation.SessionRuntimeConfig import SessionRuntimeConfig
from Tribler.Core.APIImplementation.LaunchManyCore import TriblerLaunchMany
from Tribler.Core.APIImplementation.UserCallbackHandler import UserCallbackHandler
from Tribler.Core.osutils import get_home_dir
GOTM2CRYPTO=False
try:
    import M2Crypto
    import Tribler.Core.Overlay.permid as permidmod
    GOTM2CRYPTO=True
except ImportError:
    pass

DEBUG = False

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
                state_dir = Session.get_default_state_dir()
                cfgfilename = Session.get_default_config_filename(state_dir)
                scfg = SessionStartupConfig.load(cfgfilename)
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
            os.makedirs(state_dir)

        collected_torrent_dir = self.sessconfig['torrent_collecting_dir']
        if not collected_torrent_dir:
            collected_torrent_dir = os.path.join(self.sessconfig['state_dir'], STATEDIR_TORRENTCOLL_DIR)
            self.sessconfig['torrent_collecting_dir'] = collected_torrent_dir
            
        if not os.path.exists(collected_torrent_dir):
            os.makedirs(collected_torrent_dir)
            
        if not self.sessconfig['peer_icon_path']:
            self.sessconfig['peer_icon_path'] = os.path.join(self.sessconfig['state_dir'], STATEDIR_PEERICON_DIR)
            
        # PERHAPS: load default TorrentDef and DownloadStartupConfig from state dir
        # Let user handle that, he's got default_state_dir, etc.

        # Core init
        #print >>sys.stderr,'Session: __init__ config is', self.sessconfig

        if GOTM2CRYPTO:
            permidmod.init()

            #
            # Set params that depend on state_dir
            #
            # 1. keypair
            #
            pairfilename = os.path.join(self.sessconfig['state_dir'],'ec.pem')
            if self.sessconfig['eckeypairfilename'] is None:
                self.sessconfig['eckeypairfilename'] = pairfilename
            
            if os.access(self.sessconfig['eckeypairfilename'],os.F_OK):
                # May throw exceptions
                self.keypair = permidmod.read_keypair(self.sessconfig['eckeypairfilename'])
            else:
                self.keypair = permidmod.generate_keypair()

                # Save keypair
                pubfilename = os.path.join(self.sessconfig['state_dir'],'ecpub.pem')
                permidmod.save_keypair(self.keypair,pairfilename)
                permidmod.save_pub_key(self.keypair,pubfilename)
        
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

        # 4. superpeer.txt and crawler.txt
        if self.sessconfig['superpeer_file'] is None:
            self.sessconfig['superpeer_file'] = os.path.join(self.sessconfig['install_dir'],LIBRARYNAME,'Core','superpeer.txt')
        if 'crawler_file' not in self.sessconfig or self.sessconfig['crawler_file'] is None:
            self.sessconfig['crawler_file'] = os.path.join(self.sessconfig['install_dir'], LIBRARYNAME,'Core','Statistics','crawler.txt')

        # 5. download_help_dir
        if self.sessconfig['overlay'] and self.sessconfig['download_help']:
            if self.sessconfig['download_help_dir'] is None:
                self.sessconfig['download_help_dir'] = os.path.join(get_default_dest_dir(),DESTDIR_COOPDOWNLOAD)
            # Jelle: under linux, default_dest_dir can be /tmp. Then download_help_dir can be deleted inbetween
            # sessions.
            if not os.path.isdir(self.sessconfig['download_help_dir']):
                os.makedirs(self.sessconfig['download_help_dir'])

        # 6. peer_icon_path
        if self.sessconfig['peer_icon_path'] is None:
            self.sessconfig['peer_icon_path'] = os.path.join(self.sessconfig['state_dir'],STATEDIR_PEERICON_DIR)
            if not os.path.isdir(self.sessconfig['peer_icon_path']):
                os.mkdir(self.sessconfig['peer_icon_path'])

        # 7. Poor man's versioning of SessionConfig, add missing
        # default values. Really should use PERSISTENTSTATE_CURRENTVERSION 
        # and do conversions.
        for key,defvalue in sessdefaults.iteritems():
            if key not in self.sessconfig:
                self.sessconfig[key] = defvalue

        if not 'live_aux_seeders' in self.sessconfig:
            # Poor man's versioning, really should update PERSISTENTSTATE_CURRENTVERSION
            self.sessconfig['live_aux_seeders'] = sessdefaults['live_aux_seeders']

        if not 'nat_detect' in self.sessconfig:
            self.sessconfig['nat_detect'] = sessdefaults['nat_detect']
        if not 'puncturing_internal_port' in self.sessconfig:
            self.sessconfig['puncturing_internal_port'] = sessdefaults['puncturing_internal_port']
        if not 'stun_servers' in self.sessconfig:
            self.sessconfig['stun_servers'] = sessdefaults['stun_servers']
        if not 'pingback_servers' in self.sessconfig:
            self.sessconfig['pingback_servers'] = sessdefaults['pingback_servers']
        if not 'mainline_dht' in self.sessconfig:
            self.sessconfig['mainline_dht'] = sessdefaults['mainline_dht']
            
        # Checkpoint startup config
        self.save_pstate_sessconfig()

        # Create handler for calling back the user via separate threads
        self.uch = UserCallbackHandler(self)

        # Create engine with network thread
        self.lm = TriblerLaunchMany()
        self.lm.register(self,self.sesslock)
        self.lm.start()


    #
    # Class methods
    #
    def get_instance(*args, **kw):
        """ Returns the Session singleton if it exists or otherwise
            creates it first, in which case you need to pass the constructor 
            params. 
            @return Session."""
        if Session.__single is None:
            Session(*args, **kw)
        return Session.__single
    get_instance = staticmethod(get_instance)

    def get_default_state_dir(homedirpostfix='.Tribler'):
        """ Returns the factory default directory for storing session state
        on the current platform (Win32,Mac,Unix).
        @return An absolute path name. """

        # Allow override
        statedirvar = '${TSTATEDIR}'
        statedir = os.path.expandvars(statedirvar)
        if statedir and statedir != statedirvar:
            return statedir
        
        # Boudewijn: retrieving the homedir fails with python 2.x on
        # windows when the username contains specific unicode
        # characters. using the get_home_dir() function patches this
        # problem.
        #
        homedir = get_home_dir()
        
        if sys.platform == "win32":
            # 5 = XP, 6 = Vista
            if sys.getwindowsversion()[0] == 6:
                appdir = os.path.join(homedir,u"AppData",u"Roaming")
            else:
                appdir = os.path.join(homedir,u"Application Data")
        else:
            appdir = homedir

        statedir = os.path.join(appdir, homedirpostfix)
        return statedir

    get_default_state_dir = staticmethod(get_default_state_dir)


    #
    # Public methods
    #
    def start_download(self,tdef,dcfg=None,initialdlstatus=None):
        """ 
        Creates a Download object and adds it to the session. The passed 
        TorrentDef and DownloadStartupConfig are copied into the new Download 
        object. The Download is then started and checkpointed.

        If a checkpointed version of the Download is found, that is restarted
        overriding the saved DownloadStartupConfig if "dcfg" is not None.
        
        @param tdef  A finalized TorrentDef
        @param dcfg DownloadStartupConfig or None, in which case 
        a new DownloadStartupConfig() is created with its default settings
        and the result becomes the runtime config of this Download.
        @param initialdlstatus The initial download status of this Download 
        or None. This enables the caller to create a Download in e.g. 
        DLSTATUS_REPEXING state instead.
        @return Download
        """
        # locking by lm
        return self.lm.add(tdef,dcfg,initialdlstatus=initialdlstatus)

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
        

    def get_externally_reachable(self):
        """ Returns whether the Session is externally reachable, i.e., its 
          listen port is not firewalled. Use add_observer() with NTFY_REACHABLE
          to register to the event of detecting reachablility. Note that due to
          the use of UPnP a Session may become reachable some time after 
          startup and due to the Dialback mechanism, this method may return 
          False while the Session is actually already reachable. Note that True
          doesn't mean the Session is reachable from the open Internet, could just
          be from the local (otherwise firewalled) LAN.
          @return A boolean. """

        # Arno, LICHT: make it throw exception when used in LITE versie.
        from Tribler.Core.NATFirewall.DialbackMsgHandler import DialbackMsgHandler
        
        return DialbackMsgHandler.getInstance().isConnectable()


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
        self.sesslock.acquire()
        try:
            url = None
            if 'tracker_url' in self.sessconfig:
                url = self.sessconfig['tracker_url'] # user defined override, e.g. specific hostname
            if url is None:
                ip = self.lm.get_ext_ip()
                port = self.get_listen_port()
                url = 'http://'+ip+':'+str(port)+'/announce/'
            return url
        finally:
            self.sesslock.release()


    def get_internal_tracker_dir(self):
        """ Returns the directory containing the torrents tracked by the internal 
        tracker (and associated databases).
        @return An absolute path. """
        # Called by any thread
        self.sesslock.acquire()
        try:
            if self.sessconfig['state_dir'] is None:
                return None
            else:
                return os.path.join(self.sessconfig['state_dir'],STATEDIR_ITRACKER_DIR)
        finally:
            self.sesslock.release()


    def add_to_internal_tracker(self,tdef):
        """ Add a torrent def to the list of torrents tracked by the internal
        tracker. Use this method to use the Session as a standalone tracker. 
        @param tdef A finalized TorrentDef. 
        """
        # Called by any thread
        self.sesslock.acquire()
        try:
            infohash = tdef.get_infohash()
            filename = self.get_internal_tracker_torrentfilename(infohash)
            tdef.save(filename)
            
            print >>sys.stderr,"Session: add_to_int_tracker: saving to",filename,"url-compat",tdef.get_url_compat()
            
            # Bring to attention of Tracker thread
            self.lm.tracker_rescan_dir()
        finally:
            self.sesslock.release()
        
    def remove_from_internal_tracker(self,tdef):
        """ Remove a torrent def from the list of torrents tracked by the 
        internal tracker. Use this method to use the Session as a standalone 
        tracker. 
        @param tdef A finalized TorrentDef.
        """
        infohash = tdef.get_infohash()
        self.remove_from_internal_tracker_by_infohash(infohash)
        
    def remove_from_internal_tracker_by_infohash(self,infohash):
        """ Remove a torrent def from the list of torrents tracked by the 
        internal tracker. Use this method to use the Session as a standalone 
        tracker. 
        @param infohash Identifier of the torrent def to remove.
        """
        # Called by any thread
        self.sesslock.acquire()
        try:
            filename = self.get_internal_tracker_torrentfilename(infohash)
            if DEBUG:
                print >>sys.stderr,"Session: removing itracker entry",filename
            if os.access(filename,os.F_OK):
                os.remove(filename)
            # Bring to attention of Tracker thread
            self.lm.tracker_rescan_dir()
        finally:
            self.sesslock.release()

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

    def open_dbhandler(self,subject):
        """ Opens a connection to the specified database. Only the thread 
        calling this method may use this connection. The connection must be 
        closed with close_dbhandler() when this thread exits.
        
        @param subject The database to open. Must be one of the subjects
        specified here.
        @return A reference to a DBHandler class for the specified subject or 
        None when the Session was not started with megacaches enabled. 
        <pre> NTFY_PEERS -> PeerDBHandler
        NTFY_TORRENTS -> TorrentDBHandler
        NTFY_PREFERENCES -> PreferenceDBHandler
        NTFY_SUPERPEERS -> SuperpeerDBHandler
        NTFY_FRIENDS -> FriendsDBHandler
        NTFY_MYPREFERENCES -> MyPreferenceDBHandler
        NTFY_BARTERCAST -> BartercastDBHandler
        NTFY_SEARCH -> SearchDBHandler
        NTFY_TERM -> TermDBHandler
        NTFY_VOTECAST -> VotecastDBHandler
        NTFY_CHANNELCAST -> ChannelCastDBHandler
        </pre>
        """ 
        # Called by any thread
        self.sesslock.acquire()
        try:
            if subject == NTFY_PEERS:
                return self.lm.peer_db
            elif subject == NTFY_TORRENTS:
                return self.lm.torrent_db
            elif subject == NTFY_PREFERENCES:
                return self.lm.pref_db
            elif subject == NTFY_SUPERPEERS:
                return self.lm.superpeer_db
            elif subject == NTFY_FRIENDS:
                return self.lm.friend_db
            elif subject == NTFY_MYPREFERENCES:
                return self.lm.mypref_db
            elif subject == NTFY_BARTERCAST:
                return self.lm.bartercast_db
            elif subject == NTFY_SEEDINGSTATS:
                return self.lm.seedingstats_db
            elif subject == NTFY_SEEDINGSTATSSETTINGS:
                return self.lm.seedingstatssettings_db
            elif subject == NTFY_VOTECAST:
                return self.lm.votecast_db
            elif subject == NTFY_SEARCH:
                return self.lm.search_db
            elif subject == NTFY_TERM:
                return self.lm.term_db
            elif subject == NTFY_CHANNELCAST:
                return self.lm.channelcast_db
            else:
                raise ValueError('Cannot open DB subject: '+subject)
        finally:
            self.sesslock.release()
        
        
    def close_dbhandler(self,dbhandler):
        """ Closes the given database connection """
        dbhandler.close()
    

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
    def load_checkpoint(self,initialdlstatus=None):
        """ Restart Downloads from checkpoint, if any.
        
        This method allows the API user to manage restoring downloads. 
        E.g. a video player that wants to start the torrent the user clicked 
        on first, and only then restart any sleeping torrents (e.g. seeding).
        The optional initialdlstatus parameter can be set to DLSTATUS_STOPPED
        to restore all the Downloads in DLSTATUS_STOPPED state.
        """
        self.lm.load_checkpoint(initialdlstatus)
    
    
    def checkpoint(self):
        """ Saves the internal session state to the Session's state dir. """
        #Called by any thread
        self.checkpoint_shutdown(stop=False,checkpoint=True,gracetime=None,hacksessconfcheckpoint=False)
    
    def shutdown(self,checkpoint=True,gracetime=2.0,hacksessconfcheckpoint=True):
        """ Checkpoints the session and closes it, stopping the download engine.
        @param checkpoint Whether to checkpoint the Session state on shutdown.
        @param gracetime Time to allow for graceful shutdown + signoff (seconds).
        """ 
        # Called by any thread
        self.lm.early_shutdown()
        self.checkpoint_shutdown(stop=True,checkpoint=checkpoint,gracetime=gracetime,hacksessconfcheckpoint=hacksessconfcheckpoint)
        self.uch.shutdown()
    
    def has_shutdown(self):
        """ Whether the Session has completely shutdown, i.e., its internal
        threads are finished and it is safe to quit the process the Session
        is running in.
        @return A Boolean.
        """
        return self.lm.sessdoneflag.isSet()
        
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
    # Tribler Core special features
    #
    def query_connected_peers(self,query,usercallback,max_peers_to_query=None):
        """ Ask all Tribler peers we're currently connected to resolve the
        specified query and return the hits. For each peer that returns
        hits the usercallback method is called with first parameter the
        permid of the peer, as second parameter the query string and
        as third parameter a dictionary of hits. The number of times the 
        usercallback method will be called is undefined.

        The callback will be called by a popup thread which can be used
        indefinitely (within reason) by the higher level code.

        At the moment we support three types of query, which are all queries for
        torrent files that match a set of keywords. The format of the
        query string is "SIMPLE kw1 kw2 kw3" (type 1) or "SIMPLE+METADATA kw1 kw2 
        kw3" (type 3). In the future we plan to support full SQL queries.
        
        For SIMPLE queries the dictionary of hits consists of 
        (infohash,torrentrecord) pairs. The torrentrecord is a 
        dictionary that contains the following keys:
        <pre>
        * 'content_name': The 'name' field of the torrent.
        * 'length': The total size of the content in the torrent.
        * 'leecher': The currently known number of downloaders.
        * 'seeder': The currently known number of seeders.
        * 'category': A list of category strings the torrent was classified into
          by the remote peer.
        </pre>

        From Session API version 1.0.2 the following keys were added
        to the torrentrecord:
        <pre>
        * 'torrent_size': The size of the .torrent file.
        </pre>

        For SIMPLE+METADATA queries there is an extra field
        <pre>
        * 'torrent_file': Bencoded contents of the .torrent file. 
        </pre>
        The torrents *not* be automatically added to the TorrentDBHandler 
        (if enabled) at the time of the call.

        
        The third type of query: search for channels. It is used to query for 
        channels: either a particular channel matching the permid in the query, 
        or a list of channels whose names match the keywords in the query
        by sending the query to connected peers. 
        
        The format of the query in the corresponding scenarios should be: 
        a. keyword-based query: "CHANNEL k:bbc"     
            ('k' stands for keyword-based and ':' is a separator followed by 
            the keywords)
        b. permid-based query: "CHANNEL p:f34wrf2345wfer2345wefd3r34r54" 
            ('p' stands for permid-based and ':' is a separator followed by
            the permid)
        
        In each of the above 2 cases, the format of the hits that is returned 
        by the queried peer is a dictionary of hits of (signature,channelrecord). 
        The channelrecord is a dictionary the contains following keys: 
        {publisher_id, publisher_name, infohash, torrenthash, torrentname, time_stamp}

        
        @param query A Unicode query string adhering to the above spec.
        @param usercallback A function adhering to the above spec.
        """
        self.sesslock.acquire()
        try:
            if self.sessconfig['overlay']:
                if not (query.startswith('SIMPLE ') or query.startswith('SIMPLE+METADATA ')) and not query.startswith('CHANNEL '):
                    raise ValueError('Query does not start with SIMPLE or SIMPLE+METADATA or CHANNEL')
                
                from Tribler.Core.SocialNetwork.RemoteQueryMsgHandler import RemoteQueryMsgHandler
                
                rqmh = RemoteQueryMsgHandler.getInstance()
                rqmh.send_query(query,usercallback,max_peers_to_query=max_peers_to_query)
            else:
                raise OperationNotEnabledByConfigurationException("Overlay not enabled")
        finally:
            self.sesslock.release()
            
    
    def download_torrentfile_from_peer(self,permid,infohash,usercallback):
        """ Ask the designated peer to send us the torrentfile for the torrent
        identified by the passed infohash. If the torrent is succesfully 
        received, the usercallback method is called with the infohash as first
        and the contents of the torrentfile (bencoded dict) as second parameter.
        If the torrent could not be obtained, the callback is not called.
        The torrent will have been added to the TorrentDBHandler (if enabled)
        at the time of the call.
        
        @param permid The PermID of the peer to query.
        @param infohash The infohash of the torrent.
        @param usercallback A function adhering to the above spec.
        """
        # ARNOCOMMENT: Perhaps make save to database optional.
        self.sesslock.acquire()
        try:
            if self.sessconfig['overlay']:
                from Tribler.Core.SocialNetwork.RemoteTorrentHandler import RemoteTorrentHandler
                
                rtorrent_handler = RemoteTorrentHandler.getInstance()
                rtorrent_handler.download_torrent(permid,infohash,usercallback)
            else:
                raise OperationNotEnabledByConfigurationException("Overlay not enabled")
        finally:
            self.sesslock.release()
        

    #
    # Internal persistence methods
    #
    def checkpoint_shutdown(self,stop,checkpoint,gracetime,hacksessconfcheckpoint):
        """ Checkpoints the Session and optionally shuts down the Session.
        @param stop Whether to shutdown the Session as well.
        @param checkpoint Whether to checkpoint at all, or just to stop.
        @param gracetime Time to allow for graceful shutdown + signoff (seconds). 
        """
        # Called by any thread
        self.sesslock.acquire()
        try:
            # Arno: Make checkpoint optional on shutdown. At the moment setting 
            # the config at runtime is not possible (see SessionRuntimeConfig)
            # so this has little use, and interferes with our way of
            # changing the startup config, which is to write a new
            # config to disk that will be read at start up.
            if hacksessconfcheckpoint:
                try:
                    self.save_pstate_sessconfig()
                except Exception,e:
                    self.lm.rawserver_nonfatalerrorfunc(e)

            # Checkpoint all Downloads and stop NetworkThread
            if DEBUG:
                print >>sys.stderr,"Session: checkpoint_shutdown"
            self.lm.checkpoint(stop=stop,checkpoint=checkpoint,gracetime=gracetime)
        finally:
            self.sesslock.release()

    def save_pstate_sessconfig(self):
        """ Save the runtime SessionConfig to disk """
        # Called by any thread
        sscfg = self.get_current_startup_config_copy()
        cfgfilename = Session.get_default_config_filename(sscfg.get_state_dir())
        sscfg.save(cfgfilename)


    def get_default_config_filename(state_dir):
        """ Return the name of the file where a session config is saved by default. 
        @return A filename 
        """
        return os.path.join(state_dir,STATEDIR_SESSCONFIG)
    get_default_config_filename = staticmethod(get_default_config_filename)


    def get_internal_tracker_torrentfilename(self,infohash):
        """ Return the absolute pathname of the torrent file used by the
        internal tracker.
        @return A filename
        """
        trackerdir = self.get_internal_tracker_dir()
        basename = binascii.hexlify(infohash)+'.torrent' # ignore .tribe stuff, not vital
        return os.path.join(trackerdir,basename)

    def get_nat_type(self, callback=None):
        """ Return the type of Network Address Translator (NAT) detected.

        When a callback parameter is supplied it will always be
        called. When the NAT-type is already known the callback will
        be made instantly. Otherwise, the callback will be made when
        the NAT discovery has finished.

        The callback will be called by a popup thread which can be used
        indefinitely (within reason) by the higher level code.

        Return values:
        "Blocked"
        "Open Internet"
        "Restricted Cone Firewall"
        "Port Restricted Cone Firewall"
        "Full Cone NAT"
        "Restricted Cone NAT"
        "Port Restricted Cone NAT"
        "Symmetric NAT"
        "Unknown NAT/Firewall"

        @param callback Optional callback used to notify the NAT type
        @return String 
        """
        # TODO: define constants in simpledefs for these
        # Called by any thread
        self.sesslock.acquire()
        try:
            from Tribler.Core.NATFirewall.ConnectionCheck import ConnectionCheck
            
            return ConnectionCheck.getInstance(self).get_nat_type(callback=callback)
        finally:
            self.sesslock.release()

    #
    # Friendship functions
    #
    def send_friendship_message(self,permid,mtype,approved=None):
        """ Send friendship msg to the specified peer 
        
        F_REQUEST_MSG:
        
        F_RESPONSE_MSG:
        @param approved Whether you want him as friend or not.
        
        """
        self.sesslock.acquire()
        try:
            if self.sessconfig['overlay']:
                if mtype == F_FORWARD_MSG:
                    raise ValueError("User cannot send FORWARD messages directly")
                
                from Tribler.Core.SocialNetwork.FriendshipMsgHandler import FriendshipMsgHandler
                
                fmh = FriendshipMsgHandler.getInstance()
                params = {}
                if approved is not None:
                    params['response'] = int(approved)
                fmh.anythread_send_friendship_msg(permid,mtype,params)
            else:
                raise OperationNotEnabledByConfigurationException("Overlay not enabled")
        finally:
            self.sesslock.release()


    def set_friendship_callback(self,usercallback):
        """ When a new friendship request is received the given
        callback function is called with as first parameter the
        requester's permid and as second parameter a dictionary of
        request arguments:
            callback(requester_permid,params)

        The callback is called by a popup thread which can be used
        indefinitely (within reason) by the higher level code.
        
        @param usercallback A callback function adhering to the above spec.
        """
        self.sesslock.acquire()
        try:
            if self.sessconfig['overlay']:
                from Tribler.Core.SocialNetwork.FriendshipMsgHandler import FriendshipMsgHandler
                
                fmh = FriendshipMsgHandler.getInstance()
                fmh.register_usercallback(usercallback)
            else:
                raise OperationNotEnabledByConfigurationException("Overlay not enabled")
        finally:
            self.sesslock.release()
            

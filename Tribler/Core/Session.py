# Written by Arno Bakker
# Updated by George Milescu
# see LICENSE.txt for license information
""" A Session is a running instance of the Tribler Core and the Core's central class. """

import os
import sys
import copy
import binascii
from traceback import print_exc

from Tribler.Core.simpledefs import *
from Tribler.Core.defaults import sessdefaults
from Tribler.Core.Base import *
from Tribler.Core.SessionConfig import *
from Tribler.Core.APIImplementation.SessionRuntimeConfig import SessionRuntimeConfig
from Tribler.Core.APIImplementation.LaunchManyCore import TriblerLaunchMany
from Tribler.Core.APIImplementation.UserCallbackHandler import UserCallbackHandler
from Tribler.Core.osutils import get_appstate_dir
from Tribler.Core import NoDispersyRLock
import socket

GOTM2CRYPTO = False
try:
    import M2Crypto
    import Tribler.Core.permid as permidmod
    GOTM2CRYPTO = True
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

    def __init__(self, scfg=None, ignore_singleton=False):
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
                raise RuntimeError("Session is singleton")
            Session.__single = self

        self.ignore_singleton = ignore_singleton
        self.sesslock = NoDispersyRLock()

        # Determine startup config to use
        if scfg is None:  # If no override
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
        else:  # overrides any saved config
            # Work from copy
            self.sessconfig = copy.copy(scfg.sessconfig)

        def create_dir(fullpath):
            if not os.path.isdir(fullpath):
                os.makedirs(fullpath)

        def set_and_create_dir(config, name, default_dir):
            dirname = config.get(name, None)
            if dirname is None:
                config[name] = default_dir

            create_dir(config[name])

        set_and_create_dir(self.sessconfig, 'state_dir', Session.get_default_state_dir())
        set_and_create_dir(self.sessconfig, 'torrent_collecting_dir', os.path.join(self.sessconfig['state_dir'], STATEDIR_TORRENTCOLL_DIR))
        set_and_create_dir(self.sessconfig, 'swiftmetadir', os.path.join(self.sessconfig['state_dir'], STATEDIR_SWIFTRESEED_DIR))
        set_and_create_dir(self.sessconfig, 'peer_icon_path', os.path.join(self.sessconfig['state_dir'], STATEDIR_PEERICON_DIR))

        create_dir(os.path.join(self.sessconfig['state_dir'], STATEDIR_DLPSTATE_DIR))

        # Poor man's versioning of SessionConfig, add missing
        # default values. Really should use PERSISTENTSTATE_CURRENTVERSION
        # and do conversions.
        for key, defvalue in sessdefaults.iteritems():
            if key not in self.sessconfig:
                self.sessconfig[key] = defvalue

        if self.sessconfig['nickname'] == '__default_name__':
            self.sessconfig['nickname'] = socket.gethostname()

        # SWIFTPROC
        if self.sessconfig['swiftpath'] is None:
            if sys.platform == "win32":
                self.sessconfig['swiftpath'] = os.path.join(self.sessconfig['install_dir'], "swift.exe")
            else:
                self.sessconfig['swiftpath'] = os.path.join(self.sessconfig['install_dir'], "swift")

        if GOTM2CRYPTO:
            permidmod.init()
            # Set params that depend on state_dir
            #
            # 1. keypair
            #
            pairfilename = os.path.join(self.sessconfig['state_dir'], 'ec.pem')
            if self.sessconfig['eckeypairfilename'] is None:
                self.sessconfig['eckeypairfilename'] = pairfilename

            if os.access(self.sessconfig['eckeypairfilename'], os.F_OK):
                # May throw exceptions
                self.keypair = permidmod.read_keypair(self.sessconfig['eckeypairfilename'])
            else:
                self.keypair = permidmod.generate_keypair()

                # Save keypair
                pubfilename = os.path.join(self.sessconfig['state_dir'], 'ecpub.pem')
                permidmod.save_keypair(self.keypair, pairfilename)
                permidmod.save_pub_key(self.keypair, pubfilename)

        # Checkpoint startup config
        self.save_pstate_sessconfig()

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

    def has_instance():
        return Session.__single != None
    has_instance = staticmethod(has_instance)

    def del_instance():
        Session.__single = None
    del_instance = staticmethod(del_instance)

    def get_default_state_dir(homedirpostfix='.Tribler'):
        """ Returns the factory default directory for storing session state
        on the current platform (Win32,Mac,Unix).
        @return An absolute path name. """

        # Allow override
        statedirvar = '${TSTATEDIR}'
        statedir = os.path.expandvars(statedirvar)
        if statedir and statedir != statedirvar:
            return statedir

        if os.path.isdir(homedirpostfix):
            return os.path.abspath(homedirpostfix)

        appdir = get_appstate_dir()
        statedir = os.path.join(appdir, homedirpostfix)
        return statedir

    get_default_state_dir = staticmethod(get_default_state_dir)

    #
    # Public methods
    #
    def start_download(self, cdef, dcfg=None, initialdlstatus=None, hidden=False):
        """
        Creates a Download object and adds it to the session. The passed
        ContentDef and DownloadStartupConfig are copied into the new Download
        object. The Download is then started and checkpointed.

        If a checkpointed version of the Download is found, that is restarted
        overriding the saved DownloadStartupConfig if "dcfg" is not None.

        @param cdef  A finalized TorrentDef or a SwiftDef
        @param dcfg DownloadStartupConfig or None, in which case
        a new DownloadStartupConfig() is created with its default settings
        and the result becomes the runtime config of this Download.
        @param initialdlstatus The initial download status of this Download
        or None. This enables the caller to create a Download in e.g.
        DLSTATUS_STOPPED state instead.
        @param hidden Whether this torrent should be added to the mypreference table
        @return Download
        """
        # locking by lm
        if cdef.get_def_type() == "torrent":
            return self.lm.add(cdef, dcfg, initialdlstatus=initialdlstatus, hidden=hidden)
        else:
            # SWIFTPROC
            return self.lm.swift_add(cdef, dcfg, initialdlstatus=initialdlstatus, hidden=hidden)

    def resume_download_from_file(self, filename):
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

    def get_download(self, hash):
        """
        Returns the Download object for this hash.
        @return A Donwload Object.
        """
        # locking by lm
        return self.lm.get_download(hash)

    def remove_download(self, d, removecontent=False, removestate=True, hidden=False):
        """
        Stops the download and removes it from the session.
        @param d The Download to remove
        @param removecontent Whether to delete the already downloaded content
        from disk.
        @param removestate    Whether to delete the metadata files of the downloaded
        content from disk.
        @param hidden Whether this torrent is added to the mypreference table and this entry should be
        removed
        """
        # locking by lm
        if d.get_def().get_def_type() == "torrent":
            self.lm.remove(d, removecontent=removecontent, removestate=removestate, hidden=hidden)
        else:
            # SWIFTPROC
            self.lm.swift_remove(d, removecontent=removecontent, removestate=removestate, hidden=hidden)

    def remove_download_by_id(self, id, removecontent=False, removestate=True):
        """
        @param infohash The Download to remove
        @param removecontent Whether to delete the already downloaded content
        from disk.

        !We can only remove content when the download object is found, otherwise only
        the state is removed.
        """
        downloadList = self.get_downloads()
        for download in downloadList:
            if download.get_def().get_id() == id:
                self.remove_download(download, removecontent, removestate)
                return

        self.lm.remove_id(id)
        self.uch.perform_removestate_callback(id, [], False)

    def set_download_states_callback(self, usercallback, getpeerlist=None):
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
        self.lm.set_download_states_callback(usercallback, getpeerlist or [])

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
        raise NotYetImplementedException()

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
    # Notification of events in the Session
    #
    def add_observer(self, func, subject, changeTypes=[NTFY_UPDATE, NTFY_INSERT, NTFY_DELETE], objectID=None, cache=0):
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
        @param cache The time to bundle/cache events matching this function

        TODO: Jelle will add per-subject/event description here ;o)

        """
        # Called by any thread
        self.uch.notifier.add_observer(func, subject, changeTypes, objectID, cache=cache)  # already threadsafe

    def remove_observer(self, func):
        """ Remove observer function. No more callbacks will be made.
        @param func The observer function to remove. """
        # Called by any thread
        self.uch.notifier.remove_observer(func)  # already threadsafe

    def open_dbhandler(self, subject):
        """ Opens a connection to the specified database. Only the thread
        calling this method may use this connection. The connection must be
        closed with close_dbhandler() when this thread exits.

        @param subject The database to open. Must be one of the subjects
        specified here.
        @return A reference to a DBHandler class for the specified subject or
        None when the Session was not started with megacaches enabled.
        <pre> NTFY_PEERS -> PeerDBHandler
        NTFY_TORRENTS -> TorrentDBHandler
        NTFY_MYPREFERENCES -> MyPreferenceDBHandler
        NTFY_VOTECAST -> VotecastDBHandler
        NTFY_CHANNELCAST -> ChannelCastDBHandler
        </pre>
        """
        if not self.get_megacache():
            raise OperationNotEnabledByConfigurationException()

        # Called by any thread
        self.sesslock.acquire()
        try:
            if subject == NTFY_PEERS:
                return self.lm.peer_db
            elif subject == NTFY_TORRENTS:
                return self.lm.torrent_db
            elif subject == NTFY_MYPREFERENCES:
                return self.lm.mypref_db
            elif subject == NTFY_SEEDINGSTATS:
                return self.lm.seedingstats_db
            elif subject == NTFY_SEEDINGSTATSSETTINGS:
                return self.lm.seedingstatssettings_db
            elif subject == NTFY_VOTECAST:
                return self.lm.votecast_db
            elif subject == NTFY_CHANNELCAST:
                return self.lm.channelcast_db
            else:
                raise ValueError('Cannot open DB subject: ' + subject)
        finally:
            self.sesslock.release()

    def close_dbhandler(self, dbhandler):
        """ Closes the given database connection """
        dbhandler.close()

    #
    # Persistence and shutdown
    #
    def load_checkpoint(self, initialdlstatus=None, initialdlstatus_dict={}):
        """ Restart Downloads from checkpoint, if any.

        This method allows the API user to manage restoring downloads.
        E.g. a video player that wants to start the torrent the user clicked
        on first, and only then restart any sleeping torrents (e.g. seeding).
        The optional initialdlstatus parameter can be set to DLSTATUS_STOPPED
        to restore all the Downloads in DLSTATUS_STOPPED state.
        The options initialdlstatus_dict parameter can be used to specify a
        state overriding the initaldlstatus parameter per download id.
        """
        self.lm.load_checkpoint(initialdlstatus, initialdlstatus_dict)

    def checkpoint(self):
        """ Saves the internal session state to the Session's state dir. """
        # Called by any thread
        self.checkpoint_shutdown(stop=False, checkpoint=True, gracetime=None, hacksessconfcheckpoint=False)

    def start(self):
        """ Create the LaunchManyCore instance and start it"""

        # Create handler for calling back the user via separate threads
        self.uch = UserCallbackHandler(self)

        # Create engine with network thread
        self.lm = TriblerLaunchMany()
        self.lm.register(self, self.sesslock)
        self.lm.start()

    def shutdown(self, checkpoint=True, gracetime=2.0, hacksessconfcheckpoint=True):
        """ Checkpoints the session and closes it, stopping the download engine.
        @param checkpoint Whether to checkpoint the Session state on shutdown.
        @param gracetime Time to allow for graceful shutdown + signoff (seconds).
        """
        # Called by any thread
        self.lm.early_shutdown()
        self.checkpoint_shutdown(stop=True, checkpoint=checkpoint, gracetime=gracetime, hacksessconfcheckpoint=hacksessconfcheckpoint)
        # Arno, 2010-08-09: now shutdown after gracetime
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
            return os.path.join(self.sessconfig['state_dir'], STATEDIR_DLPSTATE_DIR)
        finally:
            self.sesslock.release()

    def download_torrentfile(self, infohash=None, roothash=None, usercallback=None, prio=0):
        """ Try to download the torrentfile without a known source.
        A possible source could be the DHT.
        If the torrent is succesfully
        received, the usercallback method is called with the infohash as first
        and the contents of the torrentfile (bencoded dict) as second parameter.
        If the torrent could not be obtained, the callback is not called.
        The torrent will have been added to the TorrentDBHandler (if enabled)
        at the time of the call.
        @param infohash The infohash of the torrent.
        @param usercallback A function adhering to the above spec.
        """
        if not self.lm.rtorrent_handler:
            raise OperationNotEnabledByConfigurationException()

        self.lm.rtorrent_handler.download_torrent(None, infohash, roothash, usercallback, prio)

    def download_torrentfile_from_peer(self, candidate, infohash=None, roothash=None, usercallback=None, prio=0):
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
        if not self.lm.rtorrent_handler:
            raise OperationNotEnabledByConfigurationException()

        self.lm.rtorrent_handler.download_torrent(candidate, infohash, roothash, usercallback, prio)

    def download_torrentmessages_from_peer(self, candidate, infohashes, usercallback, prio=0):
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
        if not self.lm.rtorrent_handler:
            raise OperationNotEnabledByConfigurationException()

        self.lm.rtorrent_handler.download_torrentmessages(candidate, infohashes, usercallback, prio)

    def get_dispersy_instance(self):
        if not self.get_dispersy():
            raise OperationNotEnabledByConfigurationException()

        return self.lm.dispersy

    def get_swift_process(self):
        if not self.get_swift_proc():
            raise OperationNotEnabledByConfigurationException()

        return self.lm.swift_process

    #
    # Internal persistence methods
    #
    def checkpoint_shutdown(self, stop, checkpoint, gracetime, hacksessconfcheckpoint):
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
                except Exception as e:
                    self.lm.rawserver_nonfatalerrorfunc(e)

            # Checkpoint all Downloads and stop NetworkThread
            if DEBUG or stop:
                print >> sys.stderr, "Session: checkpoint_shutdown"
            self.lm.checkpoint(stop=stop, checkpoint=checkpoint, gracetime=gracetime)
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
        return os.path.join(state_dir, STATEDIR_SESSCONFIG)
    get_default_config_filename = staticmethod(get_default_config_filename)

    def update_trackers(self, id, trackers):
        """ Update the trackers for a download.
        @param id ID of the download for which the trackers need to be updated
        @param trackers A list of tracker urls.
        """
        return self.lm.update_trackers(id, trackers)

# Written by Arno Bakker
# see LICENSE.txt for license information
""" A Session is a running instance of the Tribler Core and the Core's central class. """
import copy
import logging
import os
import socket
from binascii import hexlify

from Tribler.Core import NoDispersyRLock
from Tribler.Core.APIImplementation.LaunchManyCore import TriblerLaunchMany
from Tribler.Core.CacheDB.Notifier import Notifier
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB
from Tribler.Core.SessionConfig import SessionConfigInterface, SessionStartupConfig
from Tribler.Core.Upgrade.upgrade import TriblerUpgrader
from Tribler.Core.exceptions import NotYetImplementedException, OperationNotEnabledByConfigurationException
from Tribler.Core.simpledefs import (NTFY_CHANNELCAST, NTFY_DELETE, NTFY_INSERT, NTFY_METADATA, NTFY_MYPREFERENCES,
                                     NTFY_PEERS, NTFY_TORRENTS, NTFY_UPDATE, NTFY_VOTECAST, STATEDIR_DLPSTATE_DIR,
                                     STATEDIR_METADATA_STORE_DIR, STATEDIR_PEERICON_DIR, STATEDIR_TORRENT_STORE_DIR)


GOTM2CRYPTO = False
try:
    import M2Crypto
    import Tribler.Core.permid as permidmod
    GOTM2CRYPTO = True
except ImportError:
    pass


class Session(SessionConfigInterface):

    """

    A Session is a running instance of the Tribler Core and the Core's central
    class. It implements the SessionConfigInterface which can be used to change
    session parameters at runtime (for selected parameters).

    cf. libtorrent session
    """
    __single = None

    def __init__(self, scfg=None, ignore_singleton=False, autoload_discovery=True):
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

        self._logger = logging.getLogger(self.__class__.__name__)

        self.ignore_singleton = ignore_singleton
        self.sesslock = NoDispersyRLock()

        # Determine startup config to use
        if scfg is None:  # If no override
            scfg = SessionStartupConfig.load()
        else:  # overrides any saved config
            # Work from copy
            scfg = SessionStartupConfig(copy.copy(scfg.sessconfig))

        def create_dir(fullpath):
            if not os.path.isdir(fullpath):
                os.makedirs(fullpath)

        def set_and_create_dir(dirname, setter, default_dir):
            if dirname is None:
                setter(default_dir)
            create_dir(dirname or default_dir)

        state_dir = scfg.get_state_dir()
        set_and_create_dir(state_dir, scfg.set_state_dir, state_dir)

        set_and_create_dir(scfg.get_torrent_store_dir(),
                           scfg.set_torrent_store_dir,
                           os.path.join(scfg.get_state_dir(), STATEDIR_TORRENT_STORE_DIR))

        # metadata store
        set_and_create_dir(scfg.get_metadata_store_dir(),
                           scfg.set_metadata_store_dir,
                           os.path.join(scfg.get_state_dir(), STATEDIR_METADATA_STORE_DIR))

        set_and_create_dir(scfg.get_peer_icon_path(), scfg.set_peer_icon_path,
                           os.path.join(scfg.get_state_dir(), STATEDIR_PEERICON_DIR))

        create_dir(os.path.join(scfg.get_state_dir(), u"sqlite"))

        create_dir(os.path.join(scfg.get_state_dir(), STATEDIR_DLPSTATE_DIR))

        # Reset the nickname to something not related to the host name, it was
        # really silly to have this default on the first place.
        # TODO: Maybe move this to the upgrader?
        if socket.gethostname() in scfg.get_nickname():
            scfg.set_nickname("Tribler user")

        if GOTM2CRYPTO:
            permidmod.init()
            # Set params that depend on state_dir
            #
            # 1. keypair
            #
            pairfilename = scfg.get_permid_keypair_filename()

            if os.access(pairfilename, os.F_OK):
                # May throw exceptions
                self.keypair = permidmod.read_keypair(pairfilename)
            else:
                self.keypair = permidmod.generate_keypair()

                # Save keypair
                pubfilename = os.path.join(scfg.get_state_dir(), 'ecpub.pem')
                permidmod.save_keypair(self.keypair, pairfilename)
                permidmod.save_pub_key(self.keypair, pubfilename)

        if not scfg.get_megacache():
            scfg.set_torrent_checking(0)

        self.sessconfig = scfg.sessconfig
        self.sessconfig.lock = self.sesslock

        self.selected_ports = scfg.selected_ports

        # Claim all random ports
        self.get_listen_port()
        self.get_dispersy_port()
        self.get_mainline_dht_listen_port()
        self.get_videoplayer_port()

        self.get_anon_listen_port()
        self.get_tunnel_community_socks5_listen_ports()

        # Create handler for calling back the user via separate threads
        self.lm = TriblerLaunchMany()
        self.notifier = Notifier(use_pool=True)

        # Checkpoint startup config
        self.save_pstate_sessconfig()

        self.sqlite_db = None

        self.autoload_discovery = autoload_discovery

    def prestart(self):
        """ Pre-starts the session. We check the currently version and upgrades if needed
        before we start everything else.
        """
        # initialize the database
        self.sqlite_db = SQLiteCacheDB(self)
        self.sqlite_db.initialize()
        self.sqlite_db.initial_begin()

        # check and upgrade
        upgrader = TriblerUpgrader(self, self.sqlite_db)
        upgrader.check_and_upgrade()
        return upgrader

    #
    # Class methods
    #
    @staticmethod
    def get_instance(*args, **kw):
        """ Returns the Session singleton if it exists or otherwise
            creates it first, in which case you need to pass the constructor
            params.
            @return Session."""
        if Session.__single is None:
            Session(*args, **kw)
        return Session.__single

    @staticmethod
    def has_instance():
        return Session.__single is not None

    @staticmethod
    def del_instance():
        Session.__single = None

    #
    # Public methods
    #
    def start_download(self, tdef, dcfg=None, initialdlstatus=None, hidden=False):
        """
        Creates a Download object and adds it to the session. The passed
        ContentDef and DownloadStartupConfig are copied into the new Download
        object. The Download is then started and checkpointed.

        If a checkpointed version of the Download is found, that is restarted
        overriding the saved DownloadStartupConfig if "dcfg" is not None.

        @param tdef  A finalized TorrentDef
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
        if self.get_libtorrent():
            return self.lm.add(tdef, dcfg, initialdlstatus=initialdlstatus, hidden=hidden)
        raise OperationNotEnabledByConfigurationException()

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

    def get_download(self, infohash):
        """
        Returns the Download object for this hash.
        @return A Donwload Object.
        """
        # locking by lm
        return self.lm.get_download(infohash)

    def has_download(self, infohash):
        """
        Checks if the torrent download already exists.
        :param infohash: The torrent infohash.
        :return: True or False indicating if the torrent download already exists.
        """
        return self.lm.download_exists(infohash)

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
        self.lm.remove(d, removecontent=removecontent, removestate=removestate, hidden=hidden)

    def remove_download_by_id(self, infohash, removecontent=False, removestate=True):
        """
        @param infohash The Download to remove
        @param removecontent Whether to delete the already downloaded content
        from disk.

        !We can only remove content when the download object is found, otherwise only
        the state is removed.
        """
        downloadList = self.get_downloads()
        for download in downloadList:
            if download.get_def().get_infohash() == infohash:
                self.remove_download(download, removecontent, removestate)
                return

        self.lm.remove_id(infohash)

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
        return str(self.keypair.pub().get_der())

    def get_current_startup_config_copy(self):
        """ Returns a SessionStartupConfig that is a copy of the current runtime
        SessionConfig.
        @return SessionStartupConfig
        """
        # Called by any thread
        with self.sesslock:
            sessconfig = copy.copy(self.sessconfig)
            sessconfig.set_callback(None)
            return SessionStartupConfig(sessconfig=sessconfig)

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
        self.notifier.add_observer(func, subject, changeTypes, objectID, cache=cache)  # already threadsafe

    def remove_observer(self, func):
        """ Remove observer function. No more callbacks will be made.
        @param func The observer function to remove. """
        # Called by any thread
        self.notifier.remove_observer(func)  # already threadsafe

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
        if subject == NTFY_METADATA:
            return self.lm.metadata_db
        elif subject == NTFY_PEERS:
            return self.lm.peer_db
        elif subject == NTFY_TORRENTS:
            return self.lm.torrent_db
        elif subject == NTFY_MYPREFERENCES:
            return self.lm.mypref_db
        elif subject == NTFY_VOTECAST:
            return self.lm.votecast_db
        elif subject == NTFY_CHANNELCAST:
            return self.lm.channelcast_db
        else:
            raise ValueError(u"Cannot open DB subject: %s" % subject)

    def close_dbhandler(self, dbhandler):
        """ Closes the given database connection """
        dbhandler.close()

    def get_statistics(self):
        from Tribler.Core.statistics import TriblerStatistics
        return TriblerStatistics(self).dump_statistics()

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

        # Create engine with network thread
        self.lm.register(self, self.sesslock, autoload_discovery=self.autoload_discovery)

        self.sessconfig.set_callback(self.lm.sessconfig_changed_callback)

    def shutdown(self, checkpoint=True, gracetime=2.0, hacksessconfcheckpoint=True):
        """ Checkpoints the session and closes it, stopping the download engine.
        @param checkpoint Whether to checkpoint the Session state on shutdown.
        @param gracetime Time to allow for graceful shutdown + signoff (seconds).
        """
        # Called by any thread
        self.lm.early_shutdown()
        self.checkpoint_shutdown(stop=True, checkpoint=checkpoint,
                                 gracetime=gracetime, hacksessconfcheckpoint=hacksessconfcheckpoint)

        self.sqlite_db.close()
        self.sqlite_db = None

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
        return os.path.join(self.get_state_dir(), STATEDIR_DLPSTATE_DIR)

    def download_torrentfile(self, infohash=None, usercallback=None, prio=0):
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

        self.lm.rtorrent_handler.download_torrent(None, infohash, user_callback=usercallback, priority=prio)

    def download_torrentfile_from_peer(self, candidate, infohash=None, usercallback=None, prio=0):
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

        self.lm.rtorrent_handler.download_torrent(candidate, infohash, user_callback=usercallback, priority=prio)

    def download_torrentmessage_from_peer(self, candidate, infohash, usercallback, prio=0):
        """ Ask the designated peer to send us the torrentmessage for the torrent
        identified by the passed infohash. If the torrentmessage is succesfully
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

        self.lm.rtorrent_handler.download_torrentmessage(candidate, infohash, usercallback, prio)

    def get_dispersy_instance(self):
        if not self.get_dispersy():
            raise OperationNotEnabledByConfigurationException()

        return self.lm.dispersy

    def get_libtorrent_process(self):
        if not self.get_libtorrent():
            raise OperationNotEnabledByConfigurationException()

        return self.lm.ltmgr

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
        with self.sesslock:
            # Arno: Make checkpoint optional on shutdown. At the moment setting
            # the config at runtime is not possible (see SessionRuntimeConfig)
            # so this has little use, and interferes with our way of
            # changing the startup config, which is to write a new
            # config to disk that will be read at start up.
            if hacksessconfcheckpoint:
                try:
                    self.save_pstate_sessconfig()
                except Exception as e:
                    self._logger.error("save_pstate_sessconfig() failed with error: %s", e)

            # Checkpoint all Downloads and stop NetworkThread
            if stop:
                self._logger.debug("Session: checkpoint_shutdown")
            self.lm.checkpoint(stop=stop, checkpoint=checkpoint, gracetime=gracetime)

    def save_pstate_sessconfig(self):
        """ Save the runtime SessionConfig to disk """
        # Called by any thread
        sscfg = self.get_current_startup_config_copy()
        cfgfilename = Session.get_default_config_filename(sscfg.get_state_dir())
        sscfg.save(cfgfilename)

    def update_trackers(self, infohash, trackers):
        """ Updates the trackers of a torrent.
        :param infohash: infohash of the torrent that needs to be updated
        :param trackers: A list of tracker urls.
        """
        return self.lm.update_trackers(infohash, trackers)

    # New APIs
    def has_collected_torrent(self, infohash):
        """
        Checks if the given torrent infohash exists in the torrent_store database.
        :param infohash: The given infohash binary.
        :return: True or False indicating if we have the torrent.
        """
        if not self.get_torrent_store():
            raise OperationNotEnabledByConfigurationException("torrent_store is not enabled")
        return hexlify(infohash) in self.lm.torrent_store

    def get_collected_torrent(self, infohash):
        """
        Gets the given torrent from the torrent_store database.
        :param infohash: The given infohash binary.
        :return: The torrent data if exists, None otherwise.
        """
        if not self.get_torrent_store():
            raise OperationNotEnabledByConfigurationException("torrent_store is not enabled")
        return self.lm.torrent_store.get(hexlify(infohash))

    def save_collected_torrent(self, infohash, data):
        """
        Saves the given torrent into the torrent_store database.
        :param infohash: The given infohash binary.
        :param data: The torrent file data.
        """
        if not self.get_torrent_store():
            raise OperationNotEnabledByConfigurationException("torrent_store is not enabled")
        self.lm.torrent_store.put(hexlify(infohash), data)

    def search_remote_torrents(self, keywords):
        """
        Searches for remote torrents through SearchCommunity with the given keywords.
        :param keywords: The given keywords.
        :return: The number of requests made.
        """
        if not self.get_enable_torrent_search():
            raise OperationNotEnabledByConfigurationException("torrent_search is not enabled")
        return self.lm.search_manager.search_for_torrents(keywords)

    def search_remote_channels(self, keywords):
        """
        Searches for remote channels through AllChannelCommunity with the given keywords.
        :param keywords: The given keywords.
        """
        if not self.get_enable_channel_search():
            raise OperationNotEnabledByConfigurationException("channel_search is not enabled")
        self.lm.search_manager.search_for_channels(keywords)

    def create_channel(self, name, description, mode=u'open'):
        """
        Creates a new Channel.
        :param name: Name of the Channel.
        :param description: Description of the Channel.
        :param mode: Mode of the Channel ('open', 'semi-open', or 'closed').
        """
        if not self.get_enable_channel_search():
            raise OperationNotEnabledByConfigurationException("channel_search is not enabled")
        self.lm.channel_manager.create_channel(name, description, mode)

    def check_torrent_health(self, infohash):
        """
        Checks the given torrent's health on its trackers.
        :param infohash: The given torrent infohash.
        """
        self.lm.torrent_checker.add_gui_request(infohash)

    def set_max_upload_speed(self, rate):
        """
        Sets the maximum upload rate (kB/s).
        :param rate: The upload rate (kB/s).
        """
        if not self.get_libtorrent():
            raise OperationNotEnabledByConfigurationException("libtorrent is not enabled")
        self.lm.ltmgr.set_upload_rate_limit(rate)

    def set_max_download_speed(self, rate):
        """
        Sets the maximum download rate (kB/s).
        :param rate: The download rate (kB/s).
        """
        if not self.lm.ltmgr:
            raise OperationNotEnabledByConfigurationException("libtorrent is not enabled")
        self.lm.ltmgr.set_download_rate_limit(rate)

    def get_thumbnail_data(self, thumb_hash):
        """
        Gets the thumbnail data.
        :param thumb_hash: The thumbnail SHA1 hash.
        :return: The thumbnail data.
        """
        if not self.lm.metadata_store:
            raise OperationNotEnabledByConfigurationException("libtorrent is not enabled")
        return self.lm.rtorrent_handler.get_metadata(thumb_hash)

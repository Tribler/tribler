"""
A Session is a running instance of the Tribler Core and the Core's central class.

Author(s): Arno Bakker
"""
import errno
import logging
import os
import sys
import time
from binascii import hexlify
from twisted.internet import threads
from twisted.internet.defer import inlineCallbacks, fail
from twisted.python.failure import Failure
from twisted.python.log import addObserver
from twisted.python.threadable import isInIOThread

import Tribler.Core.permid as permid_module
from Tribler.Core import NoDispersyRLock
from Tribler.Core.APIImplementation.LaunchManyCore import TriblerLaunchMany
from Tribler.Core.CacheDB.Notifier import Notifier
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB, DB_FILE_RELATIVE_PATH
from Tribler.Core.Config.tribler_config import TriblerConfig
from Tribler.Core.Modules.restapi.rest_manager import RESTManager
from Tribler.Core.Upgrade.upgrade import TriblerUpgrader
from Tribler.Core.Utilities import torrent_utils
from Tribler.Core.Utilities.crypto_patcher import patch_crypto_be_discovery
from Tribler.Core.exceptions import NotYetImplementedException, OperationNotEnabledByConfigurationException, \
    DuplicateTorrentFileError
from Tribler.Core.simpledefs import (NTFY_CHANNELCAST, NTFY_DELETE, NTFY_INSERT, NTFY_MYPREFERENCES, NTFY_PEERS,
                                     NTFY_TORRENTS, NTFY_UPDATE, NTFY_VOTECAST, STATEDIR_DLPSTATE_DIR)
from Tribler.Core.statistics import TriblerStatistics
from Tribler.dispersy.util import blocking_call_on_reactor_thread

if sys.platform == 'win32':
    SOCKET_BLOCK_ERRORCODE = 10035  # WSAEWOULDBLOCK
else:
    SOCKET_BLOCK_ERRORCODE = errno.EWOULDBLOCK


class Session(object):
    """
    A Session is a running instance of the Tribler Core and the Core's central
    class.

    It is a singleton. It holds a reference to the download manager, LaunchManyCore and it's config.
    """
    __single = None

    def __init__(self, config=None, ignore_singleton=False, autoload_discovery=True):
        """
        A Session object is created which is configured with the Tribler configuration object.

        Only a single session instance can exist at a time in a process.

        :param config: a TriblerConfig object or None, in which case we
        look for a saved session in the default location (state dir). If
        we can't find it, we create a new TriblerConfig() object to
        serve as startup config. Next, the config is saved in the directory
        indicated by its 'state_dir' attribute.
        :param ignore_singleton: for testing purposes only. Enables the existence of multiple
        Session instances.
        :param autoload_discovery: only false in the Tunnel community tests
        """
        addObserver(self.unhandled_error_observer)

        patch_crypto_be_discovery()

        if not ignore_singleton:
            if Session.__single:
                raise RuntimeError("Session is singleton")
            Session.__single = self

        self._logger = logging.getLogger(self.__class__.__name__)

        self.ignore_singleton = ignore_singleton
        self.session_lock = NoDispersyRLock()

        self.config = config or TriblerConfig.load()
        self.get_ports_in_config()
        self.create_state_directory_structure()

        if not config.get_megacache_enabled():
            config.set_torrent_checking_enabled(False)

        self.selected_ports = config.selected_ports

        self.init_keypair()

        self.lm = TriblerLaunchMany()
        self.notifier = Notifier()

        self.sqlite_db = None
        self.upgrader = None
        self.dispersy_member = None

        self.autoload_discovery = autoload_discovery

    def create_state_directory_structure(self):
        """Create directory structure of the state directory."""
        def create_dir(path):
            if not os.path.isdir(path):
                os.makedirs(path)

        def join_state_dir(path):
            return os.path.join(self.config.get_state_dir(), path)

        def create_in_state_dir(path):
            create_dir(join_state_dir(path))

        create_dir(self.config.get_state_dir())
        self.config.set_torrent_store_dir(join_state_dir(u"collected_torrents"))
        create_in_state_dir(self.config.get_torrent_store_dir())
        self.config.set_metadata_store_dir(join_state_dir(u"collected_metadata"))
        create_in_state_dir(self.config.get_metadata_store_dir())
        create_in_state_dir(u"sqlite")
        create_in_state_dir(STATEDIR_DLPSTATE_DIR)

    def get_ports_in_config(self):
        """Claim all required random ports."""
        self.config.get_libtorrent_port()
        self.config.get_dispersy_port()
        self.config.get_mainline_dht_port()
        self.config.get_video_server_port()

        self.config.get_anon_listen_port()
        self.config.get_tunnel_community_socks5_listen_ports()

    def init_keypair(self):
        """
        Set parameters that depend on state_dir.
        """
        permid_module.init()
        # Set params that depend on state_dir
        #
        # 1. keypair
        #
        pair_filename = self.config.get_permid_keypair_filename()
        if os.path.exists(pair_filename):
            self.keypair = permid_module.read_keypair(pair_filename)
        else:
            self.keypair = permid_module.generate_keypair()

            # Save keypair
            public_key_filename = os.path.join(self.config.get_state_dir(), 'ecpub.pem')
            permid_module.save_keypair(self.keypair, pair_filename)
            permid_module.save_pub_key(self.keypair, public_key_filename)

        multichain_pairfilename = self.config.get_multichain_permid_keypair_filename()

        if os.path.exists(multichain_pairfilename):
            self.multichain_keypair = permid_module.read_keypair_multichain(multichain_pairfilename)
        else:
            self.multichain_keypair = permid_module.generate_keypair_multichain()

            # Save keypair
            multichain_pubfilename = os.path.join(self.config.get_state_dir(), 'ecpub_multichain.pem')
            permid_module.save_keypair_multichain(self.multichain_keypair, multichain_pairfilename)
            permid_module.save_pub_key_multichain(self.multichain_keypair, multichain_pubfilename)

    @blocking_call_on_reactor_thread
    def prestart(self):
        """
        Pre-starts the session. We check the current version and upgrade if needed
-       before we start everything else.
        """
        assert isInIOThread()

        db_path = os.path.join(self.config.get_state_dir(), DB_FILE_RELATIVE_PATH)

        self.sqlite_db = SQLiteCacheDB(db_path)
        self.sqlite_db.initialize()
        self.sqlite_db.initial_begin()

        # Start the REST API before the upgrader since we want to send interesting upgrader events over the socket
        if self.config.get_http_api_enabled():
            self.lm.api_manager = RESTManager(self)
            self.lm.api_manager.start()

        self.upgrader = TriblerUpgrader(self, self.sqlite_db)
        self.upgrader.run()
        return self.upgrader

    #
    # Class methods
    #
    @staticmethod
    def get_instance(*args, **kw):
        """
        Returns the Session singleton if it exists or otherwise creates it first, in which
        case you need to pass the constructor params.

        :return: the Session singleton
        """
        if Session.__single is None:
            Session(*args, **kw)
        return Session.__single

    @staticmethod
    def has_instance():
        """
        Check if there exists a Session singleton.
        :return: either True or False.
        """
        return Session.__single is not None

    @staticmethod
    def del_instance():
        """Remove the Session singleton."""
        Session.__single = None

    def unhandled_error_observer(self, event):
        """
        This method is called when an unhandled error in Tribler is observed.
        It broadcasts the tribler_exception event.
        """
        if event['isError']:
            text = ""
            if 'log_legacy' in event and 'log_text' in event:
                text = event['log_text']
            elif 'log_failure' in event:
                text = str(event['log_failure'])

            # There are some errors that we are ignoring.
            # No route to host: this issue is non-critical since Tribler can still function when a request fails.
            if 'socket.error: [Errno 113]' in text:
                self._logger.error("Observed no route to host error (but ignoring)."
                                   "This might indicate a problem with your firewall.")
                return

            # Socket block: this sometimes occurres on Windows and is non-critical.
            if 'socket.error: [Errno %s]' % SOCKET_BLOCK_ERRORCODE in text:
                self._logger.error("Unable to send data due to socket.error %s", SOCKET_BLOCK_ERRORCODE)
                return

            if 'socket.error: [Errno 51]' in text:
                self._logger.error("Could not send data: network is unreachable.")
                return

            if self.lm.api_manager and len(text) > 0:
                self.lm.api_manager.root_endpoint.events_endpoint.on_tribler_exception(text)
                self.lm.api_manager.root_endpoint.state_endpoint.on_tribler_exception(text)

    def start_download_from_uri(self, uri, download_config=None):
        """
        Start a download from an argument. This argument can be of the following type:
        -http: Start a download from a torrent file at the given url.
        -magnet: Start a download from a torrent file by using a magnet link.
        -file: Start a download from a torrent file at given location.

        :param uri: specifies the location of the torrent to be downloaded
        :param download_config: an optional configuration for the download
        :return: a deferred that fires when a download has been added to the Tribler core
        """
        if self.config.get_libtorrent_enabled():
            return self.lm.ltmgr.start_download_from_uri(uri, dconfig=download_config)
        raise OperationNotEnabledByConfigurationException()

    def start_download_from_tdef(self, torrent_definition, download_startup_config=None, hidden=False):
        """
        Creates a Download object and adds it to the session. The passed
        ContentDef and DownloadStartupConfig are copied into the new Download
        object. The Download is then started and checkpointed.

        If a checkpointed version of the Download is found, that is restarted
        overriding the saved DownloadStartupConfig if "download_startup_config" is not None.

        Locking is done by LaunchManyCore.

        :param torrent_definition: a finalized TorrentDef
        :param download_startup_config: a DownloadStartupConfig or None, in which case
        a new DownloadStartupConfig() is created with its default settings
        and the result becomes the runtime config of this Download
        :param hidden: whether this torrent should be added to the mypreference table
        :return: a Download
        """
        if self.config.get_libtorrent_enabled():
            return self.lm.add(torrent_definition, download_startup_config, hidden=hidden)
        raise OperationNotEnabledByConfigurationException()

    def resume_download_from_file(self, filename):
        """
        Recreates Download from resume file.

        Note: this cannot be made into a method of Download, as the Download
        needs to be bound to a session, it cannot exist independently.

        :return: a Download object
        :raises: a NotYetImplementedException
        """
        raise NotYetImplementedException()

    def get_downloads(self):
        """
        Returns a copy of the list of Downloads.

        Locking is done by LaunchManyCore.

        :return: a list of Download objects
        """
        return self.lm.get_downloads()

    def get_download(self, infohash):
        """
        Returns the Download object for this hash.

        Locking is done by LaunchManyCore.

        :return: a Download object
        """
        return self.lm.get_download(infohash)

    def has_download(self, infohash):
        """
        Checks if the torrent download already exists.

        :param infohash: The torrent infohash
        :return: True or False indicating if the torrent download already exists
        """
        return self.lm.download_exists(infohash)

    def remove_download(self, download, remove_content=False, remove_state=True, hidden=False):
        """
        Stops the download and removes it from the session.

        Note that LaunchManyCore locks.

        :param download: the Download to remove
        :param remove_content: whether to delete the already downloaded content from disk
        :param remove_state: whether to delete the metadata files of the downloaded content from disk
        :param hidden: whether this torrent is added to the mypreference table and this entry should be removed
        """
        self.lm.remove(download, removecontent=remove_content, removestate=remove_state, hidden=hidden)

    def remove_download_by_id(self, infohash, remove_content=False, remove_state=True):
        """
        Remove a download by it's infohash.

        We can only remove content when the download object is found, otherwise only
        the state is removed.

        :param infohash: the download to remove
        :param remove_content: whether to delete the already downloaded content from disk
        :param remove_state: whether to remove the metadata files from disk
        """
        download_list = self.get_downloads()
        for download in download_list:
            if download.get_def().get_infohash() == infohash:
                self.remove_download(download, remove_content, remove_state)
                return

        self.lm.remove_id(infohash)

    def set_download_states_callback(self, user_callback, interval=1.0):
        """
        See Download.set_state_callback. Calls user_callback with a list of
        DownloadStates, one for each Download in the Session as first argument.
        The user_callback must return a tuple (when, getpeerlist) that indicates
        when to invoke the callback again (as a number of seconds from now,
        or < 0.0 if not at all) and whether to also include the details of
        the connected peers in the DownloadStates on that next call.

        The callback will be called by a popup thread which can be used
        indefinitely (within reason) by the higher level code.

        :param user_callback: a function adhering to the above spec
        :param interval: time in between the download states callback's
        """
        self.lm.set_download_states_callback(user_callback, interval)

    #
    # Config parameters that only exist at runtime
    #
    def get_permid(self):
        """
        Returns the PermID of the Session, as determined by the
        TriblerConfig.set_permid() parameter. A PermID is a public key.

        :return: the PermID encoded in a string in DER format
        """
        return str(self.keypair.pub().get_der())

    #
    # Notification of events in the Session
    #
    def add_observer(self, observer_function, subject, change_types=[NTFY_UPDATE, NTFY_INSERT, NTFY_DELETE],
                     object_id=None, cache=0):
        """ Add an observer function function to the Session. The observer
        function will be called when one of the specified events (changeTypes)
        occurs on the specified subject.

        The function will be called by a popup thread which can be used indefinitely (within reason)
        by the higher level code. Note that this function is called by any thread and is thread safe.

        :param observer_function: should accept as its first argument
        the subject, as second argument the changeType, as third argument an
        object_id (e.g. the primary key in the observed database) and an
        optional list of arguments.
        :param subject: the subject to observe, one of NTFY_* subjects (see simpledefs).
        :param change_types: the list of events to be notified of one of NTFY_* events.
        :param object_id: The specific object in the subject to monitor (e.g. a
        specific primary key in a database to monitor for updates.)
        :param cache: the time to bundle/cache events matching this function
        """
        self.notifier.add_observer(observer_function, subject, change_types, object_id, cache=cache)

    def remove_observer(self, function):
        """
        Remove observer function. No more callbacks will be made.

        This function is called by any thread and is thread safe.
        :param function: the observer function to remove.
        """
        self.notifier.remove_observer(function)

    def open_dbhandler(self, subject):
        """
        Opens a connection to the specified database. Only the thread calling this method may
        use this connection. The connection must be closed with close_dbhandler() when this
        thread exits. This function is called by any thread.

        ;param subject: the database to open. Must be one of the subjects specified here.
        :return: a reference to a DBHandler class for the specified subject or
        None when the Session was not started with megacache enabled.
        """
        if not self.config.get_megacache_enabled():
            raise OperationNotEnabledByConfigurationException()

        if subject == NTFY_PEERS:
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

    @staticmethod
    def close_dbhandler(database_handler):
        """Closes the given database connection."""
        database_handler.close()

    def get_tribler_statistics(self):
        """Return a dictionary with general Tribler statistics."""
        return TriblerStatistics(self).get_tribler_statistics()

    def get_dispersy_statistics(self):
        """Return a dictionary with general Dispersy statistics."""
        return TriblerStatistics(self).get_dispersy_statistics()

    def get_community_statistics(self):
        """Return a dictionary with general communities statistics."""
        return TriblerStatistics(self).get_community_statistics()

    #
    # Persistence and shutdown
    #
    def load_checkpoint(self):
        """
        Restart Downloads from a saved checkpoint, if any. Note that we fetch information from the user download
        choices since it might be that a user has stopped a download. In that case, the download should not be
        resumed immediately when being loaded by libtorrent.
        """
        self.lm.load_checkpoint()

    @blocking_call_on_reactor_thread
    def start_database(self):
        """Start the SQLite database."""
        db_path = os.path.join(self.config.get_state_dir(), DB_FILE_RELATIVE_PATH)

        self.sqlite_db = SQLiteCacheDB(db_path)
        self.sqlite_db.initialize()
        self.sqlite_db.initial_begin()

    def checkpoint(self):
        """
        Saves the internal session state to the Session's state dir.

        Checkpoints the downloads via the LaunchManyCore instance. This function is called by any thread.
        """
        self.lm.checkpoint_downloads()

    @blocking_call_on_reactor_thread
    def start(self):
        """
        Start a Tribler session by initializing the LaunchManyCore class, opening the database and running the upgrader.
        Returns a deferred that fires when the Tribler session is ready for use.
        """
        # Start the REST API before the upgrader since we want to send interesting upgrader events over the socket
        if self.config.get_http_api_enabled():
            self.lm.api_manager = RESTManager(self)
            self.lm.api_manager.start()

        self.start_database()

        if self.config.get_upgrader_enabled():
            self.upgrader = TriblerUpgrader(self, self.sqlite_db)
            self.upgrader.run()

        startup_deferred = self.lm.register(self, self.session_lock)

        def load_checkpoint(_):
            if self.config.get_libtorrent_enabled():
                self.load_checkpoint()

        return startup_deferred.addCallback(load_checkpoint)

    @blocking_call_on_reactor_thread
    def shutdown(self):
        """
        Checkpoints the session and closes it, stopping the download engine.
        This method has to be called from the reactor thread.
        """
        assert isInIOThread()

        @inlineCallbacks
        def on_early_shutdown_complete(_):
            """
            Callback that gets called when the early shutdown has been completed.
            Continues the shutdown procedure that is dependant on the early shutdown.
            :param _: ignored parameter of the Deferred
            """
            self.config.write()
            yield self.checkpoint_downloads()
            self.lm.shutdown_downloads()
            self.lm.network_shutdown()

            if self.sqlite_db:
                self.sqlite_db.close()
            self.sqlite_db = None

        return self.lm.early_shutdown().addCallback(on_early_shutdown_complete)

    def has_shutdown(self):
        """
        Whether the Session has completely shutdown, i.e., its internal
        threads are finished and it is safe to quit the process the Session
        is running in.

        :return: a boolean.
        """
        return self.lm.sessdoneflag.isSet()

    def get_downloads_pstate_dir(self):
        """
        Returns the directory in which to checkpoint the Downloads in this
        Session. This function is called by the network thread.
        """
        return os.path.join(self.config.get_state_dir(), STATEDIR_DLPSTATE_DIR)

    def download_torrentfile(self, infohash=None, user_callback=None, priority=0):
        """
        Try to download the torrent file without a known source. A possible source could be the DHT.
        If the torrent is received successfully, the user_callback method is called with the infohash as first
        and the contents of the torrent file (bencoded dict) as second parameter. If the torrent could not
        be obtained, the callback is not called. The torrent will have been added to the TorrentDBHandler (if enabled)
        at the time of the call.

        :param infohash: the infohash of the torrent
        :param user_callback: a function adhering to the above spec
        :param priority: the priority of this download
        """
        if not self.lm.rtorrent_handler:
            raise OperationNotEnabledByConfigurationException()

        self.lm.rtorrent_handler.download_torrent(None, infohash, user_callback=user_callback, priority=priority)

    def download_torrentfile_from_peer(self, candidate, infohash=None, user_callback=None, priority=0):
        """
        Ask the designated peer to send us the torrent file for the torrent
        identified by the passed infohash. If the torrent is successfully
        received, the user_callback method is called with the infohash as first
        and the contents of the torrent file (bencoded dict) as second parameter.
        If the torrent could not be obtained, the callback is not called.
        The torrent will have been added to the TorrentDBHandler (if enabled)
        at the time of the call.

        :param candidate: the designated peer
        :param infohash: the infohash of the torrent
        :param user_callback: a function adhering to the above spec
        :param priority: priority of this request
        """
        if not self.lm.rtorrent_handler:
            raise OperationNotEnabledByConfigurationException()

        self.lm.rtorrent_handler.download_torrent(candidate, infohash, user_callback=user_callback, priority=priority)

    def download_torrentmessage_from_peer(self, candidate, infohash, user_callback, priority=0):
        """
        Ask the designated peer to send us the torrent message for the torrent
        identified by the passed infohash. If the torrent message is successfully
        received, the user_callback method is called with the infohash as first
        and the contents of the torrent file (bencoded dict) as second parameter.
        If the torrent could not be obtained, the callback is not called.
        The torrent will have been added to the TorrentDBHandler (if enabled)
        at the time of the call.

        :param candidate: the designated peer
        :param infohash: the infohash of the torrent
        :param user_callback: a function adhering to the above spec
        :param priority: priority of this request
        """
        if not self.lm.rtorrent_handler:
            raise OperationNotEnabledByConfigurationException()

        self.lm.rtorrent_handler.download_torrentmessage(candidate, infohash, user_callback, priority)

    def get_dispersy_instance(self):
        if not self.config.get_dispersy_enabled():
            raise OperationNotEnabledByConfigurationException()

        return self.lm.dispersy

    def get_libtorrent_process(self):
        if not self.config.get_libtorrent_enabled():
            raise OperationNotEnabledByConfigurationException()

        return self.lm.ltmgr

    #
    # Internal persistence methods
    #
    def checkpoint_downloads(self):
        """Checkpoints the downloads."""
        return self.lm.checkpoint_downloads()

    def update_trackers(self, infohash, trackers):
        """
        Updates the trackers of a torrent.

        :param infohash: infohash of the torrent that needs to be updated
        :param trackers: A list of tracker urls
        """
        return self.lm.update_trackers(infohash, trackers)

    def has_collected_torrent(self, infohash):
        """
        Checks if the given torrent infohash exists in the torrent_store database.

        :param infohash: The given infohash binary
        :return: True or False indicating if we have the torrent
        """
        if not self.config.get_torrent_store_enabled():
            raise OperationNotEnabledByConfigurationException("torrent_store is not enabled")
        return hexlify(infohash) in self.lm.torrent_store

    def get_collected_torrent(self, infohash):
        """
        Gets the given torrent from the torrent_store database.

        :param infohash: the given infohash binary
        :return: the torrent data if exists, None otherwise
        """
        if not self.config.get_torrent_store_enabled():
            raise OperationNotEnabledByConfigurationException("torrent_store is not enabled")
        return self.lm.torrent_store.get(hexlify(infohash))

    def save_collected_torrent(self, infohash, data):
        """
        Saves the given torrent into the torrent_store database.

        :param infohash: the given infohash binary
        :param data: the torrent file data
        """
        if not self.config.get_torrent_store_enabled():
            raise OperationNotEnabledByConfigurationException("torrent_store is not enabled")
        self.lm.torrent_store.put(hexlify(infohash), data)

    def delete_collected_torrent(self, infohash):
        """
        Deletes the given torrent from the torrent_store database.

        :param infohash: the given infohash binary
        """
        if not self.config.get_torrent_store_enabled():
            raise OperationNotEnabledByConfigurationException("torrent_store is not enabled")

        del self.lm.torrent_store[hexlify(infohash)]

    def search_remote_torrents(self, keywords):
        """
        Searches for remote torrents through SearchCommunity with the given keywords.

        :param keywords: the given keywords
        :return: the number of requests made
        """
        if not self.config.get_torrent_search_enabled():
            raise OperationNotEnabledByConfigurationException("torrent_search is not enabled")
        return self.lm.search_manager.search_for_torrents(keywords)

    def search_remote_channels(self, keywords):
        """
        Searches for remote channels through AllChannelCommunity with the given keywords.

        :param keywords: the given keywords
        """
        if not self.config.get_channel_search_enabled():
            raise OperationNotEnabledByConfigurationException("channel_search is not enabled")
        self.lm.search_manager.search_for_channels(keywords)

    @staticmethod
    def create_torrent_file(file_path_list, params={}):
        """
        Creates a torrent file.

        :param file_path_list: files to add in torrent file
        :param params: optional parameters for torrent file
        :return: a Deferred that fires when the torrent file has been created
        """
        return threads.deferToThread(torrent_utils.create_torrent_file, file_path_list, params)

    def create_channel(self, name, description, mode=u'closed'):
        """
        Creates a new Channel.

        :param name: name of the Channel
        :param description: description of the Channel
        :param mode: mode of the Channel ('open', 'semi-open', or 'closed')
        :return: a channel ID
        :raises a DuplicateChannelNameError if name already exists
        """
        return self.lm.channel_manager.create_channel(name, description, mode)

    def add_torrent_def_to_channel(self, channel_id, torrent_def, extra_info={}, forward=True):
        """
        Adds a TorrentDef to a Channel.

        :param channel_id: id of the Channel to add the Torrent to
        :param torrent_def: definition of the Torrent to add
        :param extra_info: description of the Torrent to add
        :param forward: when True the messages are forwarded (as defined by their message
         destination policy) to other nodes in the community. This parameter should (almost always)
         be True, its inclusion is mostly to allow certain debugging scenarios
        """
        # Make sure that this new torrent_def is also in collected torrents
        self.lm.rtorrent_handler.save_torrent(torrent_def)

        channelcast_db = self.open_dbhandler(NTFY_CHANNELCAST)
        if channelcast_db.hasTorrent(channel_id, torrent_def.infohash):
            raise DuplicateTorrentFileError("This torrent file already exists in your channel.")

        dispersy_cid = str(channelcast_db.getDispersyCIDFromChannelId(channel_id))
        community = self.get_dispersy_instance().get_community(dispersy_cid)

        community._disp_create_torrent(
            torrent_def.infohash,
            long(time.time()),
            torrent_def.get_name_as_unicode(),
            tuple(torrent_def.get_files_with_length()),
            torrent_def.get_trackers_as_single_tuple(),
            forward=forward)

        if 'description' in extra_info:
            desc = extra_info['description'].strip()
            if desc != '':
                data = channelcast_db.getTorrentFromChannelId(channel_id, torrent_def.infohash, ['ChannelTorrents.id'])
                community.modifyTorrent(data, {'description': desc}, forward=forward)

    def check_torrent_health(self, infohash, timeout=20, scrape_now=False):
        """
        Checks the given torrent's health on its trackers.

        :param infohash: the given torrent infohash
        :param timeout: time to wait while performing the request
        :param scrape_now: flag to scrape immediately
        """
        if self.lm.torrent_checker:
            return self.lm.torrent_checker.add_gui_request(infohash, timeout=timeout, scrape_now=scrape_now)
        return fail(Failure(RuntimeError("Torrent checker not available")))

    def get_thumbnail_data(self, thumb_hash):
        """
        Gets the thumbnail data.

        :param thumb_hash: the thumbnail SHA1 hash
        :return: the thumbnail data
        """
        if not self.lm.metadata_store:
            raise OperationNotEnabledByConfigurationException("libtorrent is not enabled")
        return self.lm.rtorrent_handler.get_metadata(thumb_hash)

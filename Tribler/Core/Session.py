"""
A Session is a running instance of the Tribler Core and the Core's central class.

Author(s): Arno Bakker
"""
from __future__ import absolute_import

import errno
import logging
import os
import sys
from threading import RLock

from twisted.internet import threads
from twisted.internet.defer import fail, inlineCallbacks
from twisted.python.failure import Failure
from twisted.python.log import addObserver
from twisted.python.threadable import isInIOThread

import Tribler.Core.permid as permid_module
from Tribler.Core.APIImplementation.LaunchManyCore import TriblerLaunchMany
from Tribler.Core.Config.tribler_config import TriblerConfig
from Tribler.Core.Modules.restapi.rest_manager import RESTManager
from Tribler.Core.Notifier import Notifier
from Tribler.Core.Upgrade.upgrade import TriblerUpgrader
from Tribler.Core.Utilities import torrent_utils
from Tribler.Core.Utilities.crypto_patcher import patch_crypto_be_discovery
from Tribler.Core.exceptions import NotYetImplementedException, OperationNotEnabledByConfigurationException
from Tribler.Core.simpledefs import NTFY_DELETE, NTFY_INSERT, NTFY_TRIBLER, NTFY_UPDATE, STATEDIR_CHANNELS_DIR, \
    STATEDIR_DLPSTATE_DIR, STATEDIR_WALLET_DIR, STATE_LOAD_CHECKPOINTS, STATE_READABLE_STARTED, STATE_SHUTDOWN, \
    STATE_START_API, STATE_UPGRADING_READABLE
from Tribler.Core.simpledefs import STATEDIR_DB_DIR
from Tribler.Core.statistics import TriblerStatistics

try:
    long  # pylint: disable=long-builtin
except NameError:
    long = int  # pylint: disable=redefined-builtin

if sys.platform == 'win32':
    SOCKET_BLOCK_ERRORCODE = 10035  # WSAEWOULDBLOCK
else:
    SOCKET_BLOCK_ERRORCODE = errno.EWOULDBLOCK


class Session(object):
    """
    A Session is a running instance of the Tribler Core and the Core's central class.
    """
    __single = None

    def __init__(self, config=None, autoload_discovery=True):
        """
        A Session object is created which is configured with the Tribler configuration object.

        Only a single session instance can exist at a time in a process.

        :param config: a TriblerConfig object or None, in which case we
        look for a saved session in the default location (state dir). If
        we can't find it, we create a new TriblerConfig() object to
        serve as startup config. Next, the config is saved in the directory
        indicated by its 'state_dir' attribute.
        :param autoload_discovery: only false in the Tunnel community tests
        """
        addObserver(self.unhandled_error_observer)

        patch_crypto_be_discovery()

        self._logger = logging.getLogger(self.__class__.__name__)

        self.session_lock = RLock()

        self.config = config or TriblerConfig()
        self._logger.info("Session is using state directory: %s", self.config.get_state_dir())

        self.get_ports_in_config()
        self.create_state_directory_structure()

        self.selected_ports = self.config.selected_ports

        self.init_keypair()

        self.lm = TriblerLaunchMany()
        self.notifier = Notifier()

        self.upgrader_enabled = True
        self.upgrader = None
        self.readable_status = ''  # Human-readable string to indicate the status during startup/shutdown of Tribler

        self.autoload_discovery = autoload_discovery


    def create_state_directory_structure(self):
        """Create directory structure of the state directory."""

        def create_dir(path):
            if not os.path.isdir(path):
                os.makedirs(path)

        def create_in_state_dir(path):
            create_dir(os.path.join(self.config.get_state_dir(), path))

        create_dir(self.config.get_state_dir())
        create_in_state_dir(STATEDIR_DB_DIR)
        create_in_state_dir(STATEDIR_DLPSTATE_DIR)
        create_in_state_dir(STATEDIR_WALLET_DIR)
        create_in_state_dir(STATEDIR_CHANNELS_DIR)

    def get_ports_in_config(self):
        """Claim all required random ports."""
        self.config.get_libtorrent_port()
        self.config.get_video_server_port()

        self.config.get_anon_listen_port()
        self.config.get_tunnel_community_socks5_listen_ports()

    def init_keypair(self):
        """
        Set parameters that depend on state_dir.
        """
        trustchain_pairfilename = self.config.get_trustchain_keypair_filename()
        if os.path.exists(trustchain_pairfilename):
            self.trustchain_keypair = permid_module.read_keypair_trustchain(trustchain_pairfilename)
        else:
            self.trustchain_keypair = permid_module.generate_keypair_trustchain()

            # Save keypair
            trustchain_pubfilename = os.path.join(self.config.get_state_dir(), 'ecpub_multichain.pem')
            permid_module.save_keypair_trustchain(self.trustchain_keypair, trustchain_pairfilename)
            permid_module.save_pub_key_trustchain(self.trustchain_keypair, trustchain_pubfilename)

        trustchain_testnet_pairfilename = self.config.get_trustchain_testnet_keypair_filename()
        if os.path.exists(trustchain_testnet_pairfilename):
            self.trustchain_testnet_keypair = permid_module.read_keypair_trustchain(trustchain_testnet_pairfilename)
        else:
            self.trustchain_testnet_keypair = permid_module.generate_keypair_trustchain()

            # Save keypair
            trustchain_testnet_pubfilename = os.path.join(self.config.get_state_dir(), 'ecpub_trustchain_testnet.pem')
            permid_module.save_keypair_trustchain(self.trustchain_testnet_keypair, trustchain_testnet_pairfilename)
            permid_module.save_pub_key_trustchain(self.trustchain_testnet_keypair, trustchain_testnet_pubfilename)

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
            if 'socket.error' in text and '[Errno 113]' in text:
                self._logger.error("Observed no route to host error (but ignoring)."
                                   "This might indicate a problem with your firewall.")
                return

            # Socket block: this sometimes occurres on Windows and is non-critical.
            if 'socket.error' in text and '[Errno %s]' % SOCKET_BLOCK_ERRORCODE in text:
                self._logger.error("Unable to send data due to socket.error %s", SOCKET_BLOCK_ERRORCODE)
                return

            if 'socket.error' in text and '[Errno 51]' in text:
                self._logger.error("Could not send data: network is unreachable.")
                return

            if 'socket.error' in text and '[Errno 16]' in text:
                self._logger.error("Could not send data: socket is busy.")
                return

            if 'socket.error' in text and '[Errno 11001]' in text:
                self._logger.error("Unable to perform DNS lookup.")
                return

            if 'socket.error' in text and '[Errno 10053]' in text:
                self._logger.error("An established connection was aborted by the software in your host machine.")
                return

            if 'socket.error' in text and '[Errno 10054]' in text:
                self._logger.error("Connection forcibly closed by the remote host.")
                return

            if 'exceptions.ValueError: Invalid DNS-ID' in text:
                self._logger.error("Invalid DNS-ID")
                return

            if 'twisted.web._newclient.ResponseNeverReceived' in text:
                self._logger.error("Internal Twisted response error, consider updating your Twisted version.")
                return

            if 'twisted.internet.error.AlreadyCalled' in text:
                self._logger.error("Tried to cancel an already called event\n%s", text)
                return

            # We already have a check for invalid infohash when adding a torrent, but if somehow we get this
            # error then we simply log and ignore it.
            if 'exceptions.RuntimeError: invalid info-hash' in text:
                self._logger.error("Invalid info-hash found")
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

    def start_download_from_tdef(self, torrent_definition, download_startup_config=None, pstate=None, hidden=False):
        """
        Creates a Download object and adds it to the session. The passed
        ContentDef and DownloadStartupConfig are copied into the new Download
        object. The Download is then started and checkpointed.

        If a checkpointed version of the Download is found, that is restarted
        overriding the saved DownloadStartupConfig if "download_startup_config" is not None.

        Locking is done by LaunchManyCore.

        :param torrent_definition: a TorrentDef
        :param download_startup_config: a DownloadStartupConfig or None, in which case
        a new DownloadStartupConfig() is created with its default settings
        and the result becomes the runtime config of this Download
        :param hidden: whether this torrent should be added to the mypreference table
        :return: a Download
        """
        if self.config.get_libtorrent_enabled():
            return self.lm.add(torrent_definition, download_startup_config, pstate=pstate, hidden=hidden)
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
        # locking by lm
        return self.lm.remove(download, removecontent=remove_content, removestate=remove_state, hidden=hidden)

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
                return self.remove_download(download, remove_content, remove_state)

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
    # Notification of events in the Session
    #
    def add_observer(self, observer_function, subject, change_types=None, object_id=None, cache=0):
        """
        Add an observer function function to the Session. The observer
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
        change_types = change_types or [NTFY_UPDATE, NTFY_INSERT, NTFY_DELETE]
        self.notifier.add_observer(observer_function, subject, change_types, object_id, cache=cache)

    def remove_observer(self, function):
        """
        Remove observer function. No more callbacks will be made.

        This function is called by any thread and is thread safe.
        :param function: the observer function to remove.
        """
        self.notifier.remove_observer(function)

    def get_tribler_statistics(self):
        """Return a dictionary with general Tribler statistics."""
        return TriblerStatistics(self).get_tribler_statistics()

    def get_ipv8_statistics(self):
        """Return a dictionary with IPv8 statistics."""
        return TriblerStatistics(self).get_ipv8_statistics()

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

    def checkpoint(self):
        """
        Saves the internal session state to the Session's state dir.

        Checkpoints the downloads via the LaunchManyCore instance. This function is called by any thread.
        """
        self.lm.checkpoint_downloads()

    def start(self):
        """
        Start a Tribler session by initializing the LaunchManyCore class, opening the database and running the upgrader.
        Returns a deferred that fires when the Tribler session is ready for use.
        """
        # Start the REST API before the upgrader since we want to send interesting upgrader events over the socket
        if self.config.get_http_api_enabled():
            self.lm.api_manager = RESTManager(self)
            self.readable_status = STATE_START_API
            self.lm.api_manager.start()

        if self.upgrader_enabled:
            self.upgrader = TriblerUpgrader(self)
            self.readable_status = STATE_UPGRADING_READABLE
            self.upgrader.run()

        startup_deferred = self.lm.register(self, self.session_lock)

        def load_checkpoint(_):
            if self.config.get_libtorrent_enabled():
                self.readable_status = STATE_LOAD_CHECKPOINTS
                self.load_checkpoint()
            self.readable_status = STATE_READABLE_STARTED

        return startup_deferred.addCallback(load_checkpoint)

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
            self.notify_shutdown_state("Saving configuration...")
            self.config.write()

            self.notify_shutdown_state("Checkpointing Downloads...")
            yield self.checkpoint_downloads()

            self.notify_shutdown_state("Shutting down Downloads...")
            self.lm.shutdown_downloads()

            self.notify_shutdown_state("Shutting down Network...")
            self.lm.network_shutdown()

            if self.lm.mds:
                self.notify_shutdown_state("Shutting down Metadata Store...")
                self.lm.mds.shutdown()

            if self.upgrader:
                self.upgrader.shutdown()

            # We close the API manager as late as possible during shutdown.
            if self.lm.api_manager is not None:
                self.notify_shutdown_state("Shutting down API Manager...")
                yield self.lm.api_manager.stop()
            self.lm.api_manager = None

        # Indicates we are shutting down core. With this environment variable set
        # to 'TRUE', RESTManager will no longer accepts any new requests.
        os.environ['TRIBLER_SHUTTING_DOWN'] = "TRUE"

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

    def get_ipv8_instance(self):
        if not self.config.get_ipv8_enabled():
            raise OperationNotEnabledByConfigurationException()

        return self.lm.ipv8

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

    @staticmethod
    def create_torrent_file(file_path_list, params=None):
        """
        Creates a torrent file.

        :param file_path_list: files to add in torrent file
        :param params: optional parameters for torrent file
        :return: a Deferred that fires when the torrent file has been created
        """
        params = params or {}
        return threads.deferToThread(torrent_utils.create_torrent_file, file_path_list, params)

    def create_channel(self, name, description, mode=u'closed'):
        """
        Creates a new Channel.

        :param name: name of the Channel
        :param description: description of the Channel
        :param mode: mode of the Channel ('open', 'semi-open', or 'closed')
        :return: a channel ID
        :raises a DuplicateChannelIdError if name already exists
        """
        return self.lm.channel_manager.create_channel(name, description, mode)

    def check_torrent_health(self, infohash, timeout=20, scrape_now=False):
        """
        Checks the given torrent's health on its trackers.

        :param infohash: the given torrent infohash
        :param timeout: time to wait while performing the request
        :param scrape_now: flag to scrape immediately
        """
        if self.lm.torrent_checker:
            return self.lm.torrent_checker.check_torrent_health(infohash, timeout=timeout, scrape_now=scrape_now)
        return fail(Failure(RuntimeError("Torrent checker not available")))

    def notify_shutdown_state(self, state):
        self._logger.info("Tribler shutdown state notification:%s", state)
        self.notifier.notify(NTFY_TRIBLER, STATE_SHUTDOWN, None, state)

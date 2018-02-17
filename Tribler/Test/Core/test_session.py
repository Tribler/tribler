from binascii import hexlify, unhexlify

from nose.tools import raises
from twisted.internet.defer import Deferred, inlineCallbacks

from Tribler.Core.Config.tribler_config import TriblerConfig
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Session import Session, SOCKET_BLOCK_ERRORCODE
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.exceptions import OperationNotEnabledByConfigurationException, DuplicateTorrentFileError
from Tribler.Core.leveldbstore import LevelDbStore
from Tribler.Core.simpledefs import NTFY_CHANNELCAST, SIGNAL_CHANNEL, SIGNAL_ON_CREATED
from Tribler.Test.Core.base_test import TriblerCoreTest, MockObject
from Tribler.Test.common import TORRENT_UBUNTU_FILE
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.twisted_thread import deferred
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestSession(TriblerCoreTest):

    @raises(OperationNotEnabledByConfigurationException)
    def test_torrent_store_not_enabled(self):
        config = TriblerConfig()
        config.set_state_dir(self.getStateDir())
        config.set_torrent_store_enabled(False)
        session = Session(config)
        session.delete_collected_torrent(None)

    def test_torrent_store_delete(self):
        config = TriblerConfig()
        config.set_state_dir(self.getStateDir())
        config.set_torrent_store_enabled(True)
        session = Session(config)
        # Manually set the torrent store as we don't want to start the session.
        session.lm.torrent_store = LevelDbStore(session.config.get_torrent_store_dir())
        session.lm.torrent_store[hexlify("fakehash")] = "Something"
        self.assertEqual("Something", session.lm.torrent_store[hexlify("fakehash")])
        session.delete_collected_torrent("fakehash")

        raised_key_error = False
        # This structure is needed because if we add a @raises above the test, we cannot close the DB
        # resulting in a dirty reactor.
        try:
            self.assertRaises(KeyError,session.lm.torrent_store[hexlify("fakehash")])
        except KeyError:
            raised_key_error = True
        finally:
            session.lm.torrent_store.close()

        self.assertTrue(raised_key_error)

    def test_create_channel(self):
        """
        Test the pass through function of Session.create_channel to the ChannelManager.
        """

        class LmMock(object):
            class ChannelManager(object):
                invoked_name = None
                invoked_desc = None
                invoked_mode = None

                def create_channel(self, name, description, mode=u"closed"):
                    self.invoked_name = name
                    self.invoked_desc = description
                    self.invoked_mode = mode

            channel_manager = ChannelManager()

        config = TriblerConfig()
        config.set_state_dir(self.getStateDir())
        session = Session(config)
        session.lm = LmMock()
        session.lm.api_manager = None

        session.create_channel("name", "description", "open")
        self.assertEqual(session.lm.channel_manager.invoked_name, "name")
        self.assertEqual(session.lm.channel_manager.invoked_desc, "description")
        self.assertEqual(session.lm.channel_manager.invoked_mode, "open")


class TestSessionAsServer(TestAsServer):

    def setUpPreSession(self):
        super(TestSessionAsServer, self).setUpPreSession()
        self.config.set_megacache_enabled(True)
        self.config.set_torrent_collecting_enabled(True)
        self.config.set_channel_search_enabled(True)
        self.config.set_dispersy_enabled(True)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        yield super(TestSessionAsServer, self).setUp(autoload_discovery=autoload_discovery)
        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)
        self.called = None

    def mock_endpoints(self):
        self.session.lm.api_manager = MockObject()
        self.session.lm.api_manager.stop = lambda: None
        self.session.lm.api_manager.root_endpoint = MockObject()
        self.session.lm.api_manager.root_endpoint.events_endpoint = MockObject()
        self.session.lm.api_manager.root_endpoint.state_endpoint = MockObject()

    def test_unhandled_error_observer(self):
        """
        Test the unhandled error observer
        """
        self.mock_endpoints()

        expected_text = ""

        def on_tribler_exception(exception_text):
            self.assertEqual(exception_text, expected_text)

        on_tribler_exception.called = 0
        self.session.lm.api_manager.root_endpoint.events_endpoint.on_tribler_exception = on_tribler_exception
        self.session.lm.api_manager.root_endpoint.state_endpoint.on_tribler_exception = on_tribler_exception
        expected_text = "abcd"
        self.session.unhandled_error_observer({'isError': True, 'log_legacy': True, 'log_text': 'abcd'})
        expected_text = "defg"
        self.session.unhandled_error_observer({'isError': True, 'log_failure': 'defg'})

    def test_error_observer_ignored_error(self):
        """
        Testing whether some errors are ignored (like socket errors)
        """
        self.mock_endpoints()

        def on_tribler_exception(_):
            raise RuntimeError("This method cannot be called!")

        self.session.lm.api_manager.root_endpoint.events_endpoint.on_tribler_exception = on_tribler_exception
        self.session.lm.api_manager.root_endpoint.state_endpoint.on_tribler_exception = on_tribler_exception

        self.session.unhandled_error_observer({'isError': True, 'log_failure': 'socket.error: [Errno 113]'})
        self.session.unhandled_error_observer({'isError': True, 'log_failure': 'socket.error: [Errno 51]'})
        self.session.unhandled_error_observer({'isError': True,
                                               'log_failure': 'socket.error: [Errno %s]' % SOCKET_BLOCK_ERRORCODE})
        self.session.unhandled_error_observer({'isError': True, 'log_failure': 'exceptions.ValueError: Invalid DNS-ID'})


    @deferred(timeout=10)
    def test_add_torrent_def_to_channel(self):
        """
        Test whether adding a torrent def to a channel works
        """
        test_deferred = Deferred()

        torrent_def = TorrentDef.load(TORRENT_UBUNTU_FILE)

        @blocking_call_on_reactor_thread
        def on_channel_created(subject, change_type, object_id, channel_data):
            channel_id = self.channel_db_handler.getMyChannelId()
            self.session.add_torrent_def_to_channel(channel_id, torrent_def, {"description": "iso"}, forward=False)
            self.assertTrue(self.channel_db_handler.hasTorrent(channel_id, torrent_def.get_infohash()))
            test_deferred.callback(None)

        self.session.add_observer(on_channel_created, SIGNAL_CHANNEL, [SIGNAL_ON_CREATED])
        self.session.create_channel("name", "description", "open")

        return test_deferred

    @deferred(timeout=10)
    def test_add_torrent_def_to_channel_duplicate(self):
        """
        Test whether adding a torrent def twice to a channel raises an exception
        """
        test_deferred = Deferred()

        torrent_def = TorrentDef.load(TORRENT_UBUNTU_FILE)

        @blocking_call_on_reactor_thread
        def on_channel_created(subject, change_type, object_id, channel_data):
            channel_id = self.channel_db_handler.getMyChannelId()
            try:
                self.session.add_torrent_def_to_channel(channel_id, torrent_def, forward=False)
                self.session.add_torrent_def_to_channel(channel_id, torrent_def, forward=False)
            except DuplicateTorrentFileError:
                test_deferred.callback(None)

        self.session.add_observer(on_channel_created, SIGNAL_CHANNEL, [SIGNAL_ON_CREATED])
        self.session.create_channel("name", "description", "open")

        return test_deferred

    def test_load_checkpoint(self):
        self.load_checkpoint_called = False

        def verify_load_checkpoint_call():
            self.load_checkpoint_called = True

        self.session.lm.load_checkpoint = verify_load_checkpoint_call
        self.session.load_checkpoint()
        self.assertTrue(self.load_checkpoint_called)

    @raises(OperationNotEnabledByConfigurationException)
    def test_get_libtorrent_process_not_enabled(self):
        """
        When libtorrent is not enabled, an exception should be thrown when getting the libtorrent instance.
        """
        self.session.config.get_libtorrent_enabled = lambda: False
        self.session.get_libtorrent_process()

    @raises(OperationNotEnabledByConfigurationException)
    def test_open_dbhandler(self):
        """
        Opening the database without the megacache enabled should raise an exception.
        """
        self.session.config.get_megacache_enabled = lambda: False
        self.session.open_dbhandler("x")

    def test_close_dbhandler(self):
        handler = MockObject()
        self.called = False

        def verify_close_called():
            self.called = True
        handler.close = verify_close_called
        Session.close_dbhandler(handler)
        self.assertTrue(self.called)

    def test_download_torrentfile(self):
        """
        When libtorrent is not enabled, an exception should be thrown when downloading a torrentfile.
        """
        self.called = False

        def verify_download_torrentfile_call(*args, **kwargs):
            self.called = True
        self.session.lm.rtorrent_handler.download_torrent = verify_download_torrentfile_call

        self.session.download_torrentfile()
        self.assertTrue(self.called)

    def test_download_torrentfile_from_peer(self):
        """
        When libtorrent is not enabled, an exception should be thrown when downloading a torrentfile from a peer.
        """
        self.called = False

        def verify_download_torrentfile_call(*args, **kwargs):
            self.called = True
        self.session.lm.rtorrent_handler.download_torrent = verify_download_torrentfile_call

        self.session.download_torrentfile_from_peer("a")
        self.assertTrue(self.called)

    def test_download_torrentmessage_from_peer(self):
        """
        When libtorrent is not enabled, an exception should be thrown when downloading a torrentfile from a peer.
        """
        self.called = False

        def verify_download_torrentmessage_call(*args, **kwargs):
            self.called = True
        self.session.lm.rtorrent_handler.download_torrentmessage = verify_download_torrentmessage_call

        self.session.download_torrentmessage_from_peer("a", "b", "c")
        self.assertTrue(self.called)

    def test_get_permid(self):
        """
        Retrieving the string encoded permid should be successful.
        """
        self.assertIsInstance(self.session.get_permid(), str)

    def test_remove_download_by_id_empty(self):
        """
        Remove downloads method when empty.
        """
        self.session.remove_download_by_id("nonexisting_infohash")
        self.assertEqual(len(self.session.get_downloads()), 0)

    def test_remove_download_by_id_nonempty(self):
        """
        Remove an existing download.
        """
        infohash = "abc"
        download = MockObject()
        torrent_def = MockObject()
        torrent_def.get_infohash = lambda: infohash
        download.get_def = lambda: torrent_def
        self.session.get_downloads = lambda: [download]

        self.called = False

        def verify_remove_download_called(*args, **kwargs):
            self.called = True

        self.session.remove_download = verify_remove_download_called
        self.session.remove_download_by_id(infohash)
        self.assertTrue(self.called)

    @raises(OperationNotEnabledByConfigurationException)
    def test_get_dispersy_instance(self):
        """
        Test whether the get dispersy instance throws an exception if dispersy is not enabled.
        """
        self.session.config.get_dispersy_enabled = lambda: False
        self.session.get_dispersy_instance()

    @raises(OperationNotEnabledByConfigurationException)
    def test_get_ipv8_instance(self):
        """
        Test whether the get IPv8 instance throws an exception if IPv8 is not enabled.
        """
        self.session.config.set_ipv8_enabled(False)
        self.session.get_ipv8_instance()

    @raises(OperationNotEnabledByConfigurationException)
    def test_has_collected_torrent(self):
        """
        Test whether the has_collected_torrent throws an exception if dispersy is not enabled.
        """
        self.session.config.get_torrent_store_enabled = lambda: False
        self.session.has_collected_torrent(None)

    @raises(OperationNotEnabledByConfigurationException)
    def test_get_collected_torrent(self):
        """
        Test whether the get_collected_torrent throws an exception if dispersy is not enabled.
        """
        self.session.config.get_torrent_store_enabled = lambda: False
        self.session.get_collected_torrent(None)

    @raises(OperationNotEnabledByConfigurationException)
    def test_save_collected_torrent(self):
        """
        Test whether the save_collected_torrent throws an exception if dispersy is not enabled.
        """
        self.session.config.get_torrent_store_enabled = lambda: False
        self.session.save_collected_torrent(None, None)

    @raises(OperationNotEnabledByConfigurationException)
    def test_delete_collected_torrent(self):
        """
        Test whether the delete_collected_torrent throws an exception if dispersy is not enabled.
        """
        self.session.config.get_torrent_store_enabled = lambda: False
        self.session.delete_collected_torrent(None)

    @raises(OperationNotEnabledByConfigurationException)
    def test_search_remote_channels(self):
        """
        Test whether the search_remote_channels throws an exception if dispersy is not enabled.
        """
        self.session.config.get_channel_search_enabled = lambda: False
        self.session.search_remote_channels(None)

    @raises(OperationNotEnabledByConfigurationException)
    def test_get_thumbnail_data(self):
        """
        Test whether the get_thumbnail_data throws an exception if dispersy is not enabled.
        """
        self.session.lm.metadata_store = None
        self.session.get_thumbnail_data(None)


class TestSessionWithLibTorrent(TestSessionAsServer):

    def setUpPreSession(self):
        super(TestSessionWithLibTorrent, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)

    @deferred(timeout=10)
    def test_remove_torrent_id(self):
        """
        Test whether removing a torrent id works.
        """
        torrent_def = TorrentDef.load(TORRENT_UBUNTU_FILE)
        dcfg = DownloadStartupConfig()
        dcfg.set_dest_dir(self.getDestDir())

        download = self.session.start_download_from_tdef(torrent_def, download_startup_config=dcfg, hidden=True)

        # Create a deferred which forwards the unhexlified string version of the download's infohash
        download_started = download.get_handle().addCallback(lambda handle: unhexlify(str(handle.info_hash())))

        return download_started.addCallback(self.session.remove_download_by_id)

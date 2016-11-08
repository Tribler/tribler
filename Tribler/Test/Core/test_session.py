from binascii import hexlify

from nose.tools import raises
from twisted.internet.defer import Deferred

from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Core.exceptions import OperationNotEnabledByConfigurationException, DuplicateTorrentFileError
from Tribler.Core.leveldbstore import LevelDbStore
from Tribler.Core.simpledefs import NTFY_CHANNELCAST, DLSTATUS_STOPPED, SIGNAL_CHANNEL, SIGNAL_ON_CREATED
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Test.Core.base_test import TriblerCoreTest, MockObject
from Tribler.Test.common import TORRENT_FILE
from Tribler.Test.test_as_server import TestAsServer
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestSession(TriblerCoreTest):

    @raises(OperationNotEnabledByConfigurationException)
    def test_torrent_store_not_enabled(self):
        config = SessionStartupConfig()
        config.set_torrent_store(False)
        session = Session(config, ignore_singleton=True)
        session.delete_collected_torrent(None)

    def test_torrent_store_delete(self):
        config = SessionStartupConfig()
        config.set_torrent_store(True)
        session = Session(config, ignore_singleton=True)
        # Manually set the torrent store as we don't want to start the session.
        session.lm.torrent_store = LevelDbStore(session.get_torrent_store_dir())
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

        config = SessionStartupConfig()
        session = Session(config, ignore_singleton=True)
        session.lm = LmMock()
        session.create_channel("name", "description", "open")
        self.assertEqual(session.lm.channel_manager.invoked_name, "name")
        self.assertEqual(session.lm.channel_manager.invoked_desc, "description")
        self.assertEqual(session.lm.channel_manager.invoked_mode, "open")

    def test_unhandled_error_observer(self):
        """
        Test the unhandled error observer
        """
        session = Session(SessionStartupConfig(), ignore_singleton=True)
        session.lm = MockObject()
        session.lm.api_manager = MockObject()
        session.lm.api_manager.root_endpoint = MockObject()
        session.lm.api_manager.root_endpoint.events_endpoint = MockObject()
        session.lm.api_manager.root_endpoint.state_endpoint = MockObject()

        expected_text = ""

        def on_tribler_exception(exception_text):
            self.assertEqual(exception_text, expected_text)

        on_tribler_exception.called = 0
        session.lm.api_manager.root_endpoint.events_endpoint.on_tribler_exception = on_tribler_exception
        session.lm.api_manager.root_endpoint.state_endpoint.on_tribler_exception = on_tribler_exception
        expected_text = "abcd"
        session.unhandled_error_observer({'isError': True, 'log_legacy': True, 'log_text': 'abcd'})
        expected_text = "defg"
        session.unhandled_error_observer({'isError': True, 'log_failure': 'defg'})


class TestSessionAsServer(TestAsServer):

    def setUpPreSession(self):
        super(TestSessionAsServer, self).setUpPreSession()
        self.config.set_megacache(True)
        self.config.set_torrent_collecting(True)
        self.config.set_enable_channel_search(True)
        self.config.set_dispersy(True)

    def setUp(self, autoload_discovery=True):
        super(TestSessionAsServer, self).setUp(autoload_discovery=autoload_discovery)
        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)

    @deferred(timeout=10)
    def test_add_torrent_def_to_channel(self):
        """
        Test whether adding a torrent def to a channel works
        """
        test_deferred = Deferred()

        torrent_def = TorrentDef.load(TORRENT_FILE)

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

        torrent_def = TorrentDef.load(TORRENT_FILE)

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
        self.session.tribler_config.set_download_state("abc", "stop")
        self.load_checkpoint_called = False

        def verify_load_checkpoint_call(initialdlstatus_dict={}):
            self.load_checkpoint_called = True
            self.assertEqual(initialdlstatus_dict, {"abc": DLSTATUS_STOPPED})

        self.session.lm.load_checkpoint = verify_load_checkpoint_call
        self.session.load_checkpoint()
        self.assertTrue(self.load_checkpoint_called)

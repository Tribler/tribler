from binascii import hexlify

from nose.tools import raises

from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.exceptions import OperationNotEnabledByConfigurationException, DuplicateTorrentFileError
from Tribler.Core.leveldbstore import LevelDbStore
from Tribler.Core.simpledefs import NTFY_CHANNELCAST
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.test_libtorrent_download import TORRENT_FILE
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

    def test_add_torrent_def_to_channel(self):
        """
        Test whether adding a torrent def to a channel works
        """
        self.session.create_channel("name", "description", "open")

        channel_id = self.channel_db_handler.getMyChannelId()
        torrent_def = TorrentDef.load(TORRENT_FILE)
        extra_info = {"description": "iso"}

        @blocking_call_on_reactor_thread
        def do_test():
            self.session.add_torrent_def_to_channel(channel_id, torrent_def, extra_info, forward=False)
        do_test()

        self.assertTrue(self.channel_db_handler.hasTorrent(channel_id, torrent_def.get_infohash()))

    def test_add_torrent_def_to_channel_duplicate(self):
        """
        Test whether adding a torrent def to a channel works
        """
        self.session.create_channel("name", "description", "open")

        channel_id = self.channel_db_handler.getMyChannelId()
        torrent_def = TorrentDef.load(TORRENT_FILE)

        @raises(DuplicateTorrentFileError)
        @blocking_call_on_reactor_thread
        def do_test():
            self.session.add_torrent_def_to_channel(channel_id, torrent_def, forward=False)
            self.session.add_torrent_def_to_channel(channel_id, torrent_def, forward=False)
        do_test()

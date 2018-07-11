from Tribler.Core.Config.tribler_config import TriblerConfig
from Tribler.Core.Modules.channel.channel import ChannelObject
from Tribler.Core.Modules.channel.channel_manager import ChannelManager
from Tribler.Core.Session import Session
from Tribler.Core.exceptions import DuplicateChannelNameError
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.pyipv8.ipv8.util import blocking_call_on_reactor_thread
from twisted.internet.defer import inlineCallbacks
from twisted.python.log import removeObserver


class TestChannelManager(TriblerCoreTest):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestChannelManager, self).setUp(annotate=annotate)
        self.session = None

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        removeObserver(self.session.unhandled_error_observer)
        yield super(TestChannelManager, self).tearDown(annotate=annotate)

    @blocking_call_on_reactor_thread
    def test_create_channel_duplicate_name_error(self):
        config = TriblerConfig()
        config.set_state_dir(self.getStateDir())
        self.session = Session(config)

        class LmMock(object):
            channel_manager = ChannelManager(self.session)

        self.session.lm = LmMock()

        class MockCommunity(object):
            cid = ""

            def get_channel_name(self):
                return "Channel name"

        channel_obj = ChannelObject(self.session, MockCommunity(), is_created=True)
        self.session.lm.channel_manager._channel_list = [channel_obj]

        with self.assertRaises(DuplicateChannelNameError) as cm:
            self.session.lm.channel_manager.create_channel("Channel name", "description", "open")
        self.assertEqual(cm.exception.message, u"Channel name already exists: Channel name")

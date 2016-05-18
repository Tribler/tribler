from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.Modules.channel.channel import ChannelObject
from Tribler.Core.exceptions import DuplicateChannelNameError
from Tribler.Core.Modules.channel.channel_manager import ChannelManager
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestChannelManager(TriblerCoreTest):

    @blocking_call_on_reactor_thread
    def test_create_channel_duplicate_name_error(self):
        self.config = SessionStartupConfig()
        self.session = Session(self.config, ignore_singleton=True)

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

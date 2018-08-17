from twisted.internet.defer import inlineCallbacks

from Tribler.Core.simpledefs import NTFY_CHANNELCAST
from Tribler.Core.simpledefs import NTFY_VOTECAST
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.test_as_server import TestAsServer
from Tribler.community.allchannel.community import AllChannelCommunity
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import ManualEnpoint
from Tribler.dispersy.member import DummyMember


class BaseTestChannel(TestAsServer):

    @inlineCallbacks
    def setUp(self):
        """
        Setup some classes and files that are used by the tests in this module.
        """
        yield super(BaseTestChannel, self).setUp()

        self.fake_session = MockObject()
        self.fake_session.add_observer = lambda a, b, c: False

        self.fake_session_config = MockObject()
        self.fake_session_config.get_state_dir = lambda: self.session_base_dir
        self.fake_session.config = self.fake_session_config

        fake_notifier = MockObject()
        fake_notifier.add_observer = lambda a, b, c, d: False
        fake_notifier.notify = lambda a, b, c, d: False
        self.fake_session.notifier = fake_notifier

        self.fake_channel_community = MockObject()
        self.fake_channel_community.get_channel_id = lambda: 42
        self.fake_channel_community.cid = 'a' * 20
        self.fake_channel_community.get_channel_name = lambda: "my fancy channel"

        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)
        self.votecast_db_handler = self.session.open_dbhandler(NTFY_VOTECAST)

        self.session.get_dispersy = lambda: True
        self.session.lm.dispersy = Dispersy(ManualEnpoint(0), self.getStateDir())

    def setUpPreSession(self):
        super(BaseTestChannel, self).setUpPreSession()
        self.config.set_megacache_enabled(True)

    def insert_channel_in_db(self, dispersy_cid, peer_id, name, description):
        return self.channel_db_handler.on_channel_from_dispersy(dispersy_cid, peer_id, name, description)

    def insert_torrents_into_channel(self, torrent_list):
        self.channel_db_handler.on_torrents_from_dispersy(torrent_list)

    def create_fake_allchannel_community(self):
        """
        This method creates a fake AllChannel community so we can check whether a request is made in the community
        when doing stuff with a channel.
        """
        self.session.lm.dispersy._database.open()
        fake_member = DummyMember(self.session.lm.dispersy, 1, "a" * 20)
        member = self.session.lm.dispersy.get_new_member(u"curve25519")
        fake_community = AllChannelCommunity(self.session.lm.dispersy, fake_member, member)
        self.session.lm.dispersy._communities = {"allchannel": fake_community}
        return fake_community

    @inlineCallbacks
    def tearDown(self):
        self.session.lm.dispersy.cancel_all_pending_tasks()
        self.session.lm.dispersy = None
        yield super(BaseTestChannel, self).tearDown()

from Tribler.community.channel.community import ChannelCommunity

from Tribler.Test.test_as_server import AbstractServer
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import ManualEnpoint
from Tribler.dispersy.member import DummyMember
from Tribler.dispersy.requestcache import RequestCache
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class AbstractTestChannelCommunity(AbstractServer):

    # We have to initialize Dispersy and the channel community on the reactor thread
    @blocking_call_on_reactor_thread
    def setUp(self):
        super(AbstractTestChannelCommunity, self).setUp()

        self.dispersy = Dispersy(ManualEnpoint(0), self.getStateDir())
        self.dispersy._database.open()
        self.master_member = DummyMember(self.dispersy, 1, "a" * 20)
        self.member = self.dispersy.get_new_member(u"curve25519")
        self.channel_community = ChannelCommunity(self.dispersy, self.master_member, self.member)
        self.channel_community._request_cache = RequestCache()

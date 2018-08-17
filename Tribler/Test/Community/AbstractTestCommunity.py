from twisted.internet.defer import inlineCallbacks

from Tribler.Test.test_as_server import AbstractServer
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import ManualEnpoint
from Tribler.dispersy.member import DummyMember


class AbstractTestCommunity(AbstractServer):

    # We have to initialize Dispersy and the tunnel community on the reactor thread

    @inlineCallbacks
    def setUp(self):
        yield super(AbstractTestCommunity, self).setUp()
        self.dispersy = Dispersy(ManualEnpoint(0), self.getStateDir())
        self.dispersy._database.open()
        self.master_member = DummyMember(self.dispersy, 1, "a" * 20)
        self.member = self.dispersy.get_new_member(u"curve25519")

    @inlineCallbacks
    def tearDown(self):
        for community in self.dispersy.get_communities():
            yield community.unload_community()

        self.master_member = None
        self.member = None
        yield super(AbstractTestCommunity, self).tearDown()

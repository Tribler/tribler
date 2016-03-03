import logging
import signal
from twisted.internet.defer import inlineCallbacks

from twisted.internet import reactor
from twisted.python.log import addObserver

from Tribler.Core.Session import Session
from Tribler.community.allchannel.community import AllChannelCommunity, ChannelCastDBStub
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import StandaloneEndpoint

logging.basicConfig(format="%(asctime)-15s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class TestDispersy(Dispersy):

    def signal_handler(self, sig, frame):
        print '' # empty line to make info logging cleaner
        key = ''
        for i in signal.__dict__.keys():
            if i.startswith("SIG") and getattr(signal, i) == sig:
                key = i
                break
        logger.info("Received signal '%s', shutting down.", key)
        self.stop()
        reactor.stop()

    def bind_signals(self):
        "Binds to terminating signals"
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGQUIT, self.signal_handler)

    def setup_communities(self):
        master_key = "3081a7301006072a8648ce3d020106052b81040027038192000405548a13626683d4788ab19393fa15c9e9d6f5ce0ff47737747fa511af6c4e956f523dc3d1ae8d7b83b850f21ab157dd4320331e2f136aa01e70d8c96df665acd653725e767da9b5079f25cebea808832cd16015815797906e90753d135ed2d796b9dfbafaf1eae2ebea3b8846716c15814e96b93ae0f5ffaec44129688a38ea35f879205fdbe117323e73076561f112".decode("HEX")
        master = self.get_member(public_key=master_key)

        # Create an instance of the market community
        # self.allchannel_community = AllChannelCommunity.init_community(self, master, self.me)
        # self.attach_community(self.allchannel_community)

        self.stub = ChannelCastDBStub(self)

    @inlineCallbacks
    def query_community(self):
        for i in xrange(5):
            print "", i
            var = yield self.stub._cacheTorrents()

    def init(self):
        self.start(autoload_discovery=True)
        logger.info('Started Dispersy instance on port %d' % self.port)
        self.me = self.get_new_member()

        self.setup_communities()
        deferred = self.query_community()

    def __init__(self, port):
        self.port = port
        super(TestDispersy, self).__init__(StandaloneEndpoint(port), u'../data_' + str(port), u'dispersy.db')
        self.statistics.enable_debug_statistics(True)

        self.bind_signals()

        from Tribler.dispersy.util import unhandled_error_observer
        addObserver(unhandled_error_observer)

    def dispersy_start(self):
        logger.info('Starting Twisted Reactor')
        reactor.exitCode = 0
        reactor.callWhenRunning(self.init)
        reactor.run()

# class BasicRun():
#
#     def initialize(self):
#         self.allchannel_community = AllChannelCommunity()
#         self.session = Session.get_instance()
#         self.allchannel_community.initialize(tribler_session=self.session)
#
#     def run(self):
#         self.allchannel_community._selectTorrentsToCollect(0, "BEE")


if __name__ == "__main__":
    testDispersy = TestDispersy(15783)
    testDispersy.dispersy_start()
    exit(reactor.exitCode)

    # basic = BasicRun()
    # basic.initialize()



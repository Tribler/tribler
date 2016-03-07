import logging
import signal

import time
import yappi
from pycallgraph import PyCallGraph, Config
from pycallgraph.output import GraphvizOutput
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
        self.quit_now()

    def quit_now(self):
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

    def insert_random_crap_in_db(self):
        for _ in xrange(1000000):
            self._database.execute(
                    u"INSERT INTO sync (community, member, global_time, meta_message, packet, sequence) "
                    u"VALUES (?, ?, ?, ?, ?, ?)",
                   (-1,
                    -1,
                    time.time(),
                    -1,
                    buffer("bla"),
                    None
                    ))

    @inlineCallbacks
    def query_community(self):

        total_delay = 2 #seconds
        calls = 100 # amount of calls
        step_delay = float(total_delay) / float(calls)
        write_statistics = False
        # self.insert_random_crap_in_db()

        calls_made = open("profiling/calls_made_blocking.txt", 'w')
        calls_done = open("profiling/calls_done_blocking.txt", "w")

        if write_statistics:
            graphviz = GraphvizOutput()
            name = "profiling/graphiz_stub_cacheTorrents_%s_%s.svg" % (calls, time.strftime("%d-%m-%Y-%H-%M-%S"))
            graphviz.output_file = name
            graphviz.output_type = 'svg'
            # config = Config(max_depth=3, memory=True)

        def print_done(i):
            calls_done.write("%s %s %s\n" % (i, float(step_delay*i), int(round(time.time() * 1000))))

        yappi.set_clock_type('cpu')
        yappi.start(builtins=True)

        if write_statistics:
            with PyCallGraph(output=graphviz):
                for i in xrange(calls):
                    yield self.stub._cacheTorrents()
        else:
            for i in xrange(calls):
                calls_made.write("%s %s %s\n" % (i, float(i*step_delay), int(round(time.time() * 1000))))
                reactor.callLater(float(i*step_delay), print_done, i)
                yield self.stub._cacheTorrents()

        yappi.stop()

        stats = yappi.get_func_stats()
        stats.sort("tsub").print_all(columns={0:("name",100), 1:("ncall", 12), 2:("tsub", 10), 3:("ttot", 10), 4:("tavg",10)})

        if write_statistics:
            name = "profiling/stub_cacheTorrents_%s_%s.pstat" % (calls, time.strftime("%d-%m-%Y-%H-%M-%S"))
            stats.sort("tsub").save(name, type="pstat")

        time.sleep(5)
        calls_made.flush()
        calls_done.flush()
        self.quit_now()

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
    graphviz = GraphvizOutput()


    exit(reactor.exitCode)

    # basic = BasicRun()
    # basic.initialize()



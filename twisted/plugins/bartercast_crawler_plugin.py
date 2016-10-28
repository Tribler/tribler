"""
Run Dispersy in standalone bartercast crawler mode.

Crawls BarterCommunity and collects interaction data from peers.

Temporary approach: all peers will run this service if this works OK. See Github issue #3.
"""
import os
import signal

from Tribler.dispersy.crypto import NoVerifyCrypto, NoCrypto
# from dispersy.discovery.community import DiscoveryCommunity
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import StandaloneEndpoint
from Tribler.dispersy.exception import CommunityNotFoundException
from twisted.application.service import IServiceMaker, MultiService
from twisted.conch import manhole_tap
from twisted.internet import reactor
from twisted.plugin import IPlugin
from twisted.python import usage
from twisted.python.log import msg
from twisted.python.threadable import isInIOThread
from zope.interface import implements
from Tribler.community.bartercast4.community import BarterCommunityCrawler
from Tribler.dispersy.tool.clean_observers import clean_twisted_observers


clean_twisted_observers()


class BartercastCrawler(Dispersy):

    def __init__(self, endpoint, working_directory, silent=False, crypto=NoVerifyCrypto()):
        super(BartercastCrawler, self).__init__(endpoint, working_directory, u":memory:", crypto)

        # location of persistent storage
        self._persistent_storage_filename = os.path.join(working_directory, "persistent-storage.data")
        self._silent = silent
        self._my_member = None


    def start(self):
        assert isInIOThread()
        if super(BartercastCrawler, self).start():
            self._create_my_member()
            print "loading bartercc as member %s: " % self._my_member
           # self.register_task("unload inactive communities",
            #                   LoopingCall(self.unload_inactive_communities)).start(COMMUNITY_CLEANUP_INTERVAL)

            self.define_auto_load(BarterCommunityCrawler, self._my_member, (), load=True)
            # self.define_auto_load(TrackerHardKilledCommunity, self._my_member)

            # if not self._silent:
            #    self._statistics_looping_call = LoopingCall(self._report_statistics)
            #    self._statistics_looping_call.start(300)

            return True
        return False

    def _create_my_member(self):
        # generate a new my-member
        ec = self.crypto.generate_key(u"very-low")
        self._my_member = self.get_member(private_key=self.crypto.key_to_bin(ec))

    @property
    def persistent_storage_filename(self):
        return self._persistent_storage_filename

    def get_community(self, cid, load=False, auto_load=True):
        try:
            return super(BartercastCrawler, self).get_community(cid, True, True)
        except CommunityNotFoundException:
            return BarterCommunityCrawler.init_community(self, self.get_member(mid=cid), self._my_member)


class Options(usage.Options):
    optFlags = [
        ["profiler"   , "P", "use cProfile on the Dispersy thread"],
        ["memory-dump", "d", "use meliae to dump the memory periodically"],
        ["silent"     , "s", "Prevent tracker printing to console"],
    ]
    optParameters = [
        ["statedir", "s", "."       , "Use an alternate statedir"                                    , str],
        ["ip"      , "i", "0.0.0.0" , "Dispersy uses this ip"                                        , str],
        ["port"    , "p", 6421      , "Dispersy uses this UDL port"                                  , int],
        ["crypto"  , "c", "ECCrypto", "The Crypto object type Dispersy is going to use"              , str],
        ["manhole" , "m", 0         , "Enable manhole telnet service listening at the specified port", int],
    ]


class BartercastCrawlerServiceMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "bartercast_crawler"
    description = "A BartercastCommunity statistics crawler"
    options = Options

    def makeService(self, options):
        """
        Construct a dispersy service.
        """

        tracker_service = MultiService()
        tracker_service.setName("Bartercast Crawler")
        # crypto
        if options["crypto"] == 'NoCrypto':
            crypto = NoCrypto()
        else:
            crypto = NoVerifyCrypto()

        container = [None]
        manhole_namespace = {}
        if options["manhole"]:
            port = options["manhole"]
            manhole = manhole_tap.makeService({
                'namespace': manhole_namespace,
                'telnetPort': 'tcp:%d:interface=127.0.0.1' % port,
                'sshPort': None,
                'passwd': os.path.join(os.path.dirname(__file__), 'passwd'),
            })
            tracker_service.addService(manhole)
            manhole.startService()

        def run():
            # setup
            dispersy = BartercastCrawler(StandaloneEndpoint(options["port"],
                                                          options["ip"]),
                                       unicode(options["statedir"]),
                                       bool(options["silent"]),
                                       crypto)
            container[0] = dispersy
            manhole_namespace['dispersy'] = dispersy

            self._stopping = False
            def signal_handler(sig, frame):
                msg("Received signal '%s' in %s (shutting down)" % (sig, frame))
                if not self._stopping:
                    self._stopping = True
                    dispersy.stop().addCallback(lambda _: reactor.stop)
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            # start
            print "starting dispersy"
            if not dispersy.start():
                raise RuntimeError("Unable to start Dispersy")

        # wait forever
        reactor.exitCode = 0
        reactor.callWhenRunning(run)
        # TODO: exit code
        return tracker_service


# Now construct an object which *provides* the relevant interfaces
# The name of this variable is irrelevant, as long as there is *some*
# name bound to a provider of IPlugin and IServiceMaker.
serviceMaker = BartercastCrawlerServiceMaker()

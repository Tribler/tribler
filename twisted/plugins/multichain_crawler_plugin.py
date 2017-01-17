import os
import signal
import logging.config

from twisted.application.service import IServiceMaker, MultiService
from twisted.internet import reactor
from twisted.plugin import IPlugin
from twisted.python import usage

from zope.interface import implements

from Tribler.community.multichain.community import MultiChainCommunityCrawler
from Tribler.dispersy.crypto import ECCrypto
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import StandaloneEndpoint


class Options(usage.Options):
    optParameters = [
        ["statedir", "s", os.path.join(unicode(os.environ.get('HOME')), u'.multichain')
          if os.environ.get('HOME') else u'.multichain', "Use an alternate statedir"    , unicode],
        ["ip"      , "i", "0.0.0.0" ,  "Dispersy uses this ip"                          , str],
        ["port"    , "p", 6421      ,  "Dispersy uses this UDP port"                    , int],
    ]


class MultichainCrawlerServiceMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "multichain_crawler"
    description = "A MultichainCommunity crawler"
    options = Options

    def makeService(self, options):
        # setup logging if there is a logger.conf in the state dir or working dir
        if os.path.exists(os.path.join(options["statedir"], "logger.conf")):
            logging.config.fileConfig(os.path.join(options["statedir"], "logger.conf"))
        elif os.path.exists("logger.conf"):
            logging.config.fileConfig("logger.conf")
        else:
            logging.basicConfig(format="%(asctime)-15s [%(levelname)s] %(message)s", level=logging.DEBUG)
        logger = logging.getLogger(__name__)
        tracker_service = MultiService()
        tracker_service.setName("Multichain Crawler")

        def run():
            crypto = ECCrypto()
            dispersy = Dispersy(StandaloneEndpoint(options["port"], options["ip"]),
                                options["statedir"],
                                u'dispersy.db',
                                crypto)
            if not dispersy.start():
                raise RuntimeError("Unable to start Dispersy")
            master_member = MultiChainCommunityCrawler.get_master_members(dispersy)[0]
            my_member = dispersy.get_member(private_key=crypto.key_to_bin(crypto.generate_key(u"curve25519")))
            MultiChainCommunityCrawler.init_community(dispersy, master_member, my_member)

            self._stopping = False

            def signal_handler(sig, frame):
                logger.info("Received signal '%s' in %s (shutting down)" % (sig, frame))
                if not self._stopping:
                    self._stopping = True
                    dispersy.stop().addCallback(lambda _: reactor.stop)
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

        reactor.exitCode = 0
        reactor.callWhenRunning(run)
        return tracker_service


# Now construct an object which *provides* the relevant interfaces
# The name of this variable is irrelevant, as long as there is *some*
# name bound to a provider of IPlugin and IServiceMaker.
serviceMaker = MultichainCrawlerServiceMaker()

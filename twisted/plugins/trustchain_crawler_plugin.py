import os
import signal
import logging.config

from twisted.application.service import IServiceMaker, MultiService
from twisted.internet import reactor
from twisted.plugin import IPlugin
from twisted.python import usage
from twisted.python.log import msg

from zope.interface import implements

from Tribler.community.triblerchain.community import TriblerChainCommunityCrawler
from Tribler.dispersy.crypto import ECCrypto
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import StandaloneEndpoint


class Options(usage.Options):
    optParameters = [
        ["statedir", "s", os.path.join(unicode(os.environ.get('HOME')), u'.trustchain')
          if os.environ.get('HOME') else u'.trustchain', "Use an alternate statedir", unicode],
        ["ip", "i", "0.0.0.0",  "Dispersy uses this ip", str],
        ["port", "p", 6421,  "Dispersy uses this UDP port", int],
    ]


if not os.path.exists("logger.conf"):
    print "Unable to find logger.conf"
else:
    log_directory = os.path.abspath(os.environ.get('APPDATA', os.path.expanduser('~')))
    log_directory = os.path.join(log_directory, '.Tribler', 'logs')

    if not os.path.exists(log_directory):
        os.makedirs(log_directory)

    logging.info_log_file = '%s/tribler-info.log' % log_directory
    logging.error_log_file = '%s/tribler-error.log' % log_directory
    logging.config.fileConfig("logger.conf", disable_existing_loggers=False)


class TrustchainCrawlerServiceMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "trustchain_crawler"
    description = "A TrustChainCommunity crawler"
    options = Options

    def makeService(self, options):
        tracker_service = MultiService()
        tracker_service.setName("Trustchain Crawler")

        def run():
            crypto = ECCrypto()
            dispersy = Dispersy(StandaloneEndpoint(options["port"], options["ip"]),
                                options["statedir"],
                                u'dispersy.db',
                                crypto)
            if not dispersy.start():
                raise RuntimeError("Unable to start Dispersy")
            master_member = TriblerChainCommunityCrawler.get_master_members(dispersy)[0]
            my_member = dispersy.get_member(private_key=crypto.key_to_bin(crypto.generate_key(u"curve25519")))
            TriblerChainCommunityCrawler.init_community(dispersy, master_member, my_member)

            self._stopping = False

            def signal_handler(sig, frame):
                msg("Received signal '%s' in %s (shutting down)" % (sig, frame))
                if not self._stopping:
                    self._stopping = True
                    dispersy.stop().addCallback(lambda _: reactor.stop())

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

        reactor.exitCode = 0
        reactor.callWhenRunning(run)
        return tracker_service


# Now construct an object which *provides* the relevant interfaces
# The name of this variable is irrelevant, as long as there is *some*
# name bound to a provider of IPlugin and IServiceMaker.
serviceMaker = TrustchainCrawlerServiceMaker()

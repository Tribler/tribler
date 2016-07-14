import logging
import os
import signal
from zope.interface import implements

from twisted.application.service import IServiceMaker, MultiService
from twisted.internet import reactor
from twisted.plugin import IPlugin
from twisted.python import usage

from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Policies.BoostingManager import BoostingManager, BoostingSettings
from Tribler.Policies.credit_mining_util import string_to_source, string_policy_to_object

logging.basicConfig(format="%(asctime)-15s [%(levelname)s] %(message)s", level=logging.DEBUG)
logger = logging.getLogger(__name__)


class Options(usage.Options):
    optParameters = [
        ["statedir", "s", os.path.join(unicode(os.environ.get('HOME')), u'.credit_mining')
         if os.environ.get('HOME') else u'.credit_mining', "Use an alternate state directory"
            , unicode],
        ["channel", "c", "0000000000000000000000000000000000000000",  "Channel boosted (dispersy cid)", str],
        ["policy", "p", "seederratio",  "Policy for swarm selection", str]
    ]


class CreditMiningServiceMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "creditmining_channel"
    description = "Credit Mining Channel Booster"
    options = Options

    def __init__(self):
        self.session = None
        self.config = SessionStartupConfig()
        self.config.set_torrent_checking(True)
        self.config.set_megacache(True)
        self.config.set_dispersy(True)
        self.config.set_torrent_store(True)
        self.config.set_enable_torrent_search(True)
        self.config.set_enable_channel_search(True)
        self.config.set_channel_community_enabled(True)
        self.config.set_preview_channel_community_enabled(True)
        self.config.set_libtorrent(True)

        self.bsetting = BoostingSettings(self.session, load_config=False)

        self._stopping = False
        self.boostingmanager = None

    def start_session(self, options):
        def signal_handler(sig, frame):
            logger.info("Received signal '%s' in %s (shutting down)" % (sig, frame))
            if not self._stopping:
                self._stopping = True
                self.boostingmanager.shutdown()
                self.session.shutdown()
                reactor.stop()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        self.config.set_state_dir(options["statedir"])

        self.session = Session(self.config)
        self.session.prestart()
        self.session.start()

        self.bsetting.policy = string_policy_to_object(options['policy'])

        self.boostingmanager = BoostingManager(self.session, self.bsetting)
        self.boostingmanager.add_source(string_to_source(options['channel']))

    def makeService(self, options):
        tracker_service = MultiService()
        tracker_service.setName(self.description)

        reactor.exitCode = 0
        reactor.callWhenRunning(self.start_session, options)
        return tracker_service

serviceMaker = CreditMiningServiceMaker()

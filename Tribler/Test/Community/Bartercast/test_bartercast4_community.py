# Written by Cor-Paul Bezemer
# see LICENSE.txt for license information

from time import sleep

from twisted.internet.task import LoopingCall
from twisted.internet.defer import inlineCallbacks, Deferred

from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Test.test_as_server import TestAsServer
from Tribler.community.bartercast4.community import BarterCommunity, BarterCommunityCrawler
from Tribler.community.bartercast4.statistics import BartercastStatisticTypes, _barter_statistics
from Tribler.community.tunnel.tunnel_community import TunnelSettings
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestBarterCommunity(TestAsServer):

    """Start a tribler session and wait for the statistics to be increased."""

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        yield super(TestBarterCommunity, self).setUp(autoload_discovery=autoload_discovery)

        self._test_condition_lc = None
        self._test_local_msg_lc = None
        self.test_deferred = Deferred()
        self.dispersy = self.session.get_dispersy_instance()
        self.load_communities(self.session, self.dispersy, True)
        yield self.setupPeer()

    # for future stuff; you can use this if you need another peer for some reason
    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setupPeer(self):
        from Tribler.Core.Session import Session

        self.config2 = self.config.copy()
        self.config2.set_state_dir(self.getStateDir(2))

        self.session2 = Session(self.config2, ignore_singleton=True)

        self.session2.prestart()
        yield self.session2.start()
        self.load_communities(self.session2, self.session2.get_dispersy_instance())

    def setUpPreSession(self):
        super(TestBarterCommunity, self).setUpPreSession()
        self.config.set_dispersy(True)
        self.config.set_megacache(True)
        self.config.set_enable_channel_search(True)

    @deferred(timeout=120)
    def test_local_stats(self):
        """
        Testing whether we locally receive stats from the BarterCast community
        """
        def do_stats_test():
            for val in _barter_statistics.bartercast[BartercastStatisticTypes.TORRENTS_RECEIVED].itervalues():
                if val > 0:
                    self._test_local_msg_lc.stop()
                    self.test_deferred.callback(None)

        self._test_local_msg_lc = LoopingCall(do_stats_test)
        self._test_local_msg_lc.start(5, now=True)
        return self.test_deferred

    @deferred(timeout=120)
    def test_stats_messages(self):
        """
        Testing whether we receive stats from other users in the BarterCast community
        """
        def do_stats_messages():
            if len(_barter_statistics.get_interactions(self.dispersy)):
                # Some bartercast statistic was crawled.
                self._test_condition_lc.stop()
                self.test_deferred.callback(None)

        self._test_condition_lc = LoopingCall(do_stats_messages)
        self._test_condition_lc.start(5, now=True)
        return self.test_deferred

    @blocking_call_on_reactor_thread
    def load_communities(self, session, dispersy, crawler=False):
        keypair = dispersy.crypto.generate_key(u"curve25519")
        dispersy_member = dispersy.get_member(private_key=dispersy.crypto.key_to_bin(keypair))
        settings = TunnelSettings(tribler_session=session)
        settings.become_exitnode = True
        if crawler:
            dispersy.define_auto_load(BarterCommunityCrawler, dispersy_member, (session, settings), load=True)
        else:
            dispersy.define_auto_load(BarterCommunity, dispersy_member, (session, settings), load=True)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        if self.session2:
            yield self.session2.shutdown()

        yield super(TestBarterCommunity, self).tearDown(annotate=annotate)

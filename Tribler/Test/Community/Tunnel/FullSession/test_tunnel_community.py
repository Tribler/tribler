from twisted.internet import reactor
from twisted.internet.defer import Deferred, inlineCallbacks

from Tribler.Core.simpledefs import DLSTATUS_SEEDING
from twisted.internet.defer import inlineCallbacks
from Tribler.Test.Community.Tunnel.FullSession.test_tunnel_base import TestTunnelBase


class TestTunnelCommunity(TestTunnelBase):
    """
    This class contains full session tests for the tunnel community.
    """

    @inlineCallbacks
    def setUp(self):
        self.test_deferred = Deferred()
        yield super(TestTunnelCommunity, self).setUp()

    @inlineCallbacks
    def test_anon_download(self):
        """
        Testing whether an anonymous download over our tunnels works
        """
        yield self.setup_nodes()

        def download_state_callback(ds):
            if ds.get_progress() == 1.0 and ds.get_status() == DLSTATUS_SEEDING:
                self.test_deferred.callback(None)
                return 0.0
            return 2.0

        download = self.start_anon_download()
        download.set_state_callback(download_state_callback)

        yield self.test_deferred
        yield self.sleep(4) # FIXME: workaround for slow Tribler Session shutdown

    @inlineCallbacks
    def test_anon_download_no_exitnodes(self):
        """
        Testing whether an anon download does not make progress without exit nodes
        """
        yield self.setup_nodes(num_exitnodes=0)

        def download_state_callback(ds):
            if ds.get_progress() != 0.0:
                self.test_deferred.errback(
                    RuntimeError("Anonymous download should not make progress without exit nodes"))
                return 0.0
            return 2.0

        download = self.start_anon_download()
        download.set_state_callback(download_state_callback)

        reactor.callLater(30, self.test_deferred.callback, None)

        yield self.test_deferred

    @inlineCallbacks
    def test_anon_download_no_relays(self):
        """
        Testing whether an anon download does not make progress without relay nodes
        """
        yield self.setup_nodes(num_relays=0, num_exitnodes=1)

        def download_state_callback(ds):
            if ds.get_progress() != 0.0:
                self.test_deferred.errback(
                    RuntimeError("Anonymous download should not make progress without relay nodes"))
                return 0.0
            return 2.0

        download = self.start_anon_download(hops=2)
        download.set_state_callback(download_state_callback)

        reactor.callLater(30, self.test_deferred.callback, None)

        yield self.test_deferred

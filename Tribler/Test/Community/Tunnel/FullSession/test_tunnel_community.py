from asyncio import Future, sleep

from Tribler.Core.simpledefs import DLSTATUS_SEEDING
from Tribler.Test.Community.Tunnel.FullSession.test_tunnel_base import TestTunnelBase
from Tribler.Test.tools import timeout


class TestTunnelCommunity(TestTunnelBase):
    """
    This class contains full session tests for the tunnel community.
    """

    async def setUp(self):
        self.test_future = Future()
        await super(TestTunnelCommunity, self).setUp()

    @timeout(30)
    async def test_anon_download(self):
        """
        Testing whether an anonymous download over our tunnels works
        """
        await self.setup_nodes()

        def download_state_callback(ds):
            if ds.get_progress() == 1.0 and ds.get_status() == DLSTATUS_SEEDING:
                self.test_future.set_result(None)
                return 0.0
            return 2.0

        download = await self.start_anon_download()
        download.set_state_callback(download_state_callback)

        await self.test_future

    @timeout(30)
    async def test_anon_download_no_exitnodes(self):
        """
        Testing whether an anon download does not make progress without exit nodes
        """
        await self.setup_nodes(num_exitnodes=0)

        def download_state_callback(ds):
            if ds.get_progress() != 0.0:
                self.test_future.set_exception(
                    RuntimeError("Anonymous download should not make progress without exit nodes"))
                return 0.0
            return 2.0

        download = await self.start_anon_download()
        download.set_state_callback(download_state_callback)

        await sleep(25)

    @timeout(30)
    async def test_anon_download_no_relays(self):
        """
        Testing whether an anon download does not make progress without relay nodes
        """
        await self.setup_nodes(num_relays=0, num_exitnodes=1)

        def download_state_callback(ds):
            if ds.get_progress() != 0.0:
                self.test_future.set_exception(
                    RuntimeError("Anonymous download should not make progress without relay nodes"))
                return 0.0
            return 2.0

        download = await self.start_anon_download(hops=2)
        download.set_state_callback(download_state_callback)

        await sleep(25)

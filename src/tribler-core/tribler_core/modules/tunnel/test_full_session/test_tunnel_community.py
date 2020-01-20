import sys
from asyncio import sleep, wait_for
from unittest import skipIf

from tribler_core.modules.tunnel.test_full_session.test_tunnel_base import TestTunnelBase
from tribler_core.tests.tools.tools import timeout


class TestTunnelCommunity(TestTunnelBase):
    """
    This class contains full session tests for the tunnel community.
    """

    @skipIf(sys.platform in ["win32", "darwin"], "Skipping this test on Windows and Mac")
    @timeout(20)
    async def test_anon_download(self):
        """
        Testing whether an anonymous download over our tunnels works
        """
        await self.setup_nodes()
        download = self.start_anon_download()
        self.tunnel_community.remove_circuit = lambda *_, **__: None  # Keep the circuit so we can inspect it later
        await wait_for(download.future_finished, timeout=15)
        self.assertGreater(self.tunnel_community.find_circuits()[0].bytes_down, 2000000)

    @timeout(20)
    async def test_anon_download_no_exits(self):
        """
        Testing whether an anon download does not make progress without exit nodes
        """
        await self.setup_nodes(num_exitnodes=0)
        download = self.start_anon_download()
        await sleep(10)
        self.assertEqual(self.tunnel_community.find_circuits(), [])
        self.assertEqual(download.get_state().get_total_transferred('down'), 0)

    @timeout(20)
    async def test_anon_download_no_relays(self):
        """
        Testing whether an anon download does not make progress without relay nodes
        """
        await self.setup_nodes(num_relays=0, num_exitnodes=1)
        download = self.start_anon_download(hops=2)
        await sleep(10)
        self.assertEqual(self.tunnel_community.find_circuits(), [])
        self.assertEqual(download.get_state().get_total_transferred('down'), 0)

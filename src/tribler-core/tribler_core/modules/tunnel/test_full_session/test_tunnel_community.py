from asyncio import sleep

from tribler_common.simpledefs import DLSTATUS_DOWNLOADING

from tribler_core.modules.tunnel.test_full_session.test_tunnel_base import TestTunnelBase
from tribler_core.tests.tools.tools import timeout


class TestTunnelCommunity(TestTunnelBase):
    """
    This class contains full session tests for the tunnel community.
    """

    @timeout(20)
    async def test_anon_download(self):
        """
        Testing whether an anonymous download over our tunnels works
        """
        await self.setup_nodes()
        download = self.start_anon_download()
        await download.wait_for_status(DLSTATUS_DOWNLOADING)
        self.session.dlmgr.set_download_states_callback(self.session.dlmgr.sesscb_states_callback, interval=.1)
        while not self.tunnel_community.find_circuits():
            await sleep(.1)
        await sleep(.6)
        self.assertGreater(self.tunnel_community.find_circuits()[0].bytes_up, 0)
        self.assertGreater(self.tunnel_community.find_circuits()[0].bytes_down, 0)

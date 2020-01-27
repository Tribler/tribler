import sys
import time
from asyncio import Future
from unittest import skipIf

from ipv8.messaging.anonymization.tunnel import CIRCUIT_TYPE_IP_SEEDER

from tribler_common.simpledefs import DLSTATUS_SEEDING

from tribler_core.modules.tunnel.test_full_session.test_tunnel_base import TestTunnelBase
from tribler_core.tests.tools.tools import timeout


class TestHiddenServices(TestTunnelBase):

    @skipIf(sys.platform == "darwin", "Skipping this test on Mac")
    @timeout(40)
    async def test_hidden_services(self):
        """
        Test the hidden services overlay by constructing an end-to-end circuit and downloading a torrent over it
        """
        await self.setup_nodes(num_relays=4, num_exitnodes=2, seed_hops=1)
        await self.deliver_messages()

        for c in self.tunnel_communities:
            self.assertEqual(7, len(c.get_peers()))
        self.assertEqual(7, len(self.tunnel_community_seeder.get_peers()))

        test_future = Future()

        def download_state_callback(ds):
            self.tunnel_community.monitor_downloads([ds])
            print(time.time(), ds.get_status(), ds.get_progress())
            if ds.get_progress() == 1.0 and ds.get_status() == DLSTATUS_SEEDING:
                test_future.set_result(None)
                return 0.0
            return 2.0

        self.tunnel_community.build_tunnels(1)

        while len(self.tunnel_community_seeder.find_circuits(ctype=CIRCUIT_TYPE_IP_SEEDER)) < 1:
            await self.deliver_messages()

        download = self.start_anon_download(hops=1)
        download.set_state_callback(download_state_callback)

        await test_future

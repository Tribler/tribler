from ipv8.peerdiscovery.discovery import RandomWalk

from tribler_common.simpledefs import STATEDIR_DB_DIR
from tribler_core.components.interfaces.bandwidth_accounting import BandwidthAccountingComponent
from tribler_core.components.interfaces.ipv8 import Ipv8Component
from tribler_core.components.interfaces.reporter import ReporterComponent
from tribler_core.components.interfaces.restapi import RESTComponent
from tribler_core.components.interfaces.upgrade import UpgradeComponent
from tribler_core.modules.bandwidth_accounting.community import (
    BandwidthAccountingCommunity,
    BandwidthAccountingTestnetCommunity,
)
from tribler_core.modules.bandwidth_accounting.database import BandwidthDatabase
from tribler_core.restapi.rest_manager import RESTManager


class BandwidthAccountingComponentImp(BandwidthAccountingComponent):
    rest_manager: RESTManager

    async def run(self):
        await self.use(ReporterComponent)
        await self.use(UpgradeComponent)
        config = self.session.config

        ipv8_component = await self.use(Ipv8Component)
        ipv8 = ipv8_component.ipv8
        peer = ipv8_component.peer
        rest_manager = self.rest_manager = (await self.use(RESTComponent)).rest_manager

        if config.general.testnet or config.bandwidth_accounting.testnet:
            bandwidth_cls = BandwidthAccountingTestnetCommunity
        else:
            bandwidth_cls = BandwidthAccountingCommunity

        database_path = config.state_dir / STATEDIR_DB_DIR / "bandwidth.db"
        database = BandwidthDatabase(database_path, peer.public_key.key_to_bin())
        community = bandwidth_cls(peer, ipv8.endpoint, ipv8.network,
                                  settings=config.bandwidth_accounting,
                                  database=database)
        ipv8.strategies.append((RandomWalk(community), 20))

        community.bootstrappers.append(ipv8_component.make_bootstrapper())

        ipv8.overlays.append(community)
        self.community = community

        rest_manager.get_endpoint('trustview').bandwidth_db = community.database
        rest_manager.get_endpoint('bandwidth').bandwidth_community = community

    async def shutdown(self):
        self.rest_manager.get_endpoint('trustview').bandwidth_db = None
        self.rest_manager.get_endpoint('bandwidth').bandwidth_community = None
        await self.community.unload()

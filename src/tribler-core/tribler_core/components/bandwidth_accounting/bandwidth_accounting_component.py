from ipv8.peerdiscovery.discovery import RandomWalk

from ipv8_service import IPv8

from tribler_common.simpledefs import STATEDIR_DB_DIR

from tribler_core.components.base import Component
from tribler_core.components.ipv8 import Ipv8Component
from tribler_core.components.reporter import ReporterComponent
from tribler_core.components.restapi import RestfulComponent
from tribler_core.components.upgrade import UpgradeComponent
from tribler_core.components.bandwidth_accounting.community.community import (
    BandwidthAccountingCommunity,
    BandwidthAccountingTestnetCommunity,
)
from tribler_core.components.bandwidth_accounting.db.database import BandwidthDatabase
from tribler_core.restapi.rest_manager import RESTManager


class BandwidthAccountingComponent(RestfulComponent):
    community: BandwidthAccountingCommunity

    _ipv8: IPv8

    async def run(self):
        await super().run()
        await self.get_component(UpgradeComponent)
        config = self.session.config

        ipv8_component = await self.require_component(Ipv8Component)
        self._ipv8 = ipv8_component.ipv8
        peer = ipv8_component.peer

        if config.general.testnet or config.bandwidth_accounting.testnet:
            bandwidth_cls = BandwidthAccountingTestnetCommunity
        else:
            bandwidth_cls = BandwidthAccountingCommunity

        db_name = "bandwidth_gui_test.db" if config.gui_test_mode else f"{bandwidth_cls.DB_NAME}.db"
        database_path = config.state_dir / STATEDIR_DB_DIR / db_name
        database = BandwidthDatabase(database_path, peer.public_key.key_to_bin())
        community = bandwidth_cls(peer, self._ipv8.endpoint, self._ipv8.network,
                                  settings=config.bandwidth_accounting,
                                  database=database)
        self._ipv8.add_strategy(community, RandomWalk(community), 20)

        community.bootstrappers.append(ipv8_component.make_bootstrapper())

        self.community = community
        await self.init_endpoints(['trustview', 'bandwidth'],
                                  [('bandwidth_db', community.database), ('bandwidth_community', community)])

    async def shutdown(self):
        await super().shutdown()
        await self._ipv8.unload_overlay(self.community)

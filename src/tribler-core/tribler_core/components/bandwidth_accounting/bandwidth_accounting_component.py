from tribler_common.simpledefs import STATEDIR_DB_DIR

from tribler_core.components.bandwidth_accounting.community.bandwidth_accounting_community import (
    BandwidthAccountingCommunity,
    BandwidthAccountingTestnetCommunity,
)
from tribler_core.components.bandwidth_accounting.db.database import BandwidthDatabase
from tribler_core.components.base import Component
from tribler_core.components.ipv8.ipv8_component import Ipv8Component


class BandwidthAccountingComponent(Component):
    community: BandwidthAccountingCommunity = None
    _ipv8_component: Ipv8Component = None
    database: BandwidthDatabase = None

    async def run(self):
        await super().run()
        self._ipv8_component = await self.require_component(Ipv8Component)

        config = self.session.config
        if config.general.testnet or config.bandwidth_accounting.testnet:
            bandwidth_cls = BandwidthAccountingTestnetCommunity
        else:
            bandwidth_cls = BandwidthAccountingCommunity

        db_name = "bandwidth_gui_test.db" if config.gui_test_mode else f"{bandwidth_cls.DB_NAME}.db"
        database_path = config.state_dir / STATEDIR_DB_DIR / db_name
        self.database = BandwidthDatabase(database_path, self._ipv8_component.peer.public_key.key_to_bin())
        self.community = bandwidth_cls(self._ipv8_component.peer,
                                       self._ipv8_component.ipv8.endpoint,
                                       self._ipv8_component.ipv8.network,
                                       settings=config.bandwidth_accounting,
                                       database=self.database)

        self._ipv8_component.initialise_community_by_default(self.community)

    async def shutdown(self):
        await super().shutdown()
        if self._ipv8_component and self.community:
            await self._ipv8_component.unload_community(self.community)

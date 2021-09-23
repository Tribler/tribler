from unittest.mock import Mock

from tribler_common.simpledefs import STATE_UPGRADING_READABLE
from tribler_core.components.base import Component, testcomponent
from tribler_core.components.implementation.masterkey import MasterKeyComponent
from tribler_core.components.implementation.reporter import ReporterComponent
from tribler_core.components.implementation.restapi import RESTComponent
from tribler_core.upgrade.upgrade import TriblerUpgrader


class UpgradeComponent(Component):
    upgrader: TriblerUpgrader


class UpgradeComponentImp(UpgradeComponent):
    async def run(self):
        await self.use(ReporterComponent, required=False)
        config = self.session.config
        notifier = self.session.notifier
        masterkey = await self.use(MasterKeyComponent)

        rest_manager = (await self.use(RESTComponent)).rest_manager

        channels_dir = config.chant.get_path_as_absolute('channels_dir', config.state_dir)

        upgrader = TriblerUpgrader(
            state_dir=config.state_dir,
            channels_dir=channels_dir,
            trustchain_keypair=masterkey.keypair,
            notifier=notifier)
        rest_manager.get_endpoint('upgrader').upgrader = upgrader
        rest_manager.get_endpoint('state').readable_status = STATE_UPGRADING_READABLE
        await upgrader.run()

        self.upgrader = upgrader


@testcomponent
class UpgradeComponentMock(UpgradeComponent):
    upgrader = Mock()

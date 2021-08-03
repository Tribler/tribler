from tribler_common.simpledefs import STATE_UPGRADING_READABLE

from tribler_core.components.interfaces.restapi import RESTComponent
from tribler_core.components.interfaces.upgrade import UpgradeComponent
from tribler_core.upgrade.upgrade import TriblerUpgrader


class UpgradeComponentImp(UpgradeComponent):
    async def run(self):
        config = self.session.config
        notifier = self.session.notifier
        trustchain_keypair = self.session.trustchain_keypair
        rest_manager = (await self.use(RESTComponent)).rest_manager

        channels_dir = config.chant.get_path_as_absolute('channels_dir', config.state_dir)

        upgrader = TriblerUpgrader(
            state_dir=config.state_dir,
            channels_dir=channels_dir,
            trustchain_keypair=trustchain_keypair,
            notifier=notifier)
        rest_manager.get_endpoint('upgrader').upgrader = upgrader
        rest_manager.get_endpoint('state').readable_status = STATE_UPGRADING_READABLE
        await upgrader.run()

        self.upgrader = upgrader
        # self.provide(mediator, UPGRADER)

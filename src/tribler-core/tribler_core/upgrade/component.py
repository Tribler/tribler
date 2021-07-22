from tribler_common.simpledefs import STATE_UPGRADING_READABLE
from tribler_core.awaitable_resources import UPGRADER, REST_MANAGER

from tribler_core.modules.component import Component
from tribler_core.upgrade.upgrade import TriblerUpgrader
from tribler_core.utilities.utilities import froze_it


@froze_it
class UpgradeComponent(Component):
    role = UPGRADER

    async def run(self, mediator):
        await super().run(mediator)

        config = mediator.config
        notifier = mediator.notifier
        trustchain_keypair = mediator.trustchain_keypair
        rest_manager = await self.use(mediator, REST_MANAGER)

        channels_dir = config.chant.get_path_as_absolute('channels_dir', config.state_dir)

        upgrader = TriblerUpgrader(
            state_dir=config.state_dir,
            channels_dir=channels_dir,
            trustchain_keypair=trustchain_keypair,
            notifier=notifier)
        rest_manager.get_endpoint('upgrader').upgrader = upgrader
        rest_manager.get_endpoint('state').readable_status = STATE_UPGRADING_READABLE
        await upgrader.run()

        self.provide(mediator, UPGRADER)

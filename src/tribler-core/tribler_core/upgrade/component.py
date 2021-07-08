from tribler_common.simpledefs import STATE_UPGRADING_READABLE

from tribler_core.modules.component import Component
from tribler_core.upgrade.upgrade import TriblerUpgrader


class UpgradeComponent(Component):
    async def run(self, mediator):
        await super().run(mediator)

        config = mediator.config
        notifier = mediator.notifier
        trustchain_keypair = mediator.trustchain_keypair

        api_manager = mediator.optional.get('api_manager', None)

        channels_dir = config.chant.get_path_as_absolute('channels_dir', config.state_dir)

        upgrader = None
        if trustchain_keypair:
            upgrader = TriblerUpgrader(
                state_dir=config.state_dir,
                channels_dir=channels_dir,
                trustchain_keypair=trustchain_keypair,
                notifier=notifier)

        if api_manager:
            api_manager.get_endpoint('upgrader').upgrader = upgrader
            api_manager.get_endpoint('state').readable_status = STATE_UPGRADING_READABLE

        await upgrader.run()

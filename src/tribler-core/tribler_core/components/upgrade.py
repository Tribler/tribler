from tribler_common.simpledefs import STATE_UPGRADING_READABLE
from tribler_core.components.base import Component
from tribler_core.components.masterkey import MasterKeyComponent
from tribler_core.components.reporter import ReporterComponent
from tribler_core.components.restapi import RESTComponent
from tribler_core.upgrade.upgrade import TriblerUpgrader


class UpgradeComponent(Component):
    upgrader: TriblerUpgrader

    async def run(self):
        await self.get_component(ReporterComponent)
        config = self.session.config
        notifier = self.session.notifier
        master_key_component = await self.require_component(MasterKeyComponent)
        channels_dir = config.chant.get_path_as_absolute('channels_dir', config.state_dir)

        self.upgrader = TriblerUpgrader(
            state_dir=config.state_dir,
            channels_dir=channels_dir,
            trustchain_keypair=master_key_component.keypair,
            notifier=notifier)

        rest_component = await self.require_component(RESTComponent)
        rest_component.rest_manager.get_endpoint('upgrader').upgrader = self.upgrader
        rest_component.rest_manager.get_endpoint('state').readable_status = STATE_UPGRADING_READABLE

        await self.upgrader.run()

from tribler_common.simpledefs import STATE_UPGRADING_READABLE

from tribler_core.components.masterkey.masterkey_component import MasterKeyComponent
from tribler_core.components.restapi import RestfulComponent
from tribler_core.upgrade.upgrade import TriblerUpgrader


class UpgradeComponent(RestfulComponent):
    upgrader: TriblerUpgrader

    async def run(self):
        await super().run()
        config = self.session.config
        notifier = self.session.notifier
        master_key_component = await self.require_component(MasterKeyComponent)
        channels_dir = config.chant.get_path_as_absolute('channels_dir', config.state_dir)

        self.upgrader = TriblerUpgrader(
            state_dir=config.state_dir,
            channels_dir=channels_dir,
            trustchain_keypair=master_key_component.keypair,
            notifier=notifier)

        await self.init_endpoints(endpoints=['upgrader'], values={'upgrader': self.upgrader})
        await self.set_readable_status(STATE_UPGRADING_READABLE)
        await self.upgrader.run()

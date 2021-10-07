from tribler_common.simpledefs import STATEDIR_DB_DIR
from tribler_core.components.ipv8.ipv8_component import Ipv8Component

from tribler_core.components.masterkey.masterkey_component import MasterKeyComponent
from tribler_core.components.restapi import RestfulComponent
from tribler_core.components.tag.community.tag_community import TagCommunity
from tribler_core.components.tag.community.tag_crypto import TagCrypto
from tribler_core.components.tag.community.tag_request_controller import TagRequestController
from tribler_core.components.tag.community.tag_validator import TagValidator
from tribler_core.components.tag.db.tag_db import TagDatabase

INFINITE = -1


class TagComponent(RestfulComponent):
    community: TagCommunity = None
    tags_db: TagDatabase = None
    _ipv8_component: Ipv8Component = None

    async def run(self):
        await super().run()

        self._ipv8_component = await self.require_component(Ipv8Component)
        master_key_component = await self.require_component(MasterKeyComponent)

        db_name = "tags_gui_test.db" if self.session.config.gui_test_mode else "tags.db"
        db_path = self.session.config.state_dir / STATEDIR_DB_DIR / db_name

        if self.session.config.gui_test_mode and db_path.exists():
            # Make sure that we start with a clean metadata database when in GUI mode every time.
            self.logger.info("Wiping tags database in GUI test mode")
            db_path.unlink(missing_ok=True)

        self.tags_db = TagDatabase(str(db_path))
        self.community = TagCommunity(
            self._ipv8_component.peer,
            self._ipv8_component.ipv8.endpoint,
            self._ipv8_component.ipv8.network,
            db=db_path,
            validator=TagValidator(),
            crypto=TagCrypto(),
            request_controller=TagRequestController()
        )

        await self.init_endpoints(
            endpoints=['tags'],
            values={'tags_db': self.tags_db, 'key': master_key_component.keypair}
        )

        self._ipv8_component.initialise_community_by_default(self.community)

    async def shutdown(self):
        await super().shutdown()
        if self._ipv8_component and self.community:
            await self._ipv8_component.unload_community(self.community)
        if self.tags_db:
            self.tags_db.shutdown()

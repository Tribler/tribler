from tribler.core.components.component import Component
from tribler.core.components.database.db.knowledge_db import KnowledgeDatabase
from tribler.core.utilities.simpledefs import STATEDIR_DB_DIR


class DatabaseComponent(Component):
    tribler_should_stop_on_component_error = True

    db: KnowledgeDatabase = None

    async def run(self):
        await super().run()

        db_path = self.session.config.state_dir / STATEDIR_DB_DIR / "tribler.db"
        if self.session.config.gui_test_mode:
            db_path = ":memory:"

        self.db = KnowledgeDatabase(str(db_path), create_tables=True)

    async def shutdown(self):
        await super().shutdown()
        if self.db:
            self.db.shutdown()

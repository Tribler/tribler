import logging
from typing import Callable, List, Optional

from tribler.core.components.database.db.tribler_database import TriblerDatabase
from tribler.core.upgrade.tribler_db.decorator import has_migration_metadata
from tribler.core.upgrade.tribler_db.scheme_migrations.scheme_migration_0 import scheme_migration_0
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.simpledefs import STATEDIR_DB_DIR


class TriblerDatabaseMigrationChain:
    """ A chain of migrations that can be executed on a TriblerDatabase.

    To create a new migration, create a new function and decorate it with the `migration` decorator. Then add it to
    the `DEFAULT_CHAIN` list.
    """

    DEFAULT_CHAIN = [
        scheme_migration_0,
        # add your migration here
    ]

    def __init__(self, state_dir: Path, chain: Optional[List[Callable]] = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.state_dir = state_dir

        db_path = self.state_dir / STATEDIR_DB_DIR / 'tribler.db'
        self.logger.info(f'Tribler DB path: {db_path}')
        self.db = TriblerDatabase(str(db_path), check_tables=False) if db_path.is_file() else None

        self.migrations = chain or self.DEFAULT_CHAIN

    def execute(self) -> bool:
        """ Execute all migrations in the chain.

        Returns: True if all migrations were executed successfully, False otherwise.
        An exception in any of the migrations will halt the execution chain and be re-raised.
        """

        if not self.db:
            return False

        for m in self.migrations:
            if not has_migration_metadata(m):
                raise NotImplementedError(f'The migration {m} should have `migration` decorator')
            m(self.db, state_dir=self.state_dir)

        return True

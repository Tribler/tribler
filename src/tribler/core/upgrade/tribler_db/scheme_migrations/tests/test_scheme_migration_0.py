from tribler.core.upgrade.tribler_db.migration_chain import TriblerDatabaseMigrationChain
from tribler.core.upgrade.tribler_db.scheme_migrations.scheme_migration_0 import scheme_migration_0
from tribler.core.utilities.pony_utils import db_session


@db_session
def test_scheme_migration_0(migration_chain: TriblerDatabaseMigrationChain):
    """ Test that the scheme_migration_0 changes the database version to 1. """
    migration_chain.db.version = 0
    migration_chain.migrations = [scheme_migration_0]

    assert migration_chain.execute()
    assert migration_chain.db.version == 1

import pytest

from tribler.core.upgrade.tribler_db.decorator import migration
from tribler.core.upgrade.tribler_db.migration_chain import TriblerDatabaseMigrationChain
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.pony_utils import db_session


def test_db_does_not_exist(tmpdir):
    """ Test that the migration chain does not execute if the database does not exist."""
    tribler_db_migration = TriblerDatabaseMigrationChain(state_dir=Path(tmpdir))
    assert not tribler_db_migration.execute()


@db_session
def test_db_execute(migration_chain: TriblerDatabaseMigrationChain):
    """ Test that the migration chain executes all the migrations step by step."""
    migration_chain.db.version = 0

    @migration(execute_only_if_version=0)
    def migration1(*_, **__):
        ...

    @migration(execute_only_if_version=1)
    def migration2(*_, **__):
        ...

    @migration(execute_only_if_version=99)
    def migration99(*_, **__):  # this migration should be skipped
        ...

    migration_chain.migrations = [
        migration1,
        migration2,
        migration99,
    ]

    # test execution of all the migration
    assert migration_chain.execute()
    assert migration_chain.db.version == 2


@db_session
def test_db_execute_no_annotation(migration_chain: TriblerDatabaseMigrationChain):
    """ Test that the migration chain raises the NotImplementedError if the migration does not have the annotation."""

    def migration_without_annotation(*_, **__):
        ...

    migration_chain.migrations = [
        migration_without_annotation
    ]

    with pytest.raises(NotImplementedError):
        migration_chain.execute()

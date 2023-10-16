import pytest

from tribler.core.components.database.db.tribler_database import TriblerDatabase
from tribler.core.upgrade.tribler_db.migration_chain import TriblerDatabaseMigrationChain
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.simpledefs import STATEDIR_DB_DIR


# pylint: disable=redefined-outer-name


@pytest.fixture
def migration_chain(tmpdir):
    """ Create an empty migration chain with an empty database."""
    db_file_name = Path(tmpdir) / STATEDIR_DB_DIR / 'tribler.db'
    db_file_name.parent.mkdir()
    TriblerDatabase(filename=str(db_file_name))
    return TriblerDatabaseMigrationChain(state_dir=Path(tmpdir), chain=[])

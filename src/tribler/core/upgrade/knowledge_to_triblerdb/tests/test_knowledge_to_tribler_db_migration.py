from unittest.mock import Mock, patch

import pytest

from tribler.core.upgrade.knowledge_to_triblerdb.migration import MigrationKnowledgeToTriblerDB
from tribler.core.upgrade.tags_to_knowledge.previous_dbs.knowledge_db import KnowledgeDatabase
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.simpledefs import STATEDIR_DB_DIR


# pylint: disable=redefined-outer-name
@pytest.fixture
def migration(tmp_path: Path):
    db_dir = tmp_path / STATEDIR_DB_DIR
    db_dir.mkdir()
    migration = MigrationKnowledgeToTriblerDB(tmp_path)
    return migration


def test_no_knowledge_db(migration: MigrationKnowledgeToTriblerDB):
    # test that in the case of missed `knowledge.db`, migration.run() returns False
    assert not migration.run()
    assert not migration.knowledge_db_path.exists()
    assert not migration.tribler_db_path.exists()


def test_move_file(migration: MigrationKnowledgeToTriblerDB):
    # Test that the migration moves the `knowledge.db` to `tribler.db`

    # create DB file
    KnowledgeDatabase(str(migration.knowledge_db_path)).shutdown()

    assert migration.knowledge_db_path.exists()
    assert not migration.tribler_db_path.exists()

    # run migration
    assert migration.run()
    assert not migration.knowledge_db_path.exists()
    assert migration.tribler_db_path.exists()


@patch('tribler.core.upgrade.knowledge_to_triblerdb.migration.shutil.move', Mock(side_effect=FileNotFoundError))
def test_exception(migration: MigrationKnowledgeToTriblerDB):
    # Test that the migration doesn't move the `knowledge.db` to `tribler.db` after unsuccessful migration procedure.

    # create DB file
    KnowledgeDatabase(str(migration.knowledge_db_path)).shutdown()

    assert migration.knowledge_db_path.exists()
    assert not migration.tribler_db_path.exists()

    # run migration
    assert not migration.run()

    assert migration.knowledge_db_path.exists()
    assert not migration.tribler_db_path.exists()

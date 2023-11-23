import sqlite3
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


from tribler.core.utilities.db_corruption_handling.base import DatabaseIsCorrupted, handle_db_if_corrupted, \
    handling_malformed_db_error

malformed_error = sqlite3.DatabaseError('database disk image is malformed')


def test_handling_malformed_db_error__no_error(db_filepath):
    # If no error is raised, the database should not be marked as corrupted
    with handling_malformed_db_error(db_filepath):
        pass

    assert not Path(str(db_filepath) + '.is_corrupted').exists()


def test_handling_malformed_db_error__malformed_error(db_filepath):
    # Malformed database errors should be handled by marking the database as corrupted
    with pytest.raises(DatabaseIsCorrupted):
        with handling_malformed_db_error(db_filepath):
            raise malformed_error

    assert Path(str(db_filepath) + '.is_corrupted').exists()


def test_handling_malformed_db_error__other_error(db_filepath):
    # Other errors should not be handled like malformed database errors
    class TestError(Exception):
        pass

    with pytest.raises(TestError):
        with handling_malformed_db_error(db_filepath):
            raise TestError()

    assert not Path(str(db_filepath) + '.is_corrupted').exists()


def test_handle_db_if_corrupted__corrupted(db_filepath: Path):
    # If the corruption marker is found, the corrupted database file is removed
    marker_path = Path(str(db_filepath) + '.is_corrupted')
    marker_path.touch()

    handle_db_if_corrupted(db_filepath)
    assert not db_filepath.exists()
    assert not marker_path.exists()


@patch('tribler.core.utilities.db_corruption_handling.base._handle_corrupted_db')
def test_handle_db_if_corrupted__not_corrupted(handle_corrupted_db: Mock, db_filepath: Path):
    # If the corruption marker is not found, the handling of the database is not performed
    handle_db_if_corrupted(db_filepath)
    handle_corrupted_db.assert_not_called()

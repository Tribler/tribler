from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Union

logger = logging.getLogger('db_corruption_handling')


class DatabaseIsCorrupted(Exception):
    pass


@contextmanager
def handling_malformed_db_error(db_filepath: Path):
    # Used in all methods of Connection and Cursor classes where the database corruption error can occur
    try:
        yield
    except Exception as e:
        if _is_malformed_db_exception(e):
            _mark_db_as_corrupted(db_filepath)
            raise DatabaseIsCorrupted(str(db_filepath)) from e
        raise


def handle_db_if_corrupted(db_filename: Union[str, Path]):
    # Checks if the database is marked as corrupted and handles it by removing the database file and the marker file
    db_path = Path(db_filename)
    marker_path = get_corrupted_db_marker_path(db_path)
    if marker_path.exists():
        _handle_corrupted_db(db_path)


def get_corrupted_db_marker_path(db_filepath: Path) -> Path:
    return Path(str(db_filepath) + '.is_corrupted')


def _is_malformed_db_exception(exception):
    return isinstance(exception, sqlite3.DatabaseError) and 'malformed' in str(exception)


def _mark_db_as_corrupted(db_filepath: Path):
    # Creates a new `*.is_corrupted` marker file alongside the database file
    marker_path = get_corrupted_db_marker_path(db_filepath)
    marker_path.touch()


def _handle_corrupted_db(db_path: Path):
    # Removes the database file and the marker file
    if db_path.exists():
        logger.warning(f'Database file was marked as corrupted, removing it: {db_path}')
        db_path.unlink()

    marker_path = get_corrupted_db_marker_path(db_path)
    if marker_path.exists():
        logger.warning(f'Removing the corrupted database marker: {marker_path}')
        marker_path.unlink()

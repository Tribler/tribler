import sqlite3
from unittest.mock import Mock, patch

import pytest

from tribler.core.utilities.db_corruption_handling.base import DatabaseIsCorrupted
from tribler.core.utilities.db_corruption_handling.sqlite_replacement import Blob, Connection, \
    Cursor, _add_method_wrapper_that_handles_malformed_db_exception, connect


# pylint: disable=protected-access


malformed_error = sqlite3.DatabaseError('database disk image is malformed')


def test_connect(db_filepath):
    connection = connect(str(db_filepath))
    assert isinstance(connection, Connection)
    connection.close()


def test_make_method_that_handles_malformed_db_exception(db_filepath):
    # Tests that the _make_method_that_handles_malformed_db_exception function creates a method that handles
    # the malformed database exception

    class BaseClass:
        method1 = Mock(return_value=Mock())

    class TestClass(BaseClass):
        _db_filepath = db_filepath

    _add_method_wrapper_that_handles_malformed_db_exception(TestClass, 'method1')

    # The method should be successfully wrapped
    assert TestClass.method1.is_wrapped
    assert TestClass.method1.__name__ == 'method1'

    test_instance = TestClass()
    result = test_instance.method1(1, 2, x=3, y=4)

    # *args and **kwargs should be passed to the original method, and the result should be returned
    BaseClass.method1.assert_called_once_with(1, 2, x=3, y=4)
    assert result is BaseClass.method1.return_value

    # When the base method raises a malformed database exception, the DatabaseIsCorrupted exception should be raised
    BaseClass.method1.side_effect = malformed_error
    with pytest.raises(DatabaseIsCorrupted):
        test_instance.method1(1, 2, x=3, y=4)


def test_connection_cursor(connection):
    cursor = connection.cursor()
    assert isinstance(cursor, Cursor)


def test_connection_iterdump(connection):
    with pytest.raises(NotImplementedError):
        connection.iterdump()


@patch('tribler.core.utilities.db_corruption_handling.sqlite_replacement.ConnectionBase.blobopen',
       Mock(side_effect=malformed_error))
def test_connection_blobopen__exception(connection):
    with pytest.raises(DatabaseIsCorrupted):
        connection.blobopen()


@patch('tribler.core.utilities.db_corruption_handling.sqlite_replacement.ConnectionBase.blobopen')
def test_connection_blobopen__no_exception(blobopen, connection):
    blobopen.return_value = Mock()
    result = connection.blobopen()

    blobopen.assert_called_once()
    assert isinstance(result, Blob)
    assert result._blob is blobopen.return_value
    assert result._db_filepath == connection._db_filepath

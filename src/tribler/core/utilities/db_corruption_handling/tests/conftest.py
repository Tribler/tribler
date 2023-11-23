import pytest

from tribler.core.utilities.db_corruption_handling.sqlite_replacement import connect


@pytest.fixture(name='db_filepath')
def db_filepath_fixture(tmp_path):
    return tmp_path / 'test.db'


@pytest.fixture(name='connection')
def connection_fixture(db_filepath):
    connection = connect(str(db_filepath))
    yield connection
    connection.close()

from unittest.mock import MagicMock, Mock, patch

from tribler.core.upgrade.db8_to_db10 import get_db_version
from tribler.core.utilities.path_util import Path


def test_get_db_version_no_db_version():
    """ Test that get_db_version returns 0 if the database version is not found."""
    cursor = Mock(return_value=Mock(fetchone=Mock(return_value=None)))
    with patch('tribler.core.upgrade.db8_to_db10.sqlite3.connect', return_value=MagicMock(cursor=cursor)):
        assert get_db_version(Path()) == 0

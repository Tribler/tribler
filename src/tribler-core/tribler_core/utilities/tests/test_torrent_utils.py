from unittest.mock import Mock

from tribler_core.tests.tools.common import TESTS_DATA_DIR
from tribler_core.utilities.torrent_utils import create_torrent_file, get_info_from_handle


TORRENT_DATA_DIR = TESTS_DATA_DIR / "torrent_creation_files"
FILE1_NAME = "file1.txt"
FILE2_NAME = "file2.txt"


def get_params():
    return {"comment": "Proudly created by Tribler", "created by": "someone",
            "announce": "http://tracker.com/announce", "announce-list": ["http://tracker.com/announce"],
            "httpseeds": "http://seed.com", "urllist": "http://urlseed.com/seed.php",
            "nodes": []}


def verify_created_torrent(result):
    assert isinstance(result, dict)
    assert result["base_path"] == TORRENT_DATA_DIR
    assert result["success"]


def test_create_torrent_one_file():
    result = create_torrent_file([TORRENT_DATA_DIR / FILE1_NAME], get_params())
    verify_created_torrent(result)


def test_create_torrent_one_file_2():
    result = create_torrent_file([TORRENT_DATA_DIR / FILE2_NAME], {})
    verify_created_torrent(result)


def test_create_torrent_with_nodes():
    params = get_params()
    params["nodes"] = [("127.0.0.1", 1234)]
    result = create_torrent_file([TORRENT_DATA_DIR / FILE1_NAME], params)
    verify_created_torrent(result)


def test_create_torrent_two_files():
    file_path_list = [TORRENT_DATA_DIR / FILE1_NAME,
                      TORRENT_DATA_DIR / FILE2_NAME]
    result = create_torrent_file(file_path_list, get_params())
    assert result["success"]


def test_get_info_from_handle():
    mock_handle = Mock()

    def mock_get_torrent_file():
        raise RuntimeError

    mock_handle.torrent_file = mock_get_torrent_file
    assert not get_info_from_handle(mock_handle)

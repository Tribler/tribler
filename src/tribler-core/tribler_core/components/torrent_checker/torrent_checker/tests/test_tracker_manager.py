import pytest

from tribler_core.components.torrent_checker.torrent_checker.tracker_manager import TrackerManager


@pytest.fixture
def tracker_manager(tmp_path, metadata_store):
    return TrackerManager(state_dir=tmp_path, metadata_store=metadata_store)


def test_add_tracker(tracker_manager):
    """
    Test whether adding a tracker works correctly
    """
    tracker_manager.add_tracker("http://test1.com")
    assert not tracker_manager.get_tracker_info("http://test1.com")

    tracker_manager.add_tracker("http://test1.com:80/announce")
    assert tracker_manager.get_tracker_info("http://test1.com:80/announce")


def test_remove_tracker(tracker_manager):
    """
    Test whether removing a tracker works correctly
    """
    tracker_manager.add_tracker("http://test1.com:80/announce")
    assert tracker_manager.get_tracker_info("http://test1.com:80/announce")
    tracker_manager.remove_tracker("http://test1.com:80/announce")
    assert not tracker_manager.get_tracker_info("http://test1.com:80/announce")


def test_get_tracker_info(tracker_manager):
    """
    Test whether the correct tracker info is returned when requesting it in the tracker manager
    """
    assert not tracker_manager.get_tracker_info("http://nonexisting.com")

    tracker_manager.add_tracker("http://test1.com:80/announce")
    assert tracker_manager.get_tracker_info("http://test1.com:80/announce")


def test_update_tracker_info(tracker_manager):
    """
    Test whether the tracker info is correctly updated
    """
    tracker_manager.update_tracker_info("http://nonexisting.com", True)
    assert not tracker_manager.get_tracker_info("http://nonexisting.com")

    tracker_manager.add_tracker("http://test1.com:80/announce")
    tracker_manager.update_tracker_info("http://test1.com/announce", False)

    tracker_info = tracker_manager.get_tracker_info("http://test1.com/announce")
    assert tracker_info
    assert tracker_info['failures'] == 1

    tracker_manager.update_tracker_info("http://test1.com/announce", True)
    tracker_info = tracker_manager.get_tracker_info("http://test1.com/announce")
    assert tracker_info['is_alive']


def test_get_tracker_for_check(tracker_manager):
    """
    Test whether the correct tracker is returned when fetching the next eligable tracker for the auto check
    """
    assert not tracker_manager.get_next_tracker_for_auto_check()

    tracker_manager.add_tracker("http://test1.com:80/announce")
    assert tracker_manager.get_next_tracker_for_auto_check().url == 'http://test1.com/announce'


def test_get_tracker_for_check_blacklist(tracker_manager):
    """
    Test whether the next tracker for autocheck is not in the blacklist
    """
    assert not tracker_manager.get_next_tracker_for_auto_check()

    tracker_manager.add_tracker("http://test1.com:80/announce")
    tracker_manager.blacklist.append("http://test1.com/announce")
    assert not tracker_manager.get_next_tracker_for_auto_check()


def test_load_blacklist_from_file_none(tracker_manager):
    """
    Test if we correctly load a blacklist without entries
    """
    blacklist_file = tracker_manager.state_dir / "tracker_blacklist.txt"
    with open(blacklist_file, 'w') as f:
        f.write("")

    tracker_manager.load_blacklist()

    assert not tracker_manager.blacklist


def test_load_blacklist_from_file_single(tracker_manager):
    """
    Test if we correctly load a blacklist entry from a file
    """
    blacklist_file = tracker_manager.state_dir / "tracker_blacklist.txt"
    with open(blacklist_file, 'w') as f:
        f.write("http://test1.com/announce")

    tracker_manager.load_blacklist()

    assert "http://test1.com/announce" in tracker_manager.blacklist


def test_load_blacklist_from_file_multiple(tracker_manager):
    """
    Test if we correctly load blacklist entries from a file
    """
    blacklist_file = tracker_manager.state_dir / "tracker_blacklist.txt"
    with open(blacklist_file, 'w') as f:
        f.write("http://test1.com/announce\nhttp://test2.com/announce")

    tracker_manager.load_blacklist()

    assert "http://test1.com/announce" in tracker_manager.blacklist
    assert "http://test2.com/announce" in tracker_manager.blacklist

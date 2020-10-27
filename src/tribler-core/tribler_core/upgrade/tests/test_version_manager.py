import filecmp
import json
import os

from tribler_common.simpledefs import (
    STATEDIR_CHANNELS_DIR,
    STATEDIR_CHECKPOINT_DIR,
    STATEDIR_DB_DIR,
)

from tribler_core.tests.tools.common import TESTS_DATA_DIR
from tribler_core.upgrade.version_manager import (
    VERSION_HISTORY_FILE,
    VersionHistory,
    copy_state_directory,
    fork_state_directory_if_necessary,
    version_to_dirname,
)
from tribler_core.utilities.path_util import Path

DUMMY_STATE_DIR = TESTS_DATA_DIR / "state_dir_dummy"


def test_version_to_dirname():
    assert version_to_dirname("7.5.4") == "7.5"
    assert version_to_dirname("7.5.4-GIT") == "7.5"
    assert version_to_dirname("7.5") == "7.5"
    assert version_to_dirname("7.5.0") == "7.5"

    # These are special cases of 7.4.x series that used patch version naming
    assert version_to_dirname("7.4.4") == "7.4.4"

    # Versions earlier then 7.4 should return no dirname
    assert not version_to_dirname("7.3.0")


def test_read_write_version_history(tmpdir):
    version_history_path = Path(tmpdir) / "test_version_history.json"
    version_history = VersionHistory(version_history_path)

    # If there is no version history file, no information about last version is available
    assert not version_history.version_history['last_version']
    assert version_history.version_history['history'] == {}

    # Saving and loading the version again
    new_version = '100.100.100'
    version_history.update(new_version)
    assert version_history.last_version == new_version
    version_history2 = VersionHistory(version_history_path)
    assert version_history.version_history == version_history2.version_history


def test_get_last_upgradable_version_based_on_dir(tmpdir):
    """
    Scenario: 5 versions in the history file, but state directory only for one of those exists.
    The second version in the list has higher version than the current one, and has dir too.
    Test that that only the most recent lower version will be selected as the upgrade source.
    """
    root_state_dir = Path(tmpdir)
    json_dict = {"last_version": "100.1.1", "history": dict()}
    json_dict["history"]["1"] = "100.1.1"  # no dir - bad
    json_dict["history"]["2"] = "99.2.3"  # dir in place, earlier than 3 - bad
    (root_state_dir / "99.2").mkdir()
    json_dict["history"]["3"] = "92.3.4"  # dir in place, more recent than 2, - good
    (root_state_dir / "92.3").mkdir()
    json_dict["history"]["4"] = "200.2.3"  # version higher than code version
    (root_state_dir / "200.2").mkdir()
    json_dict["history"]["5"] = "94.3.4"  # version OK, no dir - bad

    (root_state_dir / VERSION_HISTORY_FILE).write_text(json.dumps(json_dict))

    version_history = VersionHistory(root_state_dir / VERSION_HISTORY_FILE)
    last_upgradable_version = version_history.get_last_upgradable_version(root_state_dir, "102.1.1")
    assert last_upgradable_version == "92.3.4"


def test_fork_state_directory(tmpdir_factory):
    from tribler_core.upgrade import version_manager

    result = []

    def mock_copy_state_directory(src, tgt):
        result.clear()
        result.extend([src, tgt])

    version_manager.copy_state_directory = mock_copy_state_directory

    # Scenario 1: the last used version has the same major/minor number as the code version, dir in place
    # no forking should happen, but version_history should be updated nonetheless
    tmpdir = tmpdir_factory.mktemp("scenario1")
    result.clear()
    root_state_dir = Path(tmpdir)
    json_dict = {"last_version": "120.1.1", "history": dict()}
    json_dict["history"]["2"] = "120.1.1"
    (root_state_dir / "120.1").mkdir()
    (root_state_dir / VERSION_HISTORY_FILE).write_text(json.dumps(json_dict))

    code_version = "120.1.2"

    fork_state_directory_if_necessary(root_state_dir, code_version)
    assert result == []
    assert VersionHistory(root_state_dir / VERSION_HISTORY_FILE).last_version == code_version

    # Scenario 2: the last used version minor is lower than the code version, directory exists
    # normal upgrade scenario, dir should be forked and version_history should be updated
    tmpdir = tmpdir_factory.mktemp("scenario2")
    result.clear()
    root_state_dir = Path(tmpdir)
    json_dict = {"last_version": "120.1.1", "history": dict()}
    json_dict["history"]["2"] = "120.1.1"
    (root_state_dir / "120.1").mkdir()
    (root_state_dir / VERSION_HISTORY_FILE).write_text(json.dumps(json_dict))

    code_version = "120.3.2"

    fork_state_directory_if_necessary(root_state_dir, code_version)
    assert [d.name for d in result] == ["120.1", "120.3"]
    assert VersionHistory(root_state_dir / VERSION_HISTORY_FILE).last_version == code_version

    # Scenario 3: upgrade from 7.3 (unversioned dir)
    # dir should be forked and version_history should be created
    tmpdir = tmpdir_factory.mktemp("scenario3")
    result.clear()
    root_state_dir = Path(tmpdir)
    code_version = "120.3.2"
    (root_state_dir / "triblerd.conf").write_text("foo")  # 7.3 presence marker
    fork_state_directory_if_necessary(root_state_dir, code_version)
    assert [d.name for d in result] == [root_state_dir.name, "120.3"]
    assert VersionHistory(root_state_dir / VERSION_HISTORY_FILE).last_version == code_version

    # Scenario 4: the user tried to upgrade to some tribler version, but failed. Now he tries again with
    # higher patch version of the same major/minor version.
    # The most recently used dir with major/minor version lower than the code version should be forked,
    # while the previous code version state directory should be renamed to a backup.
    tmpdir = tmpdir_factory.mktemp("scenario4")
    result.clear()
    root_state_dir = Path(tmpdir)
    json_dict = {"last_version": "120.2.1", "history": dict()}
    # The user  was on 120.2
    json_dict["history"]["2"] = "120.2.0"
    (root_state_dir / "120.2").mkdir()

    # The user tried 120.3, they did not like it
    json_dict["history"]["3"] = "120.3.0"
    (root_state_dir / "120.3").mkdir()

    # The user returned to 120.2 and continued to use it
    json_dict["history"]["4"] = "120.2.1"
    (root_state_dir / VERSION_HISTORY_FILE).write_text(json.dumps(json_dict))

    # Now user tries 120.3.2 which has a higher patch version than his previous attempt at 120.3 series
    code_version = "120.3.2"

    fork_state_directory_if_necessary(root_state_dir, code_version)
    assert [d.name for d in result] == ["120.2", "120.3"]
    # Check that the older 120.3 directory is not deleted, but instead renamed as a backup
    assert "unused_v120.3" in [d[:13] for d in os.listdir(root_state_dir)]
    assert VersionHistory(root_state_dir / VERSION_HISTORY_FILE).last_version == code_version

    # Scenario 5: normal upgrade scenario, but from 7.4.x version (dir includes patch number)
    tmpdir = tmpdir_factory.mktemp("scenario5")
    result.clear()
    root_state_dir = Path(tmpdir)
    json_dict = {"last_version": "7.4.4", "history": dict()}
    json_dict["history"]["2"] = "7.4.4"
    (root_state_dir / "7.4.4").mkdir()
    (root_state_dir / VERSION_HISTORY_FILE).write_text(json.dumps(json_dict))

    code_version = "7.5.1"

    fork_state_directory_if_necessary(root_state_dir, code_version)
    assert [d.name for d in result] == ["7.4.4", "7.5"]
    assert VersionHistory(root_state_dir / VERSION_HISTORY_FILE).last_version == code_version


def test_copy_state_directory(tmpdir):
    src_dir = DUMMY_STATE_DIR
    tgt_dir = Path(tmpdir) / "100.100.100"
    copy_state_directory(src_dir, tgt_dir)

    # Make sure only the neccessary stuff is copied, and junk is omitted
    backup_list = {STATEDIR_DB_DIR, STATEDIR_CHECKPOINT_DIR, STATEDIR_CHANNELS_DIR,
                   'ec_multichain.pem', 'ecpub_multichain.pem', 'ec_trustchain_testnet.pem',
                   'ecpub_trustchain_testnet.pem', 'triblerd.conf'}
    tgt_list = set(os.listdir(tgt_dir))
    assert backup_list & tgt_list == backup_list

    # Make sure the contents in the before and after upgrade directories are the same
    assert filecmp.cmp(src_dir / 'ec_multichain.pem', tgt_dir / 'ec_multichain.pem')

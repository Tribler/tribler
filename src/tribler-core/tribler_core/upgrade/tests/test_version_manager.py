import filecmp
import json
import os
import time
from pathlib import Path

import pytest

from tribler_common.simpledefs import STATEDIR_CHANNELS_DIR, STATEDIR_CHECKPOINT_DIR, STATEDIR_DB_DIR
from tribler_common.version_manager import (
    TriblerVersion,
    VERSION_HISTORY_FILENAME,
    VersionError,
    VersionHistory,
    remove_state_dirs,
)

import tribler_core.version
from tribler_core.tests.tools.common import TESTS_DATA_DIR

DUMMY_STATE_DIR = TESTS_DATA_DIR / "state_dir_dummy"


def test_version_to_dirname():
    root_path = Path('/ROOT')

    def version_to_dirname(version_str):
        return TriblerVersion(root_path, version_str).directory

    assert version_to_dirname("7.5.4") == Path("/ROOT/7.5")
    assert version_to_dirname("7.5.4-GIT") == Path("/ROOT/7.5")
    assert version_to_dirname("7.5") == Path("/ROOT/7.5")
    assert version_to_dirname("7.5.0") == Path("/ROOT/7.5")

    # These are special cases of 7.4.x series that used patch version naming
    assert version_to_dirname("7.4.4") == Path("/ROOT/7.4.4")

    # Versions earlier then 7.4 should return root directory
    assert version_to_dirname("7.3.0") == Path("/ROOT")


def test_read_write_version_history(tmpdir):
    root_path = Path(tmpdir)
    history = VersionHistory(root_path, code_version_id='100.100.100')

    assert history.root_state_dir == root_path
    assert history.file_path == root_path / "version_history.json"
    assert history.file_data == {"last_version": None, "history": {}}

    # If there is no version history file, no information about last version is available
    assert history.last_run_version is None
    assert not history.versions

    assert history.code_version.version_str == '100.100.100'
    assert history.code_version.major_minor == (100, 100)

    # Saving and loading the version again
    history.save()

    history2 = VersionHistory(root_path, code_version_id='100.100.100')
    # version was not added to history as the state directory does not exist
    assert history2.last_run_version is None
    assert not history2.versions
    assert not history2.versions_by_number
    assert not history2.versions_by_time

    state_dir: Path = root_path / "100.100"
    state_dir.mkdir()

    history3 = VersionHistory(root_path, code_version_id='100.100.100')
    assert history3.last_run_version is not None
    assert history3.last_run_version.version_str == '100.100.100'
    assert history3.last_run_version.directory == state_dir
    assert len(history3.versions) == 1
    assert (100, 100) in history3.versions
    assert history3.versions[100, 100] == history3.last_run_version
    assert history3.versions_by_number == [history3.last_run_version]
    assert history3.versions_by_time == [history3.last_run_version]


def test_get_last_upgradable_version_based_on_dir(tmpdir):
    """
    Scenario: 5 versions in the history file, but state directory only for one of those exists.
    The second version in the list has higher version than the current one, and has dir too.
    Test that only the most recent lower version will be selected as the upgrade source.
    """
    root_state_dir = Path(tmpdir)
    json_dict = {"last_version": "100.1.1", "history": dict()}
    json_dict["history"]["1"] = "100.1.1"  # no dir - bad
    json_dict["history"]["2"] = "99.2.3"  # dir in place, earlier than 3 - bad
    (root_state_dir / "102.1").mkdir()
    json_dict["history"]["3"] = "102.1.0"  # version OK, got dir, same major/minor version as us - ignore
    (root_state_dir / "99.2").mkdir()
    json_dict["history"]["4"] = "92.3.4"  # dir in place, more recent than 2, - good
    (root_state_dir / "92.3").mkdir()
    json_dict["history"]["5"] = "200.2.3"  # version higher than code version
    (root_state_dir / "200.2").mkdir()
    json_dict["history"]["6"] = "94.3.4"  # version OK, no dir - bad

    (root_state_dir / VERSION_HISTORY_FILENAME).write_text(json.dumps(json_dict))

    history = VersionHistory(root_state_dir, code_version_id="102.1.1")
    assert history.code_version.can_be_copied_from is not None
    assert history.code_version.can_be_copied_from.version_str == "92.3.4"


def test_fork_state_directory(tmpdir_factory):
    # Scenario 1: the last used version has the same major/minor number as the code version, dir in place
    # no forking should happen, but version_history should be updated nonetheless
    tmpdir = tmpdir_factory.mktemp("scenario1")
    root_state_dir = Path(tmpdir)
    json_dict = {"last_version": "120.1.1", "history": dict()}
    json_dict["history"]["2"] = "120.1.1"
    state_dir = root_state_dir / "120.1"
    state_dir.mkdir()
    (root_state_dir / VERSION_HISTORY_FILENAME).write_text(json.dumps(json_dict))
    code_version_id = "120.1.2"

    history = VersionHistory(root_state_dir, code_version_id)
    assert history.last_run_version is not None
    assert history.last_run_version.directory == state_dir
    assert history.last_run_version != history.code_version
    assert history.code_version.directory == state_dir
    assert history.code_version.version_str != history.last_run_version.version_str
    assert not history.code_version.should_be_copied
    assert not history.code_version.should_recreate_directory

    forked_from = history.fork_state_directory_if_necessary()
    assert forked_from is None
    history_saved = history.save_if_necessary()
    assert history_saved

    history2 = VersionHistory(root_state_dir, code_version_id)
    assert history2.last_run_version == history2.code_version
    assert history2.last_run_version.version_str == code_version_id

    # Scenario 2: the last used version minor is lower than the code version, directory exists
    # normal upgrade scenario, dir should be forked and version_history should be updated
    tmpdir = tmpdir_factory.mktemp("scenario2")
    root_state_dir = Path(tmpdir)
    json_dict = {"last_version": "120.1.1", "history": dict()}
    json_dict["history"]["1"] = "120.1.1"
    state_dir = root_state_dir / "120.1"
    state_dir.mkdir()
    (root_state_dir / VERSION_HISTORY_FILENAME).write_text(json.dumps(json_dict))
    code_version_id = "120.3.2"

    history = VersionHistory(root_state_dir, code_version_id)
    assert history.last_run_version is not None
    assert history.last_run_version.directory == state_dir
    assert history.code_version != history.last_run_version
    assert history.code_version.directory != state_dir
    assert history.code_version.version_str != history.last_run_version.version_str
    assert history.code_version.should_be_copied
    assert not history.code_version.should_recreate_directory
    assert not history.code_version.directory.exists()

    forked_from = history.fork_state_directory_if_necessary()
    assert history.code_version.directory.exists()
    assert forked_from is not None and forked_from.version_str == "120.1.1"
    history_saved = history.save_if_necessary()
    assert history_saved

    history2 = VersionHistory(root_state_dir, code_version_id)
    assert history2.last_run_version == history2.code_version
    assert history2.last_run_version.version_str == code_version_id

    # Scenario 3: upgrade from 7.3 (unversioned dir)
    # dir should be forked and version_history should be created
    tmpdir = tmpdir_factory.mktemp("scenario3")
    root_state_dir = Path(tmpdir)
    (root_state_dir / "triblerd.conf").write_text("foo")  # 7.3 presence marker
    code_version_id = "120.3.2"

    history = VersionHistory(root_state_dir, code_version_id)
    assert history.last_run_version is not None
    assert history.last_run_version.directory == root_state_dir
    assert history.code_version != history.last_run_version
    assert history.code_version.directory != root_state_dir
    assert history.code_version.should_be_copied
    assert history.code_version.can_be_copied_from is not None
    assert history.code_version.can_be_copied_from.version_str == "7.3"
    assert not history.code_version.should_recreate_directory
    assert not history.code_version.directory.exists()

    forked_from = history.fork_state_directory_if_necessary()
    assert history.code_version.directory.exists()
    assert forked_from is not None and forked_from.version_str == "7.3"
    history_saved = history.save_if_necessary()
    assert history_saved

    history2 = VersionHistory(root_state_dir, code_version_id)
    assert history2.last_run_version == history2.code_version
    assert history2.last_run_version.version_str == code_version_id

    # Scenario 4: the user tried to upgrade to some tribler version, but failed. Now he tries again with
    # higher patch version of the same major/minor version.
    # The most recently used dir with major/minor version lower than the code version should be forked,
    # while the previous code version state directory should be renamed to a backup.
    tmpdir = tmpdir_factory.mktemp("scenario4")
    root_state_dir = Path(tmpdir)
    json_dict = {"last_version": "120.2.1", "history": dict()}
    # The user  was on 120.2
    json_dict["history"]["1"] = "120.2.0"
    state_dir_1 = root_state_dir / "120.2"
    state_dir_1.mkdir()

    # The user tried 120.3, they did not like it
    json_dict["history"]["2"] = "120.3.0"
    state_dir_2 = root_state_dir / "120.3"
    state_dir_2.mkdir()

    # The user returned to 120.2 and continued to use it
    json_dict["history"]["3"] = "120.2.1"
    (root_state_dir / VERSION_HISTORY_FILENAME).write_text(json.dumps(json_dict))

    # Now user tries 120.3.2 which has a higher patch version than his previous attempt at 120.3 series
    code_version_id = "120.3.2"

    history = VersionHistory(root_state_dir, code_version_id)
    assert history.last_run_version is not None
    assert history.last_run_version.directory == state_dir_1
    assert history.code_version != history.last_run_version
    assert history.code_version.directory != root_state_dir
    assert history.code_version.should_be_copied
    assert history.code_version.can_be_copied_from is not None
    assert history.code_version.can_be_copied_from.version_str == "120.2.1"
    assert history.code_version.directory.exists()
    assert history.code_version.should_recreate_directory

    forked_from = history.fork_state_directory_if_necessary()
    assert history.code_version.directory.exists()
    assert forked_from is not None and forked_from.version_str == "120.2.1"
    history_saved = history.save_if_necessary()
    assert history_saved
    # Check that the older 120.3 directory is not deleted, but instead renamed as a backup
    assert list(root_state_dir.glob("unused_v120.3_*"))

    history2 = VersionHistory(root_state_dir, code_version_id)
    assert history2.last_run_version == history2.code_version
    assert history2.last_run_version.version_str == code_version_id

    # Scenario 5: normal upgrade scenario, but from 7.4.x version (dir includes patch number)
    tmpdir = tmpdir_factory.mktemp("scenario5")
    root_state_dir = Path(tmpdir)
    json_dict = {"last_version": "7.4.4", "history": dict()}
    json_dict["history"]["2"] = "7.4.4"
    state_dir = root_state_dir / "7.4.4"
    state_dir.mkdir()
    (root_state_dir / VERSION_HISTORY_FILENAME).write_text(json.dumps(json_dict))

    code_version_id = "7.5.1"

    history = VersionHistory(root_state_dir, code_version_id)
    assert history.last_run_version is not None
    assert history.last_run_version.directory == state_dir
    assert history.code_version != history.last_run_version
    assert history.code_version.directory != root_state_dir
    assert history.code_version.should_be_copied
    assert history.code_version.can_be_copied_from is not None
    assert history.code_version.can_be_copied_from.version_str == "7.4.4"
    assert not history.code_version.directory.exists()
    assert not history.code_version.should_recreate_directory

    forked_from = history.fork_state_directory_if_necessary()
    assert history.code_version.directory.exists()
    assert forked_from is not None and forked_from.version_str == "7.4.4"
    history_saved = history.save_if_necessary()
    assert history_saved

    history2 = VersionHistory(root_state_dir, code_version_id)
    assert history2.last_run_version == history2.code_version
    assert history2.last_run_version.version_str == code_version_id


def test_copy_state_directory(tmpdir):
    src_dir = DUMMY_STATE_DIR
    tgt_dir = Path(tmpdir) / "100.100"

    root_state_dir = Path(tmpdir)
    v1 = TriblerVersion(root_state_dir, "7.8.9")
    v1.directory = src_dir

    v2 = TriblerVersion(root_state_dir, "100.100.100")
    assert v2.directory == tgt_dir

    v2.copy_state_from(v1)

    # Make sure only the neccessary stuff is copied, and junk is omitted
    backup_list = {STATEDIR_DB_DIR, STATEDIR_CHECKPOINT_DIR, STATEDIR_CHANNELS_DIR,
                   'ec_multichain.pem', 'ecpub_multichain.pem', 'ec_trustchain_testnet.pem',
                   'ecpub_trustchain_testnet.pem', 'triblerd.conf'}
    tgt_list = set(os.listdir(tgt_dir))
    assert backup_list & tgt_list == backup_list

    # Make sure the contents in the before and after upgrade directories are the same
    assert filecmp.cmp(src_dir / 'ec_multichain.pem', tgt_dir / 'ec_multichain.pem')


# pylint: disable=too-many-locals
def test_get_disposable_state_directories(tmpdir_factory):
    tmpdir = tmpdir_factory.mktemp("scenario")
    root_state_dir = Path(tmpdir)

    # Scenario: multiple versions of state directory exists, <major.minor.version>. Then on disposable directories
    # based on the current version show all other directories except the last version.

    major_versions = [8, 7]
    minor_versions = list(range(10))
    patch_versions = list(range(3))

    last_version = "8.9.2"
    last_version_dir = root_state_dir / "8.9"
    second_last_version_dir = root_state_dir / "8.8"

    version_history = {"last_version": last_version, "history": dict()}
    base_install_ts = time.time() - 1000  # some timestamp in the past

    # Create state directories for all older versions
    for major in major_versions:
        for minor in reversed(minor_versions):
            for patch in patch_versions:
                version = f"{major}.{minor}.{patch}"
                version_dir = f"{major}.{minor}"

                # Set install time in order of version. i.e. newer version are installed later
                version_install_ts = base_install_ts + major * 100 + minor * 10 + patch
                version_history["history"][version_install_ts] = version

                # Create an empty version directory if does not exist
                (root_state_dir / version_dir).mkdir(exist_ok=True)

    unused1 = root_state_dir / "unused_v8.9_1234567"
    unused2 = root_state_dir / "unused_v9.0_7654321"
    unused1.mkdir()
    unused2.mkdir()

    # Write the version history file before checking disposable directories
    (root_state_dir / VERSION_HISTORY_FILENAME).write_text(json.dumps(version_history))

    code_version_id = "9.0.0"
    history = VersionHistory(root_state_dir, code_version_id)

    # Case 1: Skip last two versions, then those two last directories will not returned as disposable dirs.
    disposable_dirs = history.get_disposable_state_directories()
    assert last_version_dir in disposable_dirs
    assert second_last_version_dir in disposable_dirs
    assert unused1 in disposable_dirs
    assert unused2 in disposable_dirs

    # Case 2: Skip only one version
    disposable_dirs = history.get_disposable_state_directories(skip_versions=1, include_unused=False)
    assert last_version_dir not in disposable_dirs
    assert second_last_version_dir in disposable_dirs
    assert unused1 not in disposable_dirs
    assert unused2 not in disposable_dirs


def test_installed_versions_and_removal(tmpdir_factory):
    tmpdir = tmpdir_factory.mktemp("install_version_test")
    root_state_dir = Path(tmpdir)

    # create current version directory
    code_version_id = "8.9.10"
    current_version_dir = root_state_dir / "8.9"
    current_version_dir.mkdir()

    major_versions = [7, 8]
    minor_versions = [5, 6, 7, 8]

    version_history = {"last_version": "7.8", "history": dict()}
    base_install_ts = time.time() - 1000  # some timestamp in the past

    for major in major_versions:
        for minor in minor_versions:
            version_str = f"{major}.{minor}"
            (root_state_dir / version_str).mkdir(exist_ok=True)
            # Set install time in order of version. i.e. newer version are installed later
            version_install_ts = base_install_ts + major * 100 + minor * 10
            version_history["history"][version_install_ts] = version_str

    (root_state_dir / VERSION_HISTORY_FILENAME).write_text(json.dumps(version_history))

    history = VersionHistory(root_state_dir, code_version_id)

    # 1. Default values
    installed_versions = history.get_installed_versions()
    assert history.code_version in installed_versions
    assert len(installed_versions) == len(major_versions) * len(minor_versions) + 1  # including the current version

    # 2. exclude current version
    installed_versions = history.get_installed_versions(with_code_version=False)
    assert history.code_version not in installed_versions
    assert len(installed_versions) == len(major_versions) * len(minor_versions)  # the current version not included

    # 3. Delete a few versions
    history.versions[7, 5].delete_state()
    history.versions[7, 6].delete_state()

    installed_versions = history.get_installed_versions(with_code_version=False)
    assert current_version_dir not in installed_versions
    assert len(installed_versions) == len(major_versions) * len(minor_versions) - 2


# pylint: disable=too-many-statements
def test_coverage(tmpdir):
    root_state_dir = Path(tmpdir)
    v1 = TriblerVersion(root_state_dir, "7.3.1a")
    assert repr(v1) == '<TriblerVersion{7.3.1a}>'
    with pytest.raises(VersionError, match='Cannot rename root directory'):
        v1.rename_directory("foo")

    v2 = TriblerVersion(root_state_dir, "7.8.1")
    assert v2.directory == root_state_dir / "7.8"
    v2.directory.mkdir()
    v2.rename_directory("renamed")
    assert list(root_state_dir.glob("renamed7.8_*"))
    assert v2.directory == root_state_dir / "7.8"

    v2.directory.mkdir()
    (v2.directory / "foobar.txt").write_text("abc")
    v2.delete_state()
    assert list(root_state_dir.glob("deleted_v7.8_*"))

    v2.directory = Path(DUMMY_STATE_DIR)
    size = v2.calc_state_size()
    assert size > 0

    v3 = TriblerVersion(root_state_dir, "7.7")
    v3.directory.mkdir()
    v3.deleted = True
    v3.delete_state()
    assert v3.directory.exists()
    v3.deleted = False
    v3.delete_state()
    assert not v3.directory.exists()

    v4 = TriblerVersion(root_state_dir, "7.5.1a")
    v4.directory.mkdir()
    (v4.directory / 'triblerd.conf').write_text("abc")
    v5 = TriblerVersion(root_state_dir, "7.6.1b")
    v5.directory.mkdir()
    with pytest.raises(VersionError, match='Directory for version 7.6.1b already exists'):
        v5.copy_state_from(v4)
    v5.copy_state_from(v4, overwrite=True)
    assert (v5.directory / 'triblerd.conf').read_text() == "abc"

    (root_state_dir / "version_history.json").write_text('{"last_version": "7.7"}')

    with pytest.raises(VersionError, match="Invalid history file structure"):
        VersionHistory(root_state_dir)

    (root_state_dir / "version_history.json").write_text(
        '{"last_version": "7.7", "history": {"1": "7.3.1a", "2": "7.7", "3": "7.5.1a", "4": "7.6.1b", "5": "7.8.1"}}')

    (root_state_dir / "sqlite").mkdir()
    (root_state_dir / "channels").mkdir()
    (root_state_dir / 'triblerd.conf').write_text("abc")

    history = VersionHistory(root_state_dir)
    assert history.code_version.version_str == tribler_core.version.version_id
    assert repr(history) == "<VersionHistory[(7, 6), (7, 5), (7, 3)]>"

    dirs = history.get_disposable_state_directories()
    names = [d.name for d in dirs]
    assert len(names) == 5
    for name in names:
        assert name in ('7.5', '7.6', 'channels', 'sqlite') or name.startswith("deleted_v7.8_")

    remove_state_dirs(root_state_dir, names)
    assert not (root_state_dir / "7.5").exists()
    assert not (root_state_dir / "7.6").exists()
    assert not (root_state_dir / "channels").exists()
    assert not (root_state_dir / "sqlite").exists()

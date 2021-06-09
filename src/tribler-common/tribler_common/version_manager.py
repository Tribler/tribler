from __future__ import annotations

import json
import os.path
import shutil
import time
from collections import OrderedDict
from datetime import datetime
from distutils.version import LooseVersion
from operator import attrgetter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from tribler_common.simpledefs import STATEDIR_CHANNELS_DIR, STATEDIR_CHECKPOINT_DIR, STATEDIR_DB_DIR

import tribler_core.version

VERSION_HISTORY_FILENAME = "version_history.json"

# Copy other important files: keys and config
STATE_FILES_TO_COPY = (
    'ec_multichain.pem',
    'ecpub_multichain.pem',
    'ec_trustchain_testnet.pem',
    'ecpub_trustchain_testnet.pem',
    'triblerd.conf',
)

STATE_DIRS_TO_COPY = (STATEDIR_DB_DIR, STATEDIR_CHECKPOINT_DIR, STATEDIR_CHANNELS_DIR)

"""
The main purpose of the Version Management mechanism is to provide a safe fallback for both users
and developers during upgrades of major/minor (non-patch) versions. The rules are:
1. Every (major.minor) X.Y version has a separate state directory inside the root state directory.
2. Patch versions (x.y.Z) do not get a separate state directory.
3. The history of Tribler versions is written into version_history.json file in the root state directory.
3. When a new Tribler version is launched, it looks into the root state directory and version_history.json
    to determine if copying the state from the previous version is necessary:
     a. if the last used version is the same version as the code version AND the corresponding state directory
         exists, do nothing.
     b. otherwise, look for the most recently used Tribler version that has lower major/minor version that has
         state directory and copy state files from it into the new state directory named according to code version.

 IMPORTANT: If there already exists a state directory for the code version (the same major/minor numbers),
  but the history file indicates that the most recent used Tribler version with the same major/minor version
  has a lower patch version (x.y.<Z>), we rename the existing dir to unused_v<version>_<timestamp>.
  This corresponds to a situation where the user tried some version of Tribler and then went back to the previous
  version, but now tries again the same series with a higher patch version. This is a most typical scenario
  in which the version management system comes into play.
  Example:
   the user installed 7.5.0 and used it for some time, then tried to upgraded to 7.6.0 and failed. Then the user
   went back to 7.5.0. After 7.6.1 was released, the user tried upgrading again. When run, 7.6.1 looked at the
   version_history.json and detected that the last used version was 7.5.0. It tried to create the 7.6 directory
   but failed because 7.6 was already installed before. Then, version management procedure renamed the old 7.6
   directory to unused_v7.6_<timestamp> and created 7.6 directory anew, and copied 7.5 contents into it.

In some sense, the system works exactly as GIT does: it "branches" from the last-non conflicting version dir
and "stashes" the state dirs with conflicting names by renaming them.

Note that due to failures in design pre-7.4 series and 7.4.x series get special treatment.
"""


class VersionError(Exception):
    pass


# pylint: disable=too-many-instance-attributes
class TriblerVersion:
    version_str: str
    version_tuple: Tuple
    major_minor: Tuple[int, int]
    last_launched_at: float
    root_state_dir: Path
    directory: Path
    prev_version_by_time: Optional[TriblerVersion]
    prev_version_by_number: Optional[TriblerVersion]
    can_be_copied_from: Optional[TriblerVersion]
    should_be_copied: bool
    should_recreate_directory: bool
    deleted: bool

    def __init__(self, root_state_dir: Path, version_str: str, last_launched_at: Optional[float] = None):
        if last_launched_at is None:
            last_launched_at = time.time()
        self.version_str = version_str
        self.version_tuple = tuple(LooseVersion(version_str).version)
        self.major_minor = self.version_tuple[:2]
        self.last_launched_at = last_launched_at
        self.root_state_dir = root_state_dir
        self.directory = self.get_directory()
        self.prev_version_by_time = None
        self.prev_version_by_number = None
        self.can_be_copied_from = None
        self.should_be_copied = False
        self.should_recreate_directory = False
        self.deleted = False

    def __repr__(self):
        return f'<{self.__class__.__name__}{{{self.version_str}}}>'

    def get_directory(self):
        if self.major_minor < (7, 4):
            # This should only happen for old "7.0.0-GIT" case
            return self.root_state_dir
        if self.major_minor == (7, 4):
            # 7.4.x are treated specially
            return self.root_state_dir / (".".join(str(part) for part in LooseVersion(self.version_str).version[:3]))
        return self.root_state_dir / ('%d.%d' % self.major_minor)

    def state_exists(self):
        # For ancient versions that use root directory for state storage
        # we additionally check the existence of the `triblerd.conf` file
        if self.directory == self.root_state_dir:
            return (self.root_state_dir / "triblerd.conf").exists()
        return self.directory.exists()

    def calc_state_size(self):
        # Should work even for pre-7.4 versions, counting only files and folder related to that version
        result = 0
        for filename in STATE_FILES_TO_COPY:
            path = self.directory / filename
            if path.exists():
                result += path.stat().st_size
        for dirname in STATE_DIRS_TO_COPY:
            path = self.directory / dirname
            for f in path.glob('**/*'):
                result += f.stat().st_size
        return result

    def delete_state(self) -> Optional[Path]:
        # Try to delete the directory for the version.
        # If directory contains unknown files or folders, then rename the directory instead.
        # Return renamed path or None if the directory was deleted successfully.

        if self.deleted:
            return None

        self.deleted = True
        for filename in STATE_FILES_TO_COPY:
            try:
                (self.directory / filename).unlink()
            except FileNotFoundError:
                pass
        for dirname in STATE_DIRS_TO_COPY:
            shutil.rmtree(str(self.directory / dirname), ignore_errors=True)
        if self.directory != self.root_state_dir:
            try:
                # do not delete directory with unknown leftover files
                self.directory.rmdir()
            except OSError:
                # cannot delete, then rename
                renamed = self.rename_directory("deleted_v")
                return renamed
        return None

    def copy_state_from(self, other: TriblerVersion, overwrite=False):
        if self.directory.exists():
            if not overwrite:
                raise VersionError(f'Directory for version {self.version_str} already exists')
            self.delete_state()

        self.directory.mkdir()
        for dirname in STATE_DIRS_TO_COPY:
            src = other.directory / dirname
            if src.exists():
                dst = self.directory / dirname
                shutil.copytree(src, dst)

        for filename in STATE_FILES_TO_COPY:
            src = other.directory / filename
            if src.exists():
                dst = self.directory / filename
                shutil.copy(src, dst)

    def rename_directory(self, prefix='unused_v'):
        if self.directory == self.root_state_dir:
            raise VersionError('Cannot rename root directory')
        timestamp_str = datetime.now().strftime("%Y-%m-%d_%Hh%Mm%Ss")
        dirname = prefix + '%d.%d' % self.major_minor + '_' + timestamp_str
        return self.directory.rename(self.root_state_dir / dirname)


class VersionHistory:
    """
    This class represents Tribler version usage history. The history is saved/loaded to/from the version_history.json
    file typically stored at the top-level root state directory.
    """

    root_state_dir: Path
    file_path: Path
    file_data: Dict
    versions: OrderedDict[Tuple[int, int], TriblerVersion]  # pylint: disable=unsubscriptable-object
    versions_by_number: List[TriblerVersion]
    versions_by_time: List[TriblerVersion]
    last_run_version: Optional[TriblerVersion]
    code_version: TriblerVersion

    # pylint: disable=too-many-branches
    def __init__(self, root_state_dir: Path, code_version_id: Optional[str] = None):
        if code_version_id is None:
            code_version_id = tribler_core.version.version_id

        self.root_state_dir = root_state_dir
        self.file_path = root_state_dir / VERSION_HISTORY_FILENAME
        self.file_data = {"last_version": None, "history": {}}
        self.versions = versions = OrderedDict()
        if self.file_path.exists():
            self.load(self.file_path)
        elif (root_state_dir / "triblerd.conf").exists():
            # Pre-7.4 versions of Tribler don't have history file
            # and can by detected by presence of the triblerd.conf file in the root directory
            version = TriblerVersion(root_state_dir, "7.3", 0.0)
            self.add_version(version)

        versions_by_time = []
        last_run_version = None
        if versions:
            versions_by_time = list(reversed(versions.values()))
            last_run_version = versions_by_time[0]
            for i in range(len(versions_by_time) - 1):
                versions_by_time[i].prev_version_by_time = versions_by_time[i + 1]

        code_version = TriblerVersion(root_state_dir, code_version_id)

        if not last_run_version:
            # No previous versions found
            pass
        elif last_run_version.version_str == code_version.version_str:
            # Previously we started the same version, nothing to upgrade
            code_version = last_run_version
        elif last_run_version.major_minor == code_version.major_minor:
            # Previously we started version from the same directory and can continue use this directory
            pass
        else:
            # Previously we started version from the different directory
            for v in versions_by_time:
                if v.major_minor < code_version.major_minor:
                    code_version.can_be_copied_from = v
                    break

            if code_version.can_be_copied_from:
                if not code_version.directory.exists():
                    code_version.should_be_copied = True

                elif code_version.major_minor in versions:
                    # We already used version with this major.minor number, but not the last time.
                    # We need to upgrade from the latest version if possible (see description at the top of the file).
                    # Probably we should ask user, should we copy data again from the previous version or not
                    code_version.should_be_copied = True
                    code_version.should_recreate_directory = True

        self.versions_by_number = sorted(versions.values(), key=attrgetter('major_minor'))
        self.versions_by_time = versions_by_time
        self.last_run_version = last_run_version
        self.code_version = code_version

    def __repr__(self):
        s = repr([v.major_minor for v in self.versions_by_time])
        return f'<{self.__class__.__name__}{s}>'

    def load(self, file_path: Path):
        self.file_data = json.loads(file_path.read_text().strip())
        if "history" not in self.file_data:
            raise VersionError("Invalid history file structure")

        # timestamps needs to be converted to float before sorting
        history_items = [(float(time_str), version_str) for time_str, version_str in self.file_data["history"].items()]
        for timestamp, version_str in sorted(history_items):
            version = TriblerVersion(self.root_state_dir, version_str, timestamp)
            # store only versions with directories:
            if version.state_exists():
                # eventually store only the latest launched version with the same major_minor tuple
                self.add_version(version)

    def add_version(self, version):
        self.versions[version.major_minor] = version
        self.versions.move_to_end(version.major_minor)

    def save_if_necessary(self) -> bool:
        """Returns True if state was saved"""
        should_save = self.code_version != self.last_run_version
        if should_save:
            self.save()
        return should_save

    def save(self):
        self.file_data["last_version"] = self.code_version.version_str
        self.file_data["history"][str(self.code_version.last_launched_at)] = self.code_version.version_str
        self.file_path.write_text(json.dumps(self.file_data))

    def fork_state_directory_if_necessary(self) -> Optional[TriblerVersion]:
        """Returns version string from which the state directory was forked"""
        code_version = self.code_version
        if code_version.should_recreate_directory:
            code_version.rename_directory()

        if code_version.should_be_copied:
            prev_version = code_version.can_be_copied_from
            if prev_version:  # should always be True here
                code_version.copy_state_from(prev_version)
                return prev_version
        return None

    def get_installed_versions(self, with_code_version=True) -> List[TriblerVersion]:
        installed_versions = [
            v for v in self.versions_by_number if not v.deleted and v.major_minor != self.code_version.major_minor
        ]
        if with_code_version:
            installed_versions.insert(0, self.code_version)
        return installed_versions

    def get_disposable_versions(self, skip_versions: int = 0) -> List[TriblerVersion]:
        # versions are sorted in the order of usage, we want to keep the current version and two previous versions
        disposable_versions = [
            v for v in self.versions_by_time if not v.deleted and v.major_minor != self.code_version.major_minor
        ]
        return disposable_versions[skip_versions:]

    def get_disposable_state_directories(
        self, skip_versions: int = 0, include_unused=True, include_deleted=True, include_old_dirs=True
    ) -> List[Path]:
        result = []
        for v in self.get_disposable_versions(skip_versions):
            if v.directory != self.root_state_dir and v.directory.exists():
                result.append(v.directory)

        if include_unused:
            result.extend(self.root_state_dir.glob('unused_v*'))

        if include_deleted:
            result.extend(self.root_state_dir.glob('deleted_v*'))

        if include_old_dirs:
            for dir_name in STATE_DIRS_TO_COPY:
                dir_path = self.root_state_dir / dir_name
                if dir_path.exists():
                    result.append(dir_path)

        result.sort()
        return result


def remove_state_dirs(root_state_dir: str, state_dirs: List[str]):
    for state_dir in state_dirs:
        state_dir = os.path.join(root_state_dir, state_dir)
        shutil.rmtree(state_dir, ignore_errors=True)

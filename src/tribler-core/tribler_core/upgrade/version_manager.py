import os
import shutil
import time
from datetime import datetime
from distutils.version import LooseVersion
from pathlib import Path

from tribler_common.simpledefs import (
    STATEDIR_CHANNELS_DIR,
    STATEDIR_CHECKPOINT_DIR,
    STATEDIR_DB_DIR,
)

from tribler_core.utilities import json_util as json
from tribler_core.utilities.osutils import dir_copy
from tribler_core.version import version_id as code_version_id

VERSION_HISTORY_FILE = "version_history.json"

# Copy other important files: keys and config
STATE_FILES_TO_COPY = ('ec_multichain.pem',
                       'ecpub_multichain.pem',
                       'ec_trustchain_testnet.pem',
                       'ecpub_trustchain_testnet.pem',
                       'triblerd.conf')

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
  has a lower patch version (x.y.<Z>),  we rename the existing dir to DIRNAME_bak_<timestamp>.
  This corresponds to a situation where the user tried some version of Tribler and then went back to the previous
  version, but now tries again the same series with a higher patch version. This is a most typical scenario
  in which the version management system comes into play.
  Example:
   the user installed 7.5.0 and used it for some time, then tried to upgraded to 7.6.0 and failed. Then the user
   went back to 7.5.0. After 7.6.1 was released, the user tried upgrading again. When run, 7.6.1 looked at the
   version_history.json and detected that the last used version was 7.5.0. It tried to create the 7.6 directory
   but failed because 7.6 was already installed before. Then, version management procedure renamed the old 7.6
   directory to 7.6_bak_<timestamp> and created 7.6 directory anew, and copied 7.5 contents into it.

In some sense, the system works exactly as GIT does: it "branches" from the last-non conflicting version dir
and "stashes" the state dirs with conflicting names by renaming them.

Note that due to failures in design pre-7.4 series and 7.4.x series get special treatment.
"""


class VersionHistory:
    """
    This class represents Tribler version usage history. The history is saved/loaded to/from the version_history.json
    file typically stored at the top-level root state directory.
    """

    def __init__(self, file_path):
        """
        :param file_path: path to version_history.json file. Will be loaded if exists, or created anew if does not.
        """
        self.file_path = file_path
        self.version_history = json.loads(file_path.read_text().strip()) if file_path.exists() else {
            "last_version": None, "history": {}}

    @property
    def last_version(self):
        return self.version_history["last_version"]

    def update(self, version_id):
        if str(self.last_version) == str(version_id):
            return
        self.version_history["last_version"] = version_id
        self.version_history["history"][str(time.time())] = version_id
        self.file_path.write_text(json.dumps(self.version_history))

    def get_last_upgradable_version(self, root_state_dir, code_version):
        """
        This function gets the list of previously used Tribler versions from the usage history file
        and returns the most recently used version that has lower number than the code version.
        :param root_state_dir: root state directory, where the version history file and old version dirs
        :param code_version: current code version
        :return: None if no upgradable version found, version number otherwise
        """

        for version in [version for _, version in sorted(self.version_history["history"].items(), reverse=True)]:
            if (LooseVersion(code_version) > LooseVersion(version)
                    and get_versioned_state_directory(root_state_dir, version).exists()):
                return version
        return None


def version_to_dirname(version_id):
    # 7.4.x are treated specially
    if LooseVersion(version_id).version[:2] == LooseVersion("7.4").version:
        return ".".join(str(part) for part in LooseVersion(version_id).version[:3])
    if LooseVersion(version_id) < LooseVersion("7.4"):
        # This should only happen for old "7.0.0-GIT" case
        return None
    return ".".join(str(part) for part in LooseVersion(version_id).version[:2])


def get_versioned_state_directory(root_state_dir, version_id=code_version_id):
    """
    Returns versioned state directory for a given version
    """
    versioned_state_dir = version_to_dirname(version_id)
    if versioned_state_dir is None:
        # "7.0.0-GIT" case
        return Path(root_state_dir)
    return Path(root_state_dir) / versioned_state_dir


def copy_state_directory(src_dir, tgt_dir):
    """
    Creates a new state directory for the given version based on the given base state directory and
    copies important files and directories to the new state directory.
    """

    # Copy directories from the current state directory to the new one.
    src_sub_dirs = os.listdir(src_dir)
    for dirname in STATE_DIRS_TO_COPY:
        if dirname in src_sub_dirs:
            dir_copy(src_dir / dirname, tgt_dir / dirname, merge_if_exists=True)
    for filename in STATE_FILES_TO_COPY:
        if os.path.exists(src_dir / filename):
            shutil.copy(src_dir / filename, tgt_dir / filename)


def fork_state_directory_if_necessary(root_state_dir, code_version):
    version_history = VersionHistory(root_state_dir / VERSION_HISTORY_FILE)
    # The previous version has the same major/minor number as the code version, and there exists
    # a corresponding versioned state directory. Nothing to do here (except possibly updating version history).
    code_version_dir = get_versioned_state_directory(root_state_dir, code_version)
    if (version_history.last_version is not None
            and LooseVersion(version_history.last_version).version[:2] == LooseVersion(code_version).version[:2]
            and code_version_dir.exists()):
        if str(version_history.last_version) != str(code_version):
            version_history.update(code_version)
        return

    src_dir = None
    tgt_dir = code_version_dir
    # Normally, last_version cannot be None in the version_history file.
    # It can only be None if there was no prior _versioned_ Tribler install.
    if version_history.last_version is not None:
        last_upgradable_version = version_history.get_last_upgradable_version(root_state_dir, code_version)
        if last_upgradable_version is not None:
            src_dir = get_versioned_state_directory(root_state_dir, last_upgradable_version)
    elif (root_state_dir / "triblerd.conf").exists():
        # Legacy version
        src_dir = root_state_dir

    if src_dir is not None:
        # Borderline case where user got an unused code version directory: rename it out of the way
        if tgt_dir.exists():
            moved_out_of_way_dirname = "unused_v" + str(tgt_dir.name) + "_" + datetime.now().strftime(
                "%Y-%m-%d_%Hh%Mm%Ss")
            tgt_dir.rename(tgt_dir.with_name(moved_out_of_way_dirname))
        copy_state_directory(src_dir, tgt_dir)

    version_history.update(code_version)

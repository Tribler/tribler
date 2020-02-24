import logging
import os
import shutil
import time
from distutils.version import LooseVersion
from pathlib import Path

from tribler_common.simpledefs import (
    STATEDIR_CHANNELS_DIR,
    STATEDIR_CHECKPOINT_DIR,
    STATEDIR_DB_DIR,
    STATEDIR_WALLET_DIR,
)

from tribler_core import version as tribler_version
from tribler_core.utilities import json_util as json
from tribler_core.utilities.osutils import dir_copy

VERSION_HISTORY_FILE = "version_history.json"


class VersionManager:

    def __init__(self, session):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session

        self.version_history = {"last_version": None, "history": {}}
        self.version_history_path = Path(self.session.config.get_root_state_dir(), VERSION_HISTORY_FILE)
        self.read_version_history()

    def read_version_history(self):
        if self.version_history_path.exists():
            self.version_history = json.loads(self.version_history_path.read_text().strip())

    def update_version_history(self, version_id):
        self.version_history["last_version"] = version_id
        self.version_history["history"][time.time()] = version_id
        self.version_history_path.write_text(json.dumps(self.version_history))

    def fork_state_directory(self, version_id, base_state_directory):
        """
        Creates a new state directory for the given version based on the given base state directory. It basically
        copies important files and directories to the new state directory. If the new state directory already
        exists and tribler config file is present, it does not overwrite anything on the directory.
        """
        new_state_dir = Path(self.session.config.get_state_dir(version_id=version_id))

        # If only there is no tribler config already in the new state directory,
        # then we assume that this is a new version so we copy the last state directory and upgrade it.
        conf_path = new_state_dir / 'triblerd.conf'
        if base_state_directory.exists() and not conf_path.exists():
            # Copy the selected directories from the current state directory to the new one.
            upgrade_dirs = [STATEDIR_DB_DIR, STATEDIR_CHECKPOINT_DIR, STATEDIR_WALLET_DIR, STATEDIR_CHANNELS_DIR]
            src_sub_dirs = os.listdir(base_state_directory)
            for upgrade_dir in upgrade_dirs:
                if upgrade_dir in src_sub_dirs:
                    dir_copy(base_state_directory / upgrade_dir, new_state_dir / upgrade_dir, merge_if_exists=True)

            # Copy other important files: keys and config
            extra_files = ['ec_multichain.pem', 'ecpub_multichain.pem', 'ec_trustchain_testnet.pem',
                           'ecpub_trustchain_testnet.pem', 'triblerd.conf']
            for extra_file in extra_files:
                if os.path.exists(base_state_directory / extra_file):
                    shutil.copy(base_state_directory / extra_file, new_state_dir / extra_file)

    def setup_state_directory_for_upgrade(self, version_id=None):
        """
        Runs the version migration  of the state directory if there was an update in the code version.
        """
        if not self.session.config.get_version_backup_enabled():
            return

        code_version = version_id or tribler_version.version_id
        # To check if Tribler directory for the running version already exists, we must check for its *contents*
        # because the directory itself is already created earlier
        # FIXME: reposition upgrader so it will start *before* creating the state directory
        code_version_directory_exists = (self.get_state_directory(code_version) / 'triblerd.conf').exists()

        last_usage_version = self.version_history.get("last_version", None)
        last_usage_version_directory_exists = self.get_state_directory(last_usage_version).exists()

        upgrade_possible = False
        # Pre-requisites for upgrading:
        # the old directory should exist and the newer version should be higher then the old one
        if last_usage_version_directory_exists and not code_version_directory_exists:
            if last_usage_version is not None:
                # Normal upgrade, e.g. 7.4.1->7.4.2
                upgrade_possible = LooseVersion(last_usage_version) < LooseVersion(code_version)
            else:
                # Legacy upgrade
                upgrade_possible = True

        # If upgrade is possible, fork the state directory for the new code version
        if upgrade_possible:
            self.fork_state_directory(code_version, self.get_state_directory(last_usage_version))

        # Update the history file
        if last_usage_version != code_version:
            self.update_version_history(code_version)

        return upgrade_possible

    def get_state_directory(self, version_id):
        """
        Returns versioned state directory for a given version else returns .Tribler directory.
        """
        return Path(self.session.config.get_state_dir(version_id=version_id)
                    if version_id else self.session.config.get_root_state_dir())

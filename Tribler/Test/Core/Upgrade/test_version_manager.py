from __future__ import absolute_import

import os

from configobj import ConfigObj

from twisted.internet.defer import inlineCallbacks

from Tribler.Core import version as tribler_version
from Tribler.Core.Config.tribler_config import CONFIG_SPEC_PATH, TriblerConfig
from Tribler.Core.Session import Session
from Tribler.Core.Upgrade.upgrade import TriblerUpgrader
from Tribler.Core.Upgrade.version_manager import VersionManager
from Tribler.Core.simpledefs import STATEDIR_CHANNELS_DIR, STATEDIR_CHECKPOINT_DIR, \
    STATEDIR_DB_DIR, STATEDIR_WALLET_DIR
from Tribler.Test.test_as_server import AbstractServer


class TestVersionManager(AbstractServer):

    @inlineCallbacks
    def setUp(self):
        yield super(TestVersionManager, self).setUp()
        self.config = TriblerConfig(ConfigObj(configspec=CONFIG_SPEC_PATH))
        self.config.set_root_state_dir(self.getRootStateDir())
        self.session = Session(self.config)

        self.upgrader = TriblerUpgrader(self.session)
        self.version_manager = VersionManager(self.session)

    def test_read_write_version(self):
        # If there is no version history file, no information about last version is available
        self.assertFalse(os.path.exists(self.version_manager.version_history_path))
        self.assertIsNone(self.version_manager.version_history['last_version'])
        self.assertEqual(self.version_manager.version_history['history'], {})

        # Saving the version
        new_version = '100.100.100'
        self.version_manager.update_version_history(new_version)
        self.assertEqual(self.version_manager.version_history['last_version'], new_version)
        self.assertEqual(len(self.version_manager.version_history['history']), 1)

        # Check that loading of version history from file works
        self.version_manager.version_history = None
        self.version_manager.read_version_history()
        self.assertEqual(self.version_manager.version_history['last_version'], new_version)
        self.assertEqual(len(self.version_manager.version_history['history']), 1)

    def test_setup_state_directory_for_upgrade(self):
        # By default version, it is referred to as the installed version for the user.
        # For test, the default version is set in the code, which is '7.0.0-GIT'.
        default_version_id = tribler_version.version_id
        self.assertEqual(default_version_id, '7.0.0-GIT')

        # With the latest implementation of the version manager, a separate state directory is created for each code
        # version including the default version.
        root_state_dir = self.session.config.get_root_state_dir()
        self.version_manager.setup_state_directory_for_upgrade(version_id=default_version_id)
        self.session.init_keypair()
        self.session.trustchain_keypair = None
        self.assertTrue(default_version_id, os.listdir(root_state_dir))

        # Also check that there are all important directories and files in the created state directory
        default_version_state_dir = self.version_manager.get_state_directory(default_version_id)
        self.assertTrue(os.path.exists(default_version_state_dir))
        self.assertTrue(len(list(default_version_state_dir.glob("*.pem"))) > 1)
        default_version_state_sub_dirs = os.listdir(default_version_state_dir)
        backup_dirs = [STATEDIR_DB_DIR, STATEDIR_CHECKPOINT_DIR, STATEDIR_WALLET_DIR, STATEDIR_CHANNELS_DIR]
        for backup_dir in backup_dirs:
            self.assertTrue(backup_dir in default_version_state_sub_dirs)

        # Assuming, new upgrade to be done
        current_version = '100.100.100'

        # First, check if the version backup is not enabled, no migration is done
        self.session.config.set_version_backup_enabled(False)
        self.version_manager.setup_state_directory_for_upgrade(version_id=current_version)

        version_state_dir = self.version_manager.get_state_directory(current_version)
        self.assertFalse(os.path.exists(version_state_dir))

        # Next, enabling the version backup, now proper migration should happen
        self.session.config.set_version_backup_enabled(True)
        self.version_manager.setup_state_directory_for_upgrade(version_id=current_version)

        # All directories and files should be copied to the state directory of the new version
        version_state_dir = self.version_manager.get_state_directory(current_version)
        self.assertTrue(os.path.exists(version_state_dir))

        version_state_sub_dirs = os.listdir(version_state_dir)
        backup_dirs = [STATEDIR_DB_DIR, STATEDIR_CHECKPOINT_DIR, STATEDIR_WALLET_DIR, STATEDIR_CHANNELS_DIR]
        for backup_dir in backup_dirs:
            self.assertTrue(backup_dir in version_state_sub_dirs)

        self.assertTrue(len(list(version_state_dir.glob("*.pem"))) > 1)

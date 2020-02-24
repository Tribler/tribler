from __future__ import absolute_import

import os
import shutil

from tribler_common.simpledefs import STATEDIR_CHECKPOINT_DIR

from tribler_core.tests.tools.base_test import TriblerCoreTest
from tribler_core.tests.tools.common import TESTS_DATA_DIR
from tribler_core.upgrade.config_converter import convert_state_file_to_conf_74


class TestConfigUpgradeto74(TriblerCoreTest):
    """
    Contains tests that test the config conversion from pre 7.4.0 config with .pstate file to compatible 7.4.0 type
    .conf files.
    """
    CONFIG_PATH = TESTS_DATA_DIR / "config_files"

    def test_convert_state_file_to_conf_74(self):
        """
        Tests conversion of the pstate files (pre-7.4.0) files to .conf files. Tests for two different pstate files,
        one corrupted with incorrect metainfo data, and the other one with correct working metadata.
        """
        from lib2to3.refactor import RefactoringTool, get_fixers_from_package
        refactoring_tool = RefactoringTool(fixer_names=get_fixers_from_package('lib2to3.fixes'))

        os.makedirs(os.path.join(self.state_dir, STATEDIR_CHECKPOINT_DIR))

        # Copy a good working Ubuntu pstate file
        src_path = os.path.join(self.CONFIG_PATH, "194257a7bf4eaea978f4b5b7fbd3b4efcdd99e43.state")
        dest_path = os.path.join(self.state_dir, STATEDIR_CHECKPOINT_DIR, "ubuntu_ok.state")

        shutil.copyfile(src_path, dest_path)
        convert_state_file_to_conf_74(dest_path, refactoring_tool)

        converted_file_path = os.path.join(self.state_dir, STATEDIR_CHECKPOINT_DIR, "ubuntu_ok.conf")
        self.assertTrue(os.path.exists(converted_file_path))
        self.assertFalse(os.path.exists(dest_path))

        os.remove(converted_file_path)

        # Copy Ubuntu pstate file with corrupted metainfo data
        src_path = os.path.join(self.CONFIG_PATH, "194257a7bf4eaea978f4b5b7fbd3b4efcdd99e43_corrupted.state")
        dest_path = os.path.join(self.state_dir, STATEDIR_CHECKPOINT_DIR, "ubuntu_corrupted.state")

        shutil.copyfile(src_path, dest_path)
        convert_state_file_to_conf_74(dest_path, refactoring_tool)

        converted_file_path = os.path.join(self.state_dir, STATEDIR_CHECKPOINT_DIR, "ubuntu_corrupted.conf")
        self.assertFalse(os.path.exists(converted_file_path))
        self.assertFalse(os.path.exists(dest_path))

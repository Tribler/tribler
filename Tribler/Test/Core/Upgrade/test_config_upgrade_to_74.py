from __future__ import absolute_import

import os
import shutil

from six import PY3

from Tribler.Core.Upgrade.config_converter import convert_state_file_to_conf_74
from Tribler.Core.simpledefs import STATEDIR_CHECKPOINT_DIR
from Tribler.Test.Core.base_test import TriblerCoreTest


class TestConfigUpgradeto74(TriblerCoreTest):
    """
    Contains tests that test the config conversion from pre 7.4.0 config with .pstate file to compatible 7.4.0 type
    .conf files.
    """
    from Tribler.Test import Core
    CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(Core.__file__)), "data/config_files/")

    def test_convert_state_file_to_conf_74(self):
        """
        Tests conversion of the pstate files (pre-7.4.0) files to .conf files. Tests for two different pstate files,
        one corrupted with incorrect metainfo data, and the other one with correct working metadata.
        """
        refactoring_tool = None
        if PY3:
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

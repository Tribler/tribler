import os
import shutil
from pathlib import Path

from configobj import ParseError as ConfigObjParseError

import pytest

from tribler_common.simpledefs import STATEDIR_CHECKPOINT_DIR

from tribler_core.tests.tools.common import TESTS_DATA_DIR
from tribler_core.upgrade import config_converter
from tribler_core.upgrade.config_converter import convert_state_file_to_conf_74


CONFIG_PATH = TESTS_DATA_DIR / "config_files"


def test_convert_state_file_to_conf_74(tmpdir):
    """
    Tests conversion of the pstate files (pre-7.4.0) files to .conf files. Tests for two different pstate files,
    one corrupted with incorrect metainfo data, and the other one with correct working metadata.
    """
    from lib2to3.refactor import RefactoringTool, get_fixers_from_package
    refactoring_tool = RefactoringTool(fixer_names=get_fixers_from_package('lib2to3.fixes'))

    os.makedirs(Path(tmpdir) / STATEDIR_CHECKPOINT_DIR)

    # Copy a good working Ubuntu pstate file
    src_path = Path(CONFIG_PATH, "194257a7bf4eaea978f4b5b7fbd3b4efcdd99e43.state")
    dest_path = Path(tmpdir) / STATEDIR_CHECKPOINT_DIR / "ubuntu_ok.state"

    shutil.copyfile(src_path, dest_path)
    convert_state_file_to_conf_74(dest_path, refactoring_tool)

    converted_file_path = Path(tmpdir) / STATEDIR_CHECKPOINT_DIR / "ubuntu_ok.conf"
    assert os.path.exists(converted_file_path)
    assert not os.path.exists(dest_path)

    os.remove(converted_file_path)

    # Copy Ubuntu pstate file with corrupted metainfo data
    src_path = CONFIG_PATH / "194257a7bf4eaea978f4b5b7fbd3b4efcdd99e43_corrupted.state"
    dest_path = Path(tmpdir) / STATEDIR_CHECKPOINT_DIR / "ubuntu_corrupted.state"

    shutil.copyfile(src_path, dest_path)
    convert_state_file_to_conf_74(dest_path, refactoring_tool)

    converted_file_path = Path(tmpdir) / STATEDIR_CHECKPOINT_DIR / "ubuntu_corrupted.conf"
    assert not os.path.exists(converted_file_path)
    assert not os.path.exists(dest_path)


@pytest.fixture(name='faulty_config_parser')
async def fixture_faulty_config_parser():
    def load_config_with_parse_error(filename):
        raise ConfigObjParseError(f"Error parsing config file {filename}")

    original_load_config = config_converter.load_config
    config_converter.load_config = load_config_with_parse_error
    yield config_converter
    config_converter.load_config = original_load_config


def test_convert_state_file_to_conf74_with_parse_error(tmpdir, faulty_config_parser):
    """
    Tests conversion of the state files (pre-7.4.0) files to .conf files (7.4) when there is parsing error.
    ParseError happens for some users for some unknown reason. We simply remove the files that we cannot
    parse. This test tests that such a corrupted file is actual deleted.
    """
    from lib2to3.refactor import RefactoringTool, get_fixers_from_package
    refactoring_tool = RefactoringTool(fixer_names=get_fixers_from_package('lib2to3.fixes'))

    state_dir = Path(tmpdir)
    os.makedirs(state_dir / STATEDIR_CHECKPOINT_DIR)

    # Copy Ubuntu pstate file with corrupted metainfo data
    src_path = CONFIG_PATH / "194257a7bf4eaea978f4b5b7fbd3b4efcdd99e43.state"
    dest_path = state_dir / STATEDIR_CHECKPOINT_DIR / "ubuntu_corrupted.state"
    shutil.copyfile(src_path, dest_path)

    # Try converting the state file to 7.4 conf format
    convert_state_file_to_conf_74(dest_path, refactoring_tool)

    # Path where the file should be saved after conversion
    converted_file_path = state_dir / STATEDIR_CHECKPOINT_DIR / "ubuntu_corrupted.conf"

    # We expect ParseError and the file to be deleted.
    assert not os.path.exists(converted_file_path)
    assert not os.path.exists(dest_path)


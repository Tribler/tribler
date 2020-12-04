import os
import shutil
from pathlib import Path

from configobj import ParseError as ConfigObjParseError

import pytest

from tribler_common.simpledefs import STATEDIR_CHECKPOINT_DIR

from tribler_core.modules.libtorrent.download_config import DownloadConfig
from tribler_core.tests.tools.common import TESTS_DATA_DIR
from tribler_core.upgrade.config_converter import convert_config_to_tribler75

CONFIG_PATH = TESTS_DATA_DIR / "config_files"


@pytest.fixture(name='faulty_download_config_parser')
async def fixture_faulty_download_config_parser():
    def load_config_with_parse_error(filename):
        raise ConfigObjParseError(f"Error parsing config file {filename}")

    original_load_config = DownloadConfig.load
    DownloadConfig.load = load_config_with_parse_error
    yield DownloadConfig
    DownloadConfig.load = original_load_config


def test_convert_state_file_to_conf75_with_parse_error(tmpdir, faulty_download_config_parser):
    """
    Tests conversion of the conf files (7.4.0) files to .conf files (7.5) when there is parsing error.
    ParseError happens for some users for some unknown reason. We simply remove the files that we cannot
    parse. This test tests that such a corrupted file is actual deleted.
    """
    state_dir = Path(tmpdir)
    os.makedirs(state_dir / STATEDIR_CHECKPOINT_DIR)

    # Copy Ubuntu conf file with corrupted metainfo data
    src_path = CONFIG_PATH / "13a25451c761b1482d3e85432f07c4be05ca8a56.conf"
    dest_path = state_dir / STATEDIR_CHECKPOINT_DIR / "ubuntu_corrupted.conf"
    shutil.copyfile(src_path, dest_path)

    # Try converting the conf file to 7.5 conf format
    convert_config_to_tribler75(Path(tmpdir))

    # Path where the file should be saved after conversion
    converted_file_path = state_dir / STATEDIR_CHECKPOINT_DIR / "ubuntu_corrupted.conf"

    # We expect ParseError and the file to be deleted.
    assert not os.path.exists(converted_file_path)
    assert not os.path.exists(dest_path)

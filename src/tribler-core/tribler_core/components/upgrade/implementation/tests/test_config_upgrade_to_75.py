import os
import shutil
from pathlib import Path

from tribler_common.simpledefs import STATEDIR_CHECKPOINT_DIR
from tribler_core.components.upgrade.implementation.config_converter import convert_config_to_tribler75

from tribler_core.tests.tools.common import TESTS_DATA_DIR

CONFIG_PATH = TESTS_DATA_DIR / "config_files"


def test_convert_state_file_to_conf75_with_parse_error(tmpdir):
    """
    Tests conversion of the conf files (7.4.0) files to .conf files (7.5) when there is parsing error.
    ParseError happens for some users for some unknown reason. We simply remove the files that we cannot
    parse. This test tests that such a corrupted file is actual deleted.
    """
    state_dir = Path(tmpdir)
    os.makedirs(state_dir / STATEDIR_CHECKPOINT_DIR)

    # Copy Ubuntu conf file with corrupted metainfo data
    src_path = CONFIG_PATH / "corrupt_download_config.conf"
    dest_path = state_dir / STATEDIR_CHECKPOINT_DIR / "ubuntu_corrupted.conf"
    shutil.copyfile(src_path, dest_path)

    # Try converting the conf file to 7.5 conf format
    convert_config_to_tribler75(Path(tmpdir))

    # Path where the file should be saved after conversion
    converted_file_path = state_dir / STATEDIR_CHECKPOINT_DIR / "ubuntu_corrupted.conf"

    # We expect ParseError and the file to be deleted.
    assert not os.path.exists(converted_file_path)
    assert not os.path.exists(dest_path)

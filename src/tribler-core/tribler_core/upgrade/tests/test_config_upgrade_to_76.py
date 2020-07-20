import shutil

from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.tests.tools.common import TESTS_DATA_DIR
from tribler_core.upgrade.config_converter import convert_config_to_tribler76


CONFIG_PATH = TESTS_DATA_DIR / "config_files"


def test_convert_tribler_conf_76(tmpdir):
    """
    Tests conversion of the Tribler 7.5 config
    """
    shutil.copy2(CONFIG_PATH / 'triblerd75.conf', tmpdir / 'triblerd.conf')
    convert_config_to_tribler76(tmpdir)
    new_config = TriblerConfig(tmpdir, tmpdir / 'triblerd.conf')
    assert new_config.get_api_key() == '7671750ba34423c97dc3c6763041e4cb'
    assert new_config.get_api_http_port() == 8085
    assert new_config.get_api_http_enabled()
    assert not new_config.get_api_https_enabled()

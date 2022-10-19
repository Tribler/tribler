import shutil

from tribler.core.config.tribler_config import TriblerConfig
from tribler.core.tests.tools.common import TESTS_DATA_DIR
from tribler.core.upgrade.config_converter import convert_config_to_tribler76

CONFIG_PATH = TESTS_DATA_DIR / "config_files"


def test_convert_tribler_conf_76(tmpdir):
    """
    Tests conversion of the Tribler 7.5 config
    """
    shutil.copy2(CONFIG_PATH / 'triblerd75.conf', tmpdir / 'triblerd.conf')
    convert_config_to_tribler76(tmpdir)

    config = TriblerConfig.load(state_dir=tmpdir)
    assert config.api.key == '7671750ba34423c97dc3c6763041e4cb'
    assert config.api.http_port == 8085
    assert config.api.http_enabled
    assert not config.api.https_enabled

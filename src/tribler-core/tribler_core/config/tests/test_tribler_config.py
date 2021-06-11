import shutil
from pathlib import Path

from configobj import ParseError

import pytest

from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.libtorrent.download_manager import DownloadManager
from tribler_core.tests.tools.common import TESTS_DATA_DIR

# fmt: off

CONFIG_PATH = TESTS_DATA_DIR / "config_files"


@pytest.mark.asyncio
async def test_copy(tribler_config):
    tribler_config.put('api', 'http_port', 42)

    cloned = tribler_config.copy()
    assert cloned.get('api', 'http_port') == 42


@pytest.mark.asyncio
async def test_put_path_relative(tmpdir):
    config = TriblerConfig(state_dir=tmpdir)

    # put correct path
    config.put_path(section_name='general', property_name='log_dir', value=Path(tmpdir))
    assert config.config['general']['log_dir'] == '.'

    config.put_path(section_name='general', property_name='log_dir', value=Path(tmpdir) / '1')
    assert config.config['general']['log_dir'] == '1'


@pytest.mark.asyncio
async def test_put_path_absolute(tmpdir):
    config = TriblerConfig(state_dir=tmpdir)

    config.put_path(section_name='general', property_name='log_dir', value=None)
    assert not config.config['general']['log_dir']

    config.put_path(section_name='general', property_name='log_dir', value=Path(tmpdir).parent)
    assert config.config['general']['log_dir'] == str(Path(tmpdir).parent)

    config.put_path(section_name='general', property_name='log_dir', value=Path('/Tribler'))
    assert config.config['general']['log_dir'] == str(Path('/Tribler'))


@pytest.mark.asyncio
async def test_get_path_relative(tmpdir):
    config = TriblerConfig(state_dir=tmpdir)

    config.config['general']['log_dir'] = None
    assert not config.get_path(section_name='general', property_name='log_dir')

    config.config['general']['log_dir'] = '.'
    assert config.get_path(section_name='general', property_name='log_dir') == Path(tmpdir)

    config.config['general']['log_dir'] = '1'
    assert config.get_path(section_name='general', property_name='log_dir') == Path(tmpdir) / '1'


@pytest.mark.asyncio
async def test_get_path_absolute(tmpdir):
    config = TriblerConfig(state_dir=tmpdir)

    config.config['general']['log_dir'] = str(Path(tmpdir).parent)
    assert config.get_path(section_name='general', property_name='log_dir') == Path(tmpdir).parent


@pytest.mark.asyncio
async def test_init_without_config():
    """
    A newly created TriblerConfig is valid.
    """
    config = TriblerConfig()
    assert config.config


@pytest.mark.asyncio
async def test_invalid_config_recovers(tmpdir):
    default_config_file = tmpdir / 'triblerd.conf'
    shutil.copy2(CONFIG_PATH / 'corrupt-triblerd.conf', default_config_file)

    # By default, recover_error set to False when loading the config file so
    # if the config file is corrupted, it should raise a ParseError.
    config = TriblerConfig(tmpdir)
    with pytest.raises(ParseError):
        config.load(file=default_config_file)

    # If recover_error is set to True, the config should successfully load using
    # the default config in case of corrupted config file and the error is saved.
    config.load(file=default_config_file, reset_config_on_error=True)
    assert "configobj.ParseError: Invalid line" in config.error

    # Since the config should be saved on previous recovery, subsequent instantiation of TriblerConfig
    # should work without the reset flag.
    config.load(file=default_config_file)
    assert not config.error


@pytest.mark.asyncio
async def test_anon_proxy_settings(tribler_config):
    proxy_type, server, auth = 3, ("33.33.33.33", [2222, 2223, 4443, 58848]), 1
    DownloadManager.set_anon_proxy_settings(tribler_config, proxy_type, server, auth)

    settings = DownloadManager.get_anon_proxy_settings(tribler_config)
    assert settings == [proxy_type, server, auth]

    proxy_type = 1
    DownloadManager.set_anon_proxy_settings(tribler_config, proxy_type, server, auth)
    settings = DownloadManager.get_anon_proxy_settings(tribler_config)
    assert settings == [proxy_type, server, None]

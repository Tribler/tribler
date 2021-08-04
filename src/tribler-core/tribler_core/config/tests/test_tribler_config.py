import shutil

from configobj import ParseError

import pytest

from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.tests.tools.common import TESTS_DATA_DIR
from tribler_core.utilities.path_util import Path

CONFIG_PATH = TESTS_DATA_DIR / "config_files"


# fmt: off


@pytest.mark.asyncio
async def test_create(tmpdir):
    config = TriblerConfig(state_dir=tmpdir)
    assert config
    assert config.state_dir == Path(tmpdir)


@pytest.mark.asyncio
async def test_base_getters_and_setters(tmpdir):
    config = TriblerConfig(state_dir=tmpdir)
    assert config.state_dir == Path(tmpdir)

    config.set_state_dir('.')
    assert config.state_dir == Path('.')


@pytest.mark.asyncio
async def test_load_write(tmpdir):
    config = TriblerConfig(state_dir=tmpdir)
    filename = 'test_read_write.ini'

    config.general.log_dir = '1'
    config.general.version_checker_enabled = False
    config.libtorrent.port = None
    config.libtorrent.proxy_type = 2

    assert not config.file
    config.write(tmpdir / filename)
    assert config.file == tmpdir / filename

    config = TriblerConfig.load(file=tmpdir / filename, state_dir=tmpdir)
    assert config.general.log_dir == '1'
    assert config.general.version_checker_enabled is False
    assert config.libtorrent.port is None
    assert config.libtorrent.proxy_type == 2
    assert config.file == tmpdir / filename


@pytest.mark.asyncio
async def test_copy(tmpdir):
    config = TriblerConfig(state_dir=tmpdir, file=tmpdir / '1.txt')
    config.api.http_port = 42

    cloned = config.copy()
    assert cloned.api.http_port == 42
    assert cloned.state_dir == tmpdir
    assert cloned.file == tmpdir / '1.txt'


@pytest.mark.asyncio
async def test_get_path_relative(tmpdir):
    config = TriblerConfig(state_dir=tmpdir)
    config.general.log_dir = None
    assert not config.general.log_dir

    config.general.log_dir = '.'
    assert config.general.get_path_as_absolute('log_dir', tmpdir) == Path(tmpdir)

    config.general.log_dir = '1'
    assert config.general.get_path_as_absolute('log_dir', tmpdir) == Path(tmpdir) / '1'


@pytest.mark.asyncio
async def test_get_path_absolute(tmpdir):
    config = TriblerConfig(state_dir=tmpdir)
    config.general.log_dir = str(Path(tmpdir).parent)
    assert config.general.get_path_as_absolute(property_name='log_dir', state_dir=tmpdir) == Path(tmpdir).parent


@pytest.mark.asyncio
async def test_invalid_config_recovers(tmpdir):
    default_config_file = tmpdir / 'triblerd.conf'
    shutil.copy2(CONFIG_PATH / 'corrupt-triblerd.conf', default_config_file)

    # By default, recover_error set to False when loading the config file so
    # if the config file is corrupted, it should raise a ParseError.
    with pytest.raises(ParseError):
        TriblerConfig.load(file=default_config_file, state_dir=tmpdir)

    # If recover_error is set to True, the config should successfully load using
    # the default config in case of corrupted config file and the error is saved.
    config = TriblerConfig.load(file=default_config_file, state_dir=tmpdir, reset_config_on_error=True)
    assert "configobj.ParseError: Invalid line" in config.error

    # Since the config should be saved on previous recovery, subsequent instantiation of TriblerConfig
    # should work without the reset flag.
    config = TriblerConfig.load(file=default_config_file, state_dir=tmpdir)
    assert not config.error

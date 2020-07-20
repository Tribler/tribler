from pathlib import Path

import pytest

from tribler_core.exceptions import OperationNotPossibleAtRuntimeException
from tribler_core.utilities.configparser import CallbackConfigParser
from tribler_core.utilities.install_dir import get_lib_path


CONFIG_FILES_DIR = get_lib_path() / "tests/tools/data/config_files/"


def test_configparser_config1():
    ccp = CallbackConfigParser()
    ccp.read_file(CONFIG_FILES_DIR / 'config1.conf')

    assert ccp.get('general', 'version') == 11
    assert ccp.get('search_community', 'enabled')
    assert isinstance(ccp.get('tunnel_community', 'socks5_listen_ports'), list)
    assert not ccp.get('foo', 'bar')


def test_configparser_copy():
    ccp = CallbackConfigParser()
    ccp.read_file(CONFIG_FILES_DIR / 'config1.conf')

    copy_ccp = ccp.copy()
    assert copy_ccp.get('general', 'version') == 11
    assert copy_ccp.get('search_community', 'enabled')


def test_configparser_set_callback():
    def parser_callback(*_):
        return True

    ccp = CallbackConfigParser()
    ccp.set_callback(parser_callback)
    ccp.read_file(CONFIG_FILES_DIR / 'config1.conf')

    ccp.set('search_community', 'enabled', False)
    ccp.set('search_community', 'bar', 42)

    assert not ccp.get('search_community', 'enabled')
    assert ccp.get('search_community', 'bar') == 42


def test_configparser_false_callback():
    def parser_callback(*_):
        return False

    with pytest.raises(OperationNotPossibleAtRuntimeException):
        ccp = CallbackConfigParser()
        ccp.read_file(CONFIG_FILES_DIR / 'config1.conf')
        ccp.set_callback(parser_callback)
        ccp.set('search_community', 'enabled', False)


def test_configparser_write_file(tmpdir):
    ccp = CallbackConfigParser()
    ccp.read_file(CONFIG_FILES_DIR / 'config1.conf')

    new_path = Path(tmpdir) / 'config_new.conf'
    ccp.write_file(new_path)

    assert new_path.is_file()
    ccp.read_file(new_path)

    assert ccp.get('general', 'version') == 11
    assert ccp.get('search_community', 'enabled')
    assert isinstance(ccp.get('tunnel_community', 'socks5_listen_ports'), list)
    assert not ccp.get('foo', 'bar')


def test_configparser_write_file_defaults(tmpdir):
    ccp = CallbackConfigParser(defaults={'foo': 'bar'})

    new_path = Path(tmpdir) / 'config_new.conf'
    ccp.write_file(new_path)

    assert new_path.is_file()
    ccp.read_file(new_path)
    assert ccp.get('DEFAULT', 'foo') == 'bar'

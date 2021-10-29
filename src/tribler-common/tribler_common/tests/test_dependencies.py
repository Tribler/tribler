from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from tribler_common import dependencies
from tribler_common.dependencies import (
    Scope,
    _extract_libraries_from_requirements,
    _get_pip_dependencies,
    check_for_libtorrent,
    check_for_missing_dependencies,
    check_for_pip_dependencies,
    get_dependencies,
    get_missed,
)
from tribler_common.utilities import show_system_popup

import tribler_core
from tribler_core.utilities.path_util import Path

pytestmark = pytest.mark.asyncio


# pylint: disable=protected-access

# fmt: off

def patch_dependencies_module(target, **kwargs):
    """Patch functions from dependencies module"""
    return patch(f'{dependencies.__name__}.{target.__name__}', **kwargs)


async def test_extract_libraries_from_requirements():
    # check that libraries extracts from text correctly
    text = 'PyQt5>=5.14\n' \
           'psutil\n' \
           '\n' \
           'configobj\n'

    assert list(_extract_libraries_from_requirements(text)) == ['PyQt5', 'psutil', 'configobj']


async def test_pip_dependencies_gen():
    # check that libraries extracts from file correctly
    path = Path(tribler_core.__file__).parent / 'requirements.txt'
    assert list(_get_pip_dependencies(path))


async def test_get_dependencies():
    # check that libraries are differ from different scopes
    gui_dependencies = list(get_dependencies(Scope.gui))
    core_dependencies = list(get_dependencies(Scope.core))
    common_dependencies = list(get_dependencies(Scope.common))

    assert gui_dependencies
    assert core_dependencies
    assert common_dependencies


async def test_get_dependencies_wrong_scope():
    with pytest.raises(ValueError):
        get_dependencies(scope=100)


@patch('pkg_resources.working_set', new_callable=MagicMock)
async def test_missed_gen(mock_working_set):
    # in this test `pkg_resources.working_set` is replaced by `MagicMock` to generate a list
    # without one dependency: pony
    mock_working_set.__iter__.return_value = (
        SimpleNamespace(key=d) for d in get_dependencies(Scope.core) if d != 'pony'
    )
    assert list(get_missed(Scope.core)) == ['pony']


@patch_dependencies_module(show_system_popup)
@patch('sys.exit')
async def test_check_for_libtorrent_failed(mock_system_popup, mock_sys_exit):
    # test that in case of failed libtorrent import, sys.exit(1) has been called
    def import_module_with_exception(library):
        if library == 'libtorrent':
            raise ImportError

    with patch('importlib.import_module', side_effect=import_module_with_exception) as mock_import_module:
        check_for_libtorrent()
        mock_import_module.assert_called_once()

    mock_system_popup.assert_called_once()
    mock_sys_exit.assert_called_once()


@patch('importlib.import_module', new=MagicMock())
@patch('sys.exit')
async def test_check_for_libtorrent_succeeded(mock_sys_exit):
    # test that in case of failed libtorrent import, sys.exit(1) has been called
    check_for_libtorrent()
    mock_sys_exit.assert_not_called()


@patch_dependencies_module(get_missed, new=MagicMock(return_value='some_dependency'))
@patch_dependencies_module(show_system_popup)
async def test_check_for_pip_dependencies(mock_system_popup):
    # test that in case of missed dependencies found, show_system_popup has been called
    check_for_pip_dependencies(Scope.core)
    mock_system_popup.assert_called()


@patch_dependencies_module(get_missed, new=MagicMock(return_value=[]))
@patch_dependencies_module(show_system_popup)
async def test_check_for_pip_dependencies_no_missed(mock_system_popup):
    # test that in case of missed dependencies not found, show_system_popup has not been called

    check_for_pip_dependencies(Scope.core)
    mock_system_popup.assert_not_called()


@patch_dependencies_module(check_for_libtorrent)
@patch_dependencies_module(check_for_pip_dependencies)
async def test_check_for_missing_dependencies_core(mock_check_for_libtorrent, mock_check_for_pip_dependencies):
    # check that in case of scope==Scope.core both check_for_libtorrent and check_for_pip_dependencies have been called
    check_for_missing_dependencies(scope=Scope.core)

    mock_check_for_libtorrent.assert_called_once()
    mock_check_for_pip_dependencies.assert_called_once()

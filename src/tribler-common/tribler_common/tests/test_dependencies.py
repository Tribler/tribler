import pytest

from tribler_common.dependencies import (
    Scope,
    _extract_libraries_from_requirements,
    _get_pip_dependencies,
    get_dependencies,
)

import tribler_core
from tribler_core.utilities.path_util import Path

pytestmark = pytest.mark.asyncio


# pylint: disable=protected-access

# fmt: off

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
    # assert that in each scope dependencies are exist
    assert list(get_dependencies(Scope.gui))
    assert list(get_dependencies(Scope.core))
    assert list(get_dependencies(Scope.common))


async def test_get_dependencies_wrong_scope():
    # test that get_dependencies raises AttributeError in case of wrong scope
    with pytest.raises(AttributeError):
        get_dependencies(100)

import pytest

import tribler.core
from tribler.core.utilities.dependencies import (
    Scope,
    _extract_libraries_from_requirements,
    _get_pip_dependencies,
    get_dependencies,
)
from tribler.core.utilities.path_util import Path


# pylint: disable=protected-access

def test_extract_libraries_from_requirements():
    # check that libraries extracts from text correctly
    text = (
        'PyQt5>=5.14\n'
        'psutil  # some comment\n'
        '\n'
        '# comment line\n'
        'configobj\n'
    )
    assert list(_extract_libraries_from_requirements(text)) == ['PyQt5', 'psutil', 'configobj']


def test_pip_dependencies_gen():
    # check that libraries extracts from file correctly
    path = Path(tribler.__file__).parent.parent.parent / 'requirements.txt'
    assert list(_get_pip_dependencies(path))


def test_get_dependencies():
    # assert that in each scope dependencies are exist
    assert list(get_dependencies(Scope.gui))
    assert list(get_dependencies(Scope.core))


def test_get_dependencies_wrong_scope():
    # test that get_dependencies raises AttributeError in case of wrong scope
    with pytest.raises(AttributeError):
        get_dependencies(100)

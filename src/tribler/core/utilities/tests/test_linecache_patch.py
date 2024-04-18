from unittest.mock import Mock, patch

from tribler.core.utilities import linecache_patch


def original_updatecache_mock(filename, *args, **kwargs):
    return [filename]  # as if file consist of a single line that equal to the filename


@patch('tribler.core.utilities.linecache_patch.original_updatecache', original_updatecache_mock)
@patch('sys.frozen', False, create=True)
def test_not_frozen():
    assert linecache_patch.patched_updatecache('src\\tribler\\path') == ['src\\tribler\\path']
    assert linecache_patch.patched_updatecache('tribler/path') == ['tribler/path']
    assert linecache_patch.patched_updatecache('other/path') == ['other/path']


@patch('tribler.core.utilities.linecache_patch.original_updatecache', original_updatecache_mock)
@patch('sys.frozen', True, create=True)
def test_frozen():
    assert linecache_patch.patched_updatecache('src\\tribler\\path') == ['tribler_source\\tribler\\path']
    assert linecache_patch.patched_updatecache('tribler/path') == ['tribler_source/tribler/path']
    assert linecache_patch.patched_updatecache('other/path') == ['other/path']


@patch('tribler.core.utilities.linecache_patch.linecache')
def test_patch(linecache_mock):
    _original_updatecache_mock = Mock(patched=True)
    linecache_mock.updatecache = _original_updatecache_mock

    linecache_patch.patch()
    assert linecache_mock.updatecache is _original_updatecache_mock  # already patched, no second time patch

    _original_updatecache_mock.patched = False
    linecache_patch.patch()
    assert linecache_mock.updatecache is linecache_patch.patched_updatecache

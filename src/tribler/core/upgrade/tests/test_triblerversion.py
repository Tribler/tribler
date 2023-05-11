from tribler.core.upgrade.version_manager import TriblerVersion


def test_create_from_version(tmp_path):
    # Test that we can create a TriblerVersion object from a version string
    v = TriblerVersion(tmp_path, '7.13.1')
    assert v.version.version == [7, 13, 1]


def test_equal(tmp_path):
    # Test correctness of equal comparison
    def v(s):
        return TriblerVersion(tmp_path, s).version

    assert v('7.13.1') == v('7.13.1')
    assert v('7.13.1') != v('7.13.2')


def test_greater(tmp_path):
    # Test correctness of greater than comparison
    def v(s):
        return TriblerVersion(tmp_path, s).version

    assert v('7.13.1') >= v('7.13.1')
    assert v('7.13.1') > v('7.13')
    assert v('7.13.1') > v('7.12')


def test_less(tmp_path):
    # Test correctness of less than comparison
    def v(s):
        return TriblerVersion(tmp_path, s).version

    assert v('7.13.1') <= v('7.13.1')
    assert v('7.13') < v('7.13.1')
    assert v('7.12') < v('7.13.1')


def test_is_ancient(tmp_path):
    # Test that we can correctly determine whether a version is ancient
    last_supported = '7.5'
    assert not TriblerVersion(tmp_path, '7.13').is_ancient(last_supported)
    assert not TriblerVersion(tmp_path, '7.5').is_ancient(last_supported)

    assert TriblerVersion(tmp_path, '7.4').is_ancient(last_supported)

import pytest

from tribler.core.utilities.unicode import recursive_unicode


def test_recursive_unicode_empty():
    # Test that recursive_unicode works on empty items
    assert recursive_unicode({}) == {}
    assert recursive_unicode([]) == []
    assert recursive_unicode(b'') == ''
    assert recursive_unicode('') == ''
    assert recursive_unicode(None) is None


def test_recursive_unicode_unicode_decode_error():
    # Test that recursive_unicode raises an exception on invalid bytes
    with pytest.raises(UnicodeDecodeError):
        recursive_unicode(b'\x80')


def test_recursive_unicode_unicode_decode_error_ignore_errors():
    # Test that recursive_unicode ignores errors on invalid bytes and returns the converted bytes by using chr()
    assert recursive_unicode(b'\x80', ignore_errors=True) == '\x80'


def test_recursive_unicode_complex_object():
    # Test that recursive_unicode works on a complex object
    obj = {
        'list': [
            b'binary',
            {}
        ],
        'sub dict': {
            'sub list': [
                1,
                b'binary',
                {
                    '': b''
                },
            ]
        }
    }

    expected = {
        'list': [
            'binary',
            {}
        ],
        'sub dict': {
            'sub list': [
                1,
                'binary',
                {
                    '': ''
                },
            ]
        }
    }
    assert recursive_unicode(obj) == expected

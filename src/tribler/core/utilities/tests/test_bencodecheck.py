import pytest

from tribler_core.utilities.bencodecheck import is_bencoded


def test_bencode_checker():
    # only bytes is valid argument type
    with pytest.raises(ValueError, match='^Value should be of bytes type. Got: str$'):
        is_bencoded('3:abc')

    # empty encoded string
    assert not is_bencoded(b'')

    # excess data after the end of encoded data
    assert not is_bencoded(b'3:abc3:abc')

    # excess end marker after the end of the encoded data
    assert not is_bencoded(b'3:abce')

    # empty string
    assert is_bencoded(b'0:')

    # normal string with 'abc' value
    assert is_bencoded(b'3:abc')

    # the leading zeroes are not allowed in string length specification
    assert not is_bencoded(b'03:abc')

    # string value is too short
    assert not is_bencoded(b'4:abc')

    # colon is not present in string encoded data
    assert not is_bencoded(b'3abc')

    # zero int value
    assert is_bencoded(b'i0e')

    # positive int value
    assert is_bencoded(b'i123e')

    # negative int value
    assert is_bencoded(b'i-123e')

    # leading zeroes are not allowed in int value
    assert not is_bencoded(b'i0123e')
    assert not is_bencoded(b'i00e')

    # -0 is not allowed as int value
    assert not is_bencoded(b'i-0e')
    assert not is_bencoded(b'i-00e')
    assert not is_bencoded(b'i-0123e')

    # test for empty dict
    assert is_bencoded(b'de')

    # test for a normal dict {'abc': 'def'}
    assert is_bencoded(b'd3:abc3:defe')

    # dict key without a dict value
    assert not is_bencoded(b'd3:abce')

    # dict without end marker
    assert not is_bencoded(b'd3:abc3:def')

    # non-string key
    assert not is_bencoded(b'di123e3:defe')

    # nested dicts
    assert is_bencoded(b'd3:abcd3:foo3:baree')

    # empty list
    assert is_bencoded(b'le')

    # a normal list with four elements
    assert is_bencoded(b'li123e3:abcd3:foo3:barelee')

    # nested lists
    assert is_bencoded(b'lli123e3:abceli456e3:defee')

    # no end marker for list
    assert not is_bencoded(b'l3:abc')

    # invalid data
    assert not is_bencoded(b'hello')
    assert not is_bencoded(b'<?=#.')

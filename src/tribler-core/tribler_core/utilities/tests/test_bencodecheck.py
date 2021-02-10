import pytest

from tribler_core.utilities.bencodecheck import is_bencoded


def test_bcheck_nobytes():
    # only bytes is valid argument type
    with pytest.raises(ValueError, match='^Value should be of bytes type. Got: str$'):
        is_bencoded('3:abc')

def test_bcheck_empty():
    assert not is_bencoded(b'')

def test_bcheck_excess_data1():
    # excess data after the end of encoded string
    assert not is_bencoded(b'3:abc3:abc')

def test_bcheck_excess_data2():
    # excess end marker after the end of encoded string
    assert not is_bencoded(b'3:abce')

def test_bcheck_str1():
    # empty string
    assert is_bencoded(b'0:')

def test_bcheck_str2():
    # normal string with 'abc' value
    assert is_bencoded(b'3:abc')

def test_bcheck_str3():
    # the leading zeroes are not allowed in string length
    assert not is_bencoded(b'03:abc')

def test_bcheck_str4():
    # string value is too short
    assert not is_bencoded(b'4:abc')

def test_bcheck_str5():
    # semicolon is not present
    assert not is_bencoded(b'3abc')

def test_bcheck_int1():
    # zero int value
    assert is_bencoded(b'i0e')

def test_bcheck_int2():
    # positive value
    assert is_bencoded(b'i123e')

def test_bcheck_int3():
    # negative value
    assert is_bencoded(b'i-123e')

def test_bcheck_int4():
    # leading zeroes are not allowed in int value
    assert not is_bencoded(b'i0123e')
    assert not is_bencoded(b'i00e')

def test_bcheck_int5():
    # -0 is not allowed as int value
    assert not is_bencoded(b'i-0e')
    assert not is_bencoded(b'i-00e')
    assert not is_bencoded(b'i-0123e')

def test_bcheck_dict1():
    # test for empty dict
    assert is_bencoded(b'de')

def test_bcheck_dict2():
    # test for a normal dict {'abc': 'def'}
    assert is_bencoded(b'd3:abc3:defe')

def test_bcheck_dict3():
    # dict key without a dict value
    assert not is_bencoded(b'd3:abce')

def test_bcheck_dict4():
    # dict without end marker
    assert not is_bencoded(b'd3:abc3:def')

def test_bcheck_dict5():
    # non-string key
    assert not is_bencoded(b'di123e3:defe')

def test_bcheck_dict6():
    # nested dicts
    assert is_bencoded(b'd3:abcd3:foo3:baree')

def test_bcheck_list1():
    # empty list
    assert is_bencoded(b'le')

def test_bcheck_list2():
    # a normal list with four elements
    assert is_bencoded(b'li123e3:abcd3:foo3:barelee')

def test_bcheck_list3():
    # nested lists
    assert is_bencoded(b'lli123e3:abceli456e3:defee')

def test_bcheck_list4():
    # no end marker
    assert not is_bencoded(b'l3:abc')

def test_bcheck_garbage1():
    # invalid data
    assert not is_bencoded(b'hello')

def test_bcheck_garbage2():
    # invalid data
    assert not is_bencoded(b'<?=#.')

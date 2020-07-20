# -*- coding:utf-8 -*-
from unittest.mock import Mock

from tribler_core.restapi.util import fix_unicode_array, fix_unicode_dict, get_parameter


def test_get_parameter():
    """
    Testing the get_parameters method in REST API util class
    """
    assert get_parameter({'test': [42]}, 'test') == 42
    assert get_parameter({}, 'test') is None


def test_fix_unicode_array():
    """
    Testing the fix of a unicode array
    """
    arr1 = ['a', 'b', 'c', 'd']
    assert fix_unicode_array(arr1) == ['a', 'b', 'c', 'd']
    arr2 = ['a', b'\xa1']
    assert fix_unicode_array(arr2) == ['a', '']
    arr3 = [1, 2, 3, '4']
    assert fix_unicode_array(arr3) == [1, 2, 3, '4']
    arr4 = [{'a': 'b'}]
    assert fix_unicode_array(arr4) == [{'a': 'b'}]


def test_fix_unicode_dict():
    """
    Testing the fix of a unicode dictionary
    """
    dict1 = {'a': 'b', 'c': 'd'}
    assert fix_unicode_dict(dict1) == {'a': 'b', 'c': 'd'}
    dict2 = {'a': b'\xa2'}
    assert fix_unicode_dict(dict2) == {'a': ''}
    dict3 = {'a': [1, 2], 'b': ['1', '2']}
    assert fix_unicode_dict(dict3) == {'a': [1, 2], 'b': ['1', '2']}
    dict4 = {'a': ['1', b'2\xa3']}
    assert fix_unicode_dict(dict4) == {'a': ['1', '2']}
    dict5 = {'a': ('1', b'2\xa3')}
    assert fix_unicode_dict(dict5) == {'a': ['1', '2']}
    dict6 = {'a': {'b': b'c\xa4'}}
    assert fix_unicode_dict(dict6) == {'a': {'b': 'c'}}
    dict7 = {'a': 'ѡ'}
    assert fix_unicode_dict(dict7) == {'a': 'ѡ'}
    obj = Mock
    dict8 = {'a': {'b': obj}}
    assert fix_unicode_dict(dict8) == {'a': {'b': obj}}

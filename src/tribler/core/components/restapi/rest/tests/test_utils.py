from types import SimpleNamespace
from unittest.mock import Mock

from tribler.core.components.restapi.rest.utils import _format_frames, fix_unicode_array, fix_unicode_dict, \
    get_parameter, shorten


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


def test_shorten():
    """ Test that `shorten` returns correct string"""
    assert not shorten(None)
    assert shorten('long string', width=100) == 'long string'
    assert shorten('long string', width=3, placeholder='...') == 'lon...'
    assert shorten('long string', width=3, placeholder='...', cut_at_the_end=False) == '...ing'


def test_format_frames():
    """ Test that `format_frames` returns correct string"""
    assert not list(_format_frames(None))

    frames = SimpleNamespace(
        f_code=SimpleNamespace(
            co_filename='short_file',
            co_name='function'
        ),
        f_lineno=1,
        f_locals={
            'key': 'value'
        },
        f_back=SimpleNamespace(
            f_code=SimpleNamespace(
                co_filename='long_file' * 100,
                co_name='function'
            ),
            f_lineno=1,
            f_locals={
                'key': 'long_value' * 100
            },
            f_back=None
        )
    )
    expected = [
        "short_file:, line 1, in function\n"
        "    <source is unknown>\n"
        "\tkey = 'valu[...]\n",
        '[...]elong_file:, line 1, in function\n'
        '    <source is unknown>\n'
        "\tkey = 'long[...]\n"
    ]

    assert list(_format_frames(frames, file_width=10, value_width=5)) == expected

from tribler_common.sentry_reporter.sentry_tools import (
    delete_item,
    distinct_by,
    extract_dict,
    format_version,
    get_first_item,
    get_last_item,
    get_value,
    modify_value,
    parse_os_environ,
    parse_stacktrace,
)


def test_first():
    assert get_first_item(None, '') == ''
    assert get_first_item([], '') == ''
    assert get_first_item(['some'], '') == 'some'
    assert get_first_item(['some', 'value'], '') == 'some'

    assert get_first_item((), '') == ''
    assert get_first_item(('some', 'value'), '') == 'some'

    assert get_first_item(None, None) is None


def test_last():
    assert get_last_item(None, '') == ''
    assert get_last_item([], '') == ''
    assert get_last_item(['some'], '') == 'some'
    assert get_last_item(['some', 'value'], '') == 'value'

    assert get_last_item((), '') == ''
    assert get_last_item(('some', 'value'), '') == 'value'

    assert get_last_item(None, None) is None


def test_delete():
    assert delete_item({}, None) == {}

    assert delete_item({'key': 'value'}, None) == {'key': 'value'}
    assert delete_item({'key': 'value'}, 'missed_key') == {'key': 'value'}
    assert delete_item({'key': 'value'}, 'key') == {}


def test_parse_os_environ():
    # simple tests
    assert parse_os_environ(None) == {}
    assert parse_os_environ([]) == {}
    assert parse_os_environ(['KEY:value']) == {'KEY': 'value'}

    assert parse_os_environ(['KEY:value', 'KEY1:value1', 'KEY2:value2']) == {
        'KEY': 'value',
        'KEY1': 'value1',
        'KEY2': 'value2',
    }

    # test multiply `:`
    assert parse_os_environ(['KEY:value:and:some']) == {'KEY': 'value:and:some'}

    # test no `:`
    assert parse_os_environ(['KEY:value', 'key']) == {'KEY': 'value'}


def test_parse_stacktrace():
    assert list(parse_stacktrace(None)) == []
    assert list(parse_stacktrace('')) == []
    assert list(parse_stacktrace('\n')) == [[]]
    assert list(parse_stacktrace('\n\n')) == [[]]
    assert list(parse_stacktrace('line1\n\nline2\\nline3')) == [['line1', 'line2', 'line3']]

    # split --LONG TEXT-- and --CONTEXT-- parts
    assert list(parse_stacktrace('l1\nl2--LONG TEXT--l3\nl4--CONTEXT--l5\nl6')) == [
        ['l1', 'l2'],
        ['l3', 'l4'],
        ['l5', 'l6'],
    ]

    # split custom parts
    assert list(parse_stacktrace('l1\nl2customl3\nl4', delimiters=['custom'])) == [
        ['l1', 'l2'],
        ['l3', 'l4'],
    ]


def test_modify():
    assert modify_value(None, None, None) is None
    assert modify_value({}, None, None) == {}
    assert modify_value({}, '', None) == {}

    assert modify_value({}, 'key', lambda value: '') == {}
    assert modify_value({'a': 'b'}, 'key', lambda value: '') == {'a': 'b'}
    assert modify_value({'a': 'b', 'key': 'value'}, 'key', lambda value: '') == {'a': 'b', 'key': ''}


def test_safe_get():
    assert get_value(None, None, None) is None
    assert get_value(None, None, {}) == {}

    assert get_value(None, 'key', {}) == {}

    assert get_value({'key': 'value'}, 'key', {}) == 'value'
    assert get_value({'key': 'value'}, 'key1', {}) == {}


def test_distinct():
    assert distinct_by(None, None) is None
    assert distinct_by([], None) == []
    assert distinct_by([{'key': 'b'}, {'key': 'b'}, {'key': 'c'}, {'': ''}], 'key') == [
        {'key': 'b'},
        {'key': 'c'},
        {'': ''},
    ]

    # test nested
    assert distinct_by([{'a': {}}], 'b') == [{'a': {}}]


def test_skip_dev_version():
    assert format_version(None) is None
    assert format_version('') == ''
    assert format_version('7.6.0') == '7.6.0'
    assert format_version('7.6.0-GIT') is None

    # version from deployment tester
    assert format_version('7.7.1-17-gcb73f7baa') == '7.7.1'

    # release candidate
    assert format_version('7.7.1-RC1-10-abcd') == '7.7.1-RC1'

    # experimental versions
    assert format_version('7.7.1-exp1-1-abcd ') == '7.7.1-exp1'
    assert format_version('7.7.1-someresearchtopic-7-abcd ') == '7.7.1-someresearchtopic'


def test_extract_dict():
    assert not extract_dict(None, None)

    assert extract_dict({}, '') == {}
    assert extract_dict({'k': 'v', 'k1': 'v1'}, r'\w$') == {'k': 'v'}

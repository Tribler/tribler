from tribler_common.sentry_reporter.sentry_tools import (
    delete_item,
    distinct_by,
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
    assert parse_stacktrace(None) == []
    assert parse_stacktrace('') == []
    assert parse_stacktrace('\n') == []
    assert parse_stacktrace('\n\n') == []
    assert parse_stacktrace('some\n\nvalue') == ['some', 'value']


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
    assert distinct_by([{'key': 'b'}, {'key': 'b'}, {'key': 'c'}, {'': ''}], 'key') == \
           [{'key': 'b'}, {'key': 'c'}, {'': ''}]

    # test nested
    assert distinct_by([{'a': {}}], 'b') == [{'a': {}}]

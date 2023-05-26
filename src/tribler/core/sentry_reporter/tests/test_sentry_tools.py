import pytest

from tribler.core.sentry_reporter.sentry_tools import (
    _re_search_exception, delete_item,
    distinct_by,
    extract_dict,
    format_version,
    get_first_item,
    get_last_item,
    get_value,
    modify_value,
    obfuscate_string, parse_last_core_output,
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


FORMATTED_VERSIONS = [
    (None, None),
    ('', ''),
    ('7.6.0', '7.6.0'),
    ('7.6.0-GIT', 'dev'),  # version from developers machines
    ('7.7.1-17-gcb73f7baa', '7.7.1'),  # version from deployment tester
    ('7.7.1-RC1-10-abcd', '7.7.1-RC1'),  # release candidate
    ('7.7.1-exp1-1-abcd ', '7.7.1-exp1'),  # experimental versions
    ('7.7.1-someresearchtopic-7-abcd ', '7.7.1-someresearchtopic'),
]


@pytest.mark.parametrize('git_version, sentry_version', FORMATTED_VERSIONS)
def test_format_version(git_version, sentry_version):
    assert format_version(git_version) == sentry_version


def test_extract_dict():
    assert not extract_dict(None, None)

    assert extract_dict({}, '') == {}
    assert extract_dict({'k': 'v', 'k1': 'v1'}, r'\w$') == {'k': 'v'}


OBFUSCATED_STRINGS = [
    (None, None),
    ('', ''),
    ('any', 'challenge'),
    ('string', 'quality'),
]

EXCEPTION_STRINGS = [
    ('OverflowError: bind(): port must be 0-65535',
     ('OverflowError', 'bind(): port must be 0-65535'),
     ),

    ("pony.orm.core.TransactionIntegrityError : MiscData['db_version'] cannot be stored. IntegrityError: UNIQUE",
     ('pony.orm.core.TransactionIntegrityError', "MiscData['db_version'] cannot be stored. IntegrityError: UNIQUE"),
     ),

    ('ERROR <exception_handler:100>', None)
]


@pytest.mark.parametrize('given, expected', OBFUSCATED_STRINGS)
def test_obfuscate_string(given, expected):
    assert obfuscate_string(given) == expected


@pytest.mark.parametrize('given, expected', EXCEPTION_STRINGS)
def test_parse_last_core_output_re(given, expected):
    # Test that `_re_search_exception` matches with the expected values from the `EXCEPTION_STRINGS`
    if m := _re_search_exception.match(given):
        exception_type, exception_text = expected

        assert m.group(1) == exception_type
        assert m.group(2) == exception_text
    else:  # no match
        assert m == expected


def test_parse_last_core_output():
    # Test that `parse_last_core_output` correctly extract the last core exception from the real raw core output

    last_core_output = '''
pony.orm.core.TransactionIntegrityError: Object MiscData['db_version'] cannot be stored in the database. IntegrityError
ERROR <exception_handler:100> CoreExceptionHandler.unhandled_error_observer(): Unhandled exception occurred! bind(): 
Traceback (most recent call last):
  File "/Users/<user>/Projects/github.com/Tribler/tribler/src/tribler/core/components/component.py", line 61, in start
    await self.run()
  File "/Users/<user>/Projects/github.com/Tribler/tribler/src/tribler/core/components/restapi/restapi_component.py", 
    await rest_manager.start()
  File "/Users/<user>/Projects/github.com/Tribler/tribler/src/tribler/core/components/restapi/rest/rest_manager.py", 
    await self.site.start()
  File "/Users/<user>/Projects/github.com/Tribler/tribler/venv/lib/python3.8/site-packages/aiohttp/web_runner.py", 
    self._server = await loop.create_server(
  File "/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.8/lib/python3.8/
    sock.bind(sa)
OverflowError: bind(): port must be 0-65535.Sentry is attempting to send 1 pending error messages
Waiting up to 2 seconds
Press Ctrl-C to quit
    '''
    last_core_exception = parse_last_core_output(last_core_output)
    assert last_core_exception.type == 'OverflowError'
    assert last_core_exception.message == 'bind(): port must be 0-65535.'


def test_parse_last_core_output_no_match():
    # Test that `parse_last_core_output` returns None in the case there is no exceptions in the raw core output

    last_core_exception = parse_last_core_output('last core output without exceptions')
    assert not last_core_exception

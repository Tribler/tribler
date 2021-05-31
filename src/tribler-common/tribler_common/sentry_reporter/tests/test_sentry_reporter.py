import pytest

from tribler_common.sentry_reporter.sentry_reporter import (
    EXCEPTION, OS_ENVIRON,
    PLATFORM_DETAILS,
    SentryReporter,
    SentryStrategy,
    VALUES, this_sentry_strategy,
)
from tribler_common.sentry_reporter.sentry_scrubber import SentryScrubber


# fmt: off

@pytest.fixture(name="mock_reporter")  # this workaround implemented only for pylint
def fixture_mock_reporter():
    class MockReporter:
        def __init__(self):
            self._allow_sending = None

        def get_allow_sending(self):
            return self._allow_sending

        def allow_sending(self, value, _=None):
            self._allow_sending = value

    return MockReporter()


def test_init():
    assert SentryReporter.init('')


def test_set_user():
    assert SentryReporter.set_user(b'some_id') == {
        'id': 'db69fe66ec6b6b013c2f7d271ce17cae',
        'username': 'Wanda Brown',
    }

    assert SentryReporter.set_user(b'11111100100') == {
        'id': '91f900f528d5580581197c2c6a4adbbc',
        'username': 'Jennifer Herrera',
    }


def test_send_defaults():
    assert SentryReporter.send_event(None, None, None) is None

    assert SentryReporter.send_event(event={}) == {
        'contexts': {
            'browser': {'name': 'Tribler', 'version': None},
            'reporter': {
                '_stacktrace': [],
                '_stacktrace_context': [],
                '_stacktrace_extra': [],
                'comments': None,
                OS_ENVIRON: {},
                'sysinfo': {},
                'events': {},
            },
        },
        'tags': {'machine': None, 'os': None, 'platform': None, PLATFORM_DETAILS: None, 'version': None},
    }


def test_send_post_data():
    assert SentryReporter.send_event(
        event={'a': 'b'},
        post_data={
            "version": '0.0.0',
            "machine": 'x86_64',
            "os": 'posix',
            "timestamp": 42,
            "sysinfo": '',
            "comments": 'comment',
            "stack": 'l1\nl2--LONG TEXT--l3\nl4',
        },
    ) == {
               'a': 'b',
               'contexts': {
                   'browser': {'name': 'Tribler', 'version': '0.0.0'},
                   'reporter': {
                       '_stacktrace': ['l1', 'l2'],
                       '_stacktrace_context': [],
                       '_stacktrace_extra': ['l3', 'l4'],
                       'comments': 'comment',
                       'os.environ': {},
                       'sysinfo': {},
                       'events': {},
                   },
               },
               'tags': {'machine': 'x86_64', 'os': 'posix', 'platform': None, PLATFORM_DETAILS: None,
                        'version': '0.0.0'},
           }


def test_send_sys_info():
    assert SentryReporter.send_event(
        event={},
        sys_info={
            'platform': ['darwin'],
            PLATFORM_DETAILS: ['details'],
            OS_ENVIRON: ['KEY:VALUE', 'KEY1:VALUE1'],
            'event_1': [{'type': ''}],
            'request_1': [{}],
            'event_2': [],
            'request_2': [],
        },
    ) == {
               'contexts': {
                   'browser': {'name': 'Tribler', 'version': None},
                   'reporter': {
                       '_stacktrace': [],
                       '_stacktrace_context': [],
                       '_stacktrace_extra': [],
                       'comments': None,
                       OS_ENVIRON: {'KEY': 'VALUE', 'KEY1': 'VALUE1'},
                       'sysinfo': {'platform': ['darwin'], PLATFORM_DETAILS: ['details']},
                       'events': {'event_1': [{'type': ''}], 'request_1': [{}], 'event_2': [], 'request_2': []},
                   },
               },
               'tags': {'machine': None, 'os': None, 'platform': 'darwin', 'platform.details': 'details',
                        'version': None},
           }


def test_send_additional_tags():
    assert SentryReporter.send_event(event={}, additional_tags={'tag_key': 'tag_value'}) == {
        'contexts': {
            'browser': {'name': 'Tribler', 'version': None},
            'reporter': {
                '_stacktrace': [],
                '_stacktrace_context': [],
                '_stacktrace_extra': [],
                'comments': None,
                OS_ENVIRON: {},
                'sysinfo': {},
                'events': {},
            },
        },
        'tags': {
            'machine': None,
            'os': None,
            'platform': None,
            'platform.details': None,
            'version': None,
            'tag_key': 'tag_value',
        },
    }


def test_before_send():
    SentryReporter.thread_strategy.set(None)  # default

    scrubber = SentryScrubber()
    SentryReporter.init('', scrubber=scrubber)

    # pylint: disable=protected-access
    SentryReporter.last_event = None

    assert SentryReporter._before_send({}, {}) == {}
    assert SentryReporter._before_send(None, {}) is None
    assert SentryReporter._before_send(None, None) is None

    SentryReporter.global_strategy = SentryStrategy.SEND_SUPPRESSED
    assert SentryReporter.last_event is None

    # check that an event is stored
    assert SentryReporter._before_send({'a': 'b'}, None) is None
    assert SentryReporter.last_event == {'a': 'b'}

    # check an event has been processed
    SentryReporter.global_strategy = SentryStrategy.SEND_ALLOWED
    assert SentryReporter._before_send({'c': 'd'}, None) == {'c': 'd'}
    assert SentryReporter.last_event == {'a': 'b'}

    # check that event can be ignored
    assert SentryReporter._before_send({'a': 'b'}, {'exc_info': [KeyboardInterrupt]}) is None

    # check information has been scrubbed
    assert SentryReporter._before_send({'contexts': {'reporter': {'_stacktrace': ['/Users/username/']}}}, None) == {
        'contexts': {'reporter': {'_stacktrace': [f'/Users/{scrubber.placeholder_user}/']}}
    }

    # check release
    assert SentryReporter._before_send({'release': '7.6.0'}, None) == {'release': '7.6.0'}
    assert SentryReporter._before_send({'release': '7.6.0-GIT'}, None) == {'release': None}

    # check confirmation
    SentryReporter.global_strategy = SentryStrategy.SEND_ALLOWED_WITH_CONFIRMATION
    SentryReporter.get_confirmation = lambda e: False
    assert SentryReporter._before_send({'a': 'b'}, None) is None

    SentryReporter.get_confirmation = lambda e: True
    assert SentryReporter._before_send({'a': 'b'}, None) == {'a': 'b'}


def test_event_from_exception():
    assert not SentryReporter.event_from_exception(None)

    # sentry sdk is not initialised, so None will be returned
    SentryReporter.last_event = None
    assert not SentryReporter.event_from_exception(Exception('test'))


def test_add_breadcrumb():
    # test: None does not produce error
    assert SentryReporter.add_breadcrumb(None, None, None) is None
    assert SentryReporter.add_breadcrumb('message', 'category', 'level') is None
    assert SentryReporter.add_breadcrumb('message', 'category', 'level', named_arg='some') is None


def test_sentry_strategy():
    SentryReporter.thread_strategy.set(None)  # default
    SentryReporter.global_strategy = SentryStrategy.SEND_ALLOWED_WITH_CONFIRMATION

    with this_sentry_strategy(SentryStrategy.SEND_ALLOWED):
        assert SentryReporter.global_strategy == SentryStrategy.SEND_ALLOWED_WITH_CONFIRMATION
        assert SentryReporter.thread_strategy.get() == SentryStrategy.SEND_ALLOWED

    assert SentryReporter.thread_strategy.get() is None
    assert SentryReporter.global_strategy == SentryStrategy.SEND_ALLOWED_WITH_CONFIRMATION


def test_get_actual_strategy():
    SentryReporter.thread_strategy.set(None)  # default
    SentryReporter.global_strategy = SentryStrategy.SEND_ALLOWED_WITH_CONFIRMATION

    assert SentryReporter.get_actual_strategy() == SentryStrategy.SEND_ALLOWED_WITH_CONFIRMATION

    SentryReporter.thread_strategy.set(SentryStrategy.SEND_ALLOWED)
    assert SentryReporter.get_actual_strategy() == SentryStrategy.SEND_ALLOWED


def test_retrieve_error_message_from_stacktrace():
    post_data = {"stack": '--LONG TEXT--Type: Text'}
    event = SentryReporter.send_event({EXCEPTION: {VALUES: []}}, post_data, None, None, True)

    assert event[EXCEPTION][VALUES][0]['type'] == 'Type'
    assert event[EXCEPTION][VALUES][0]['value'] == ' Text'

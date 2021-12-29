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
# pylint: disable=redefined-outer-name, protected-access


@pytest.fixture
def sentry_reporter():
    return SentryReporter()


def test_init(sentry_reporter):
    assert sentry_reporter.init('')


def test_set_user(sentry_reporter):
    assert sentry_reporter.set_user(b'some_id') == {
        'id': 'db69fe66ec6b6b013c2f7d271ce17cae',
        'username': 'Wanda Brown',
    }

    assert sentry_reporter.set_user(b'11111100100') == {
        'id': '91f900f528d5580581197c2c6a4adbbc',
        'username': 'Jennifer Herrera',
    }


def test_send_defaults(sentry_reporter):
    assert sentry_reporter.send_event(None, None, None) is None

    assert sentry_reporter.send_event(event={}) == {
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


def test_send_post_data(sentry_reporter):
    actual = sentry_reporter.send_event(event={'a': 'b'},
                                        post_data={"version": '0.0.0', "machine": 'x86_64', "os": 'posix',
                                                   "timestamp": 42, "sysinfo": '', "comments": 'comment',
                                                   "stack": 'l1\nl2--LONG TEXT--l3\nl4', }, )
    expected = {
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
    assert actual == expected


def test_send_sys_info(sentry_reporter):
    actual = sentry_reporter.send_event(event={}, sys_info={'platform': ['darwin'], PLATFORM_DETAILS: ['details'],
                                                            OS_ENVIRON: ['KEY:VALUE', 'KEY1:VALUE1'],
                                                            'event_1': [{'type': ''}], 'request_1': [{}], 'event_2': [],
                                                            'request_2': [], }, )
    expected = {
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
    assert actual == expected


def test_send_additional_tags(sentry_reporter):
    actual = sentry_reporter.send_event(event={}, additional_tags={'tag_key': 'tag_value'})
    expected = {
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
    assert actual == expected


def test_before_send(sentry_reporter):
    sentry_reporter.thread_strategy.set(None)  # default

    scrubber = SentryScrubber()
    sentry_reporter.init('', scrubber=scrubber)
    sentry_reporter.last_event = None

    assert sentry_reporter._before_send({}, {}) == {}
    assert sentry_reporter._before_send(None, {}) is None
    assert sentry_reporter._before_send(None, None) is None

    sentry_reporter.global_strategy = SentryStrategy.SEND_SUPPRESSED
    assert sentry_reporter.last_event is None

    # check that an event is stored
    assert sentry_reporter._before_send({'a': 'b'}, None) is None
    assert sentry_reporter.last_event == {'a': 'b'}

    # check an event has been processed
    sentry_reporter.global_strategy = SentryStrategy.SEND_ALLOWED
    assert sentry_reporter._before_send({'c': 'd'}, None) == {'c': 'd'}
    assert sentry_reporter.last_event == {'a': 'b'}

    # check that event can be ignored
    assert sentry_reporter._before_send({'a': 'b'}, {'exc_info': [KeyboardInterrupt]}) is None

    # check information has been scrubbed
    assert sentry_reporter._before_send({'contexts': {'reporter': {'_stacktrace': ['/Users/username/']}}}, None) == {
        'contexts': {'reporter': {'_stacktrace': [f'/Users/{scrubber.placeholder_user}/']}}
    }

    # check release
    assert sentry_reporter._before_send({'release': '7.6.0'}, None) == {'release': '7.6.0'}
    assert sentry_reporter._before_send({'release': '7.6.0-GIT'}, None) == {'release': None}

    # check confirmation
    sentry_reporter.global_strategy = SentryStrategy.SEND_ALLOWED_WITH_CONFIRMATION
    sentry_reporter.get_confirmation = lambda e: False
    assert sentry_reporter._before_send({'a': 'b'}, None) is None

    sentry_reporter.get_confirmation = lambda e: True
    assert sentry_reporter._before_send({'a': 'b'}, None) == {'a': 'b'}


def test_event_from_exception(sentry_reporter):
    assert not sentry_reporter.event_from_exception(None)
    # sentry sdk is not initialised, so None will be returned
    assert not sentry_reporter.event_from_exception(Exception('test'))


def test_add_breadcrumb(sentry_reporter):
    # test: None does not produce error
    assert sentry_reporter.add_breadcrumb(None, None, None) is None
    assert sentry_reporter.add_breadcrumb('message', 'category', 'level') is None
    assert sentry_reporter.add_breadcrumb('message', 'category', 'level', named_arg='some') is None


def test_sentry_strategy(sentry_reporter):
    sentry_reporter.thread_strategy.set(None)  # default
    sentry_reporter.global_strategy = SentryStrategy.SEND_ALLOWED_WITH_CONFIRMATION

    with this_sentry_strategy(sentry_reporter, SentryStrategy.SEND_ALLOWED) as reporter:
        assert reporter.global_strategy == SentryStrategy.SEND_ALLOWED_WITH_CONFIRMATION
        assert reporter.thread_strategy.get() == SentryStrategy.SEND_ALLOWED

    assert sentry_reporter.thread_strategy.get() is None
    assert sentry_reporter.global_strategy == SentryStrategy.SEND_ALLOWED_WITH_CONFIRMATION


def test_get_actual_strategy(sentry_reporter):
    sentry_reporter.thread_strategy.set(None)  # default
    sentry_reporter.global_strategy = SentryStrategy.SEND_ALLOWED_WITH_CONFIRMATION

    assert sentry_reporter.get_actual_strategy() == SentryStrategy.SEND_ALLOWED_WITH_CONFIRMATION

    sentry_reporter.thread_strategy.set(SentryStrategy.SEND_ALLOWED)
    assert sentry_reporter.get_actual_strategy() == SentryStrategy.SEND_ALLOWED


def test_retrieve_error_message_from_stacktrace(sentry_reporter):
    post_data = {"stack": '--LONG TEXT--Type: Text'}
    event = sentry_reporter.send_event({EXCEPTION: {VALUES: []}}, post_data, None, None, True)

    assert event[EXCEPTION][VALUES][0]['type'] == 'Type'
    assert event[EXCEPTION][VALUES][0]['value'] == ' Text'

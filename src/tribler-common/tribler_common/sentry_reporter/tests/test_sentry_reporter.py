import pytest

from tribler_common.sentry_reporter.sentry_reporter import (
    OS_ENVIRON,
    PLATFORM_DETAILS,
    SentryReporter,
    SentryStrategy,
    this_sentry_strategy,
)
from tribler_common.sentry_reporter.sentry_scrubber import SentryScrubber


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


def test_send():
    assert SentryReporter.send_event(None, None, None) is None

    # test return defaults
    assert SentryReporter.send_event({}, None, None) == {
        'contexts': {
            'browser': {'name': 'Tribler', 'version': None},
            'reporter': {'_stacktrace': [], 'comments': None, OS_ENVIRON: {}, 'sysinfo': None},
        },
        'tags': {'machine': None, 'os': None, 'platform': None, PLATFORM_DETAILS: None, 'version': None},
    }

    # test post_data
    post_data = {
        "version": '0.0.0',
        "machine": 'x86_64',
        "os": 'posix',
        "timestamp": 42,
        "sysinfo": '',
        "comments": 'comment',
        "stack": 'some\nstack',
    }

    assert SentryReporter.send_event({'a': 'b'}, post_data, None) == {
        'a': 'b',
        'contexts': {
            'browser': {'name': 'Tribler', 'version': '0.0.0'},
            'reporter': {'_stacktrace': ['some', 'stack'], 'comments': 'comment', 'os.environ': {}, 'sysinfo': None},
        },
        'tags': {'machine': 'x86_64', 'os': 'posix', 'platform': None, 'platform.details': None, 'version': '0.0.0'},
    }

    # test sys_info
    post_data = {"sysinfo": 'key\tvalue\nkey1\tvalue1\n'}

    assert SentryReporter.send_event({}, post_data, None) == {
        'contexts': {
            'browser': {'name': 'Tribler', 'version': None},
            'reporter': {'_stacktrace': [], 'comments': None, 'os.environ': {}, 'sysinfo': None},
        },
        'tags': {'machine': None, 'os': None, 'platform': None, 'platform.details': None, 'version': None},
    }

    sys_info = {'platform': ['darwin'], 'platform.details': ['details'], OS_ENVIRON: ['KEY:VALUE', 'KEY1:VALUE1']}
    assert SentryReporter.send_event({}, None, sys_info) == {
        'contexts': {
            'browser': {'name': 'Tribler', 'version': None},
            'reporter': {
                '_stacktrace': [],
                'comments': None,
                'os.environ': {'KEY': 'VALUE', 'KEY1': 'VALUE1'},
                'sysinfo': sys_info,
            },
        },
        'tags': {'machine': None, 'os': None, 'platform': 'darwin', 'platform.details': 'details', 'version': None},
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

import pytest

from tribler_common.sentry_reporter.sentry_reporter import (
    AllowSentryReports,
    OS_ENVIRON,
    PLATFORM_DETAILS,
    SentryReporter,
)
from tribler_common.sentry_reporter.sentry_scrubber import SentryScrubber


@pytest.fixture(name="reporter")  # this workaround implemented only for pylint
def fixture_reporter():
    return SentryReporter()


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


def test_init(reporter):
    assert reporter.init('')


def test_states():
    instance1 = SentryReporter()
    instance2 = SentryReporter()
    assert instance1 != instance2
    assert instance1.get_allow_sending() == instance2.get_allow_sending()

    instance1.allow_sending_globally(not instance2.get_allow_sending())
    assert instance1.get_allow_sending() == instance2.get_allow_sending()


def test_set_user(reporter):
    assert reporter.set_user('some_id'.encode('utf-8')) == {
        'id': 'db69fe66ec6b6b013c2f7d271ce17cae',
        'username': 'Wanda Brown',
    }

    assert reporter.set_user(b'11111100100') == {
        'id': '91f900f528d5580581197c2c6a4adbbc',
        'username': 'Jennifer Herrera',
    }


def test_allow_sentry(reporter):
    reporter.allow_sending_in_thread(None)

    reporter.allow_sending_globally(True)
    assert reporter.get_allow_sending()

    reporter.allow_sending_globally(False)
    assert not reporter.get_allow_sending()

    reporter.allow_sending_globally(True)
    reporter.allow_sending_in_thread(True)
    assert reporter.get_allow_sending()

    reporter.allow_sending_globally(True)
    reporter.allow_sending_in_thread(False)
    assert not reporter.get_allow_sending()

    reporter.allow_sending_globally(False)
    reporter.allow_sending_in_thread(True)
    assert reporter.get_allow_sending()

    reporter.allow_sending_globally(False)
    reporter.allow_sending_in_thread(False)
    assert not reporter.get_allow_sending()


def test_allow_sentry_reports(reporter):
    # test base logic

    # test allow_sending_globally=True
    reporter.allow_sending_in_thread(None)
    reporter.allow_sending_globally(True)
    assert reporter.get_allow_sending()

    with AllowSentryReports(reporter=reporter):
        assert reporter.get_allow_sending() is True

    with AllowSentryReports(value=False, reporter=reporter):
        assert reporter.get_allow_sending() is False
    assert reporter.get_allow_sending() is True

    # test allow_sending_globally=False
    reporter.allow_sending_in_thread(None)
    reporter.allow_sending_globally(False)
    assert reporter.get_allow_sending() is False

    with AllowSentryReports(reporter=reporter):
        assert reporter.get_allow_sending() is True

    with AllowSentryReports(value=False, reporter=reporter):
        assert reporter.get_allow_sending() is False
    assert reporter.get_allow_sending() is False


def test_send(reporter):
    assert reporter.send_event(None, None, None) is None

    # test return defaults
    assert reporter.send_event({}, None, None) == {
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

    assert reporter.send_event({'a': 'b'}, post_data, None) == {
        'a': 'b',
        'contexts': {
            'browser': {'name': 'Tribler', 'version': '0.0.0'},
            'reporter': {'_stacktrace': ['some', 'stack'], 'comments': 'comment', 'os.environ': {}, 'sysinfo': None},
        },
        'tags': {'machine': 'x86_64', 'os': 'posix', 'platform': None, 'platform.details': None, 'version': '0.0.0'},
    }

    # test sys_info
    post_data = {"sysinfo": 'key\tvalue\nkey1\tvalue1\n'}

    assert reporter.send_event({}, post_data, None) == {
        'contexts': {
            'browser': {'name': 'Tribler', 'version': None},
            'reporter': {'_stacktrace': [], 'comments': None, 'os.environ': {}, 'sysinfo': None},
        },
        'tags': {'machine': None, 'os': None, 'platform': None, 'platform.details': None, 'version': None},
    }

    sys_info = {'platform': ['darwin'], 'platform.details': ['details'], OS_ENVIRON: ['KEY:VALUE', 'KEY1:VALUE1']}
    assert reporter.send_event({}, None, sys_info) == {
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


def test_before_send(reporter):
    scrubber = SentryScrubber()
    reporter.init('', scrubber)

    # pylint: disable=protected-access

    assert reporter._before_send({}, {}) == {}
    assert reporter._before_send(None, {}) is None
    assert reporter._before_send(None, None) is None

    reporter.allow_sending_in_thread(None)
    reporter.allow_sending_globally(False)
    assert reporter.last_event is None
    assert not reporter.get_allow_sending()

    # check that an event is stored
    assert reporter._before_send({'a': 'b'}, None) is None
    assert reporter.last_event == {'a': 'b'}

    # check an event has been processed
    reporter.allow_sending_globally(True)
    assert reporter.get_allow_sending()
    assert reporter._before_send({'c': 'd'}, None) == {'c': 'd'}
    assert reporter.last_event == {'a': 'b'}

    # check information has been scrubbed
    assert reporter._before_send({'contexts': {'reporter': {'_stacktrace': ['/Users/username/']}}}, None) == {
        'contexts': {'reporter': {'_stacktrace': [f'/Users/{scrubber.placeholder_user}/']}}
    }

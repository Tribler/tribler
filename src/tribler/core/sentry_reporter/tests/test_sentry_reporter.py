from unittest.mock import MagicMock, Mock, patch

import pytest

from tribler.core.sentry_reporter.sentry_reporter import (
    OS_ENVIRON,
    PLATFORM_DETAILS,
    SentryReporter,
    SentryStrategy,
    this_sentry_strategy,
)
from tribler.core.sentry_reporter.sentry_scrubber import SentryScrubber
from tribler.core.utilities.patch_import import patch_import


# pylint: disable=redefined-outer-name, protected-access


@pytest.fixture
def sentry_reporter():
    return SentryReporter()


@patch('tribler.core.sentry_reporter.sentry_reporter.sentry_sdk.init')
def test_init(mocked_init: Mock, sentry_reporter: SentryReporter):
    # test that `init` method set all necessary variables and calls `sentry_sdk.init()`
    sentry_reporter.init(sentry_url='url', release_version='release', scrubber=SentryScrubber(),
                         strategy=SentryStrategy.SEND_SUPPRESSED)
    assert sentry_reporter.scrubber
    assert sentry_reporter.global_strategy == SentryStrategy.SEND_SUPPRESSED
    mocked_init.assert_called_once()


@patch('tribler.core.sentry_reporter.sentry_reporter.ignore_logger')
def test_ignore_logger(mocked_ignore_logger: Mock, sentry_reporter: SentryReporter):
    # test that `ignore_logger` calls `ignore_logger` from sentry_sdk
    sentry_reporter.ignore_logger('logger name')
    mocked_ignore_logger.assert_called_with('logger name')


@patch('tribler.core.sentry_reporter.sentry_reporter.sentry_sdk.add_breadcrumb')
def test_add_breadcrumb(mocked_add_breadcrumb: Mock, sentry_reporter: SentryReporter):
    # test that `add_breadcrumb` passes all necessary arguments to `sentry_sdk`
    assert sentry_reporter.add_breadcrumb('message', 'category', 'level', named_arg='some')
    mocked_add_breadcrumb.assert_called_with({'message': 'message', 'category': 'category', 'level': 'level'},
                                             named_arg='some')


def test_get_confirmation(sentry_reporter: SentryReporter):
    # test that `get_confirmation` calls `QApplication` and `QMessageBox` from `PyQt5.QtWidgets`
    mocked_QApplication = Mock()
    mocked_QMessageBox = MagicMock()

    with patch_import('PyQt5.QtWidgets', strict=True, QApplication=mocked_QApplication, QMessageBox=mocked_QMessageBox):
        sentry_reporter.get_confirmation(Exception('test'))
        mocked_QApplication.assert_called()
        mocked_QMessageBox.assert_called()


@patch_import('PyQt5.QtWidgets', always_raise_exception_on_import=True)
def test_get_confirmation_no_qt(sentry_reporter: SentryReporter):
    assert not sentry_reporter.get_confirmation(Exception('test'))


@patch('tribler.core.sentry_reporter.sentry_reporter.sentry_sdk.capture_exception')
def test_capture_exception(mocked_capture_exception: Mock, sentry_reporter: SentryReporter):
    # test that `capture_exception` passes an exception to `sentry_sdk`
    exception = Exception('test')
    sentry_reporter.capture_exception(exception)
    mocked_capture_exception.assert_called_with(exception)


@patch('tribler.core.sentry_reporter.sentry_reporter.sentry_sdk.capture_exception')
def test_event_from_exception(mocked_capture_exception: Mock, sentry_reporter: SentryReporter):
    # test that `event_from_exception` returns '{}' in case of an empty exception
    assert sentry_reporter.event_from_exception(None) == {}

    # test that `event_from_exception` calls `capture_exception` from `sentry_sdk`
    exception = Exception('test')
    sentry_reporter.thread_strategy = Mock()

    def capture_exception(_):
        # this behaviour normally is way more complicated, but at the end, `capture_exception` should transform
        # the exception to a sentry event and this event should be stored in `sentry_reporter.last_event`
        sentry_reporter.last_event = {'sentry': 'event'}

    mocked_capture_exception.side_effect = capture_exception

    sentry_reporter.event_from_exception(exception)

    mocked_capture_exception.assert_called_with(exception)
    sentry_reporter.thread_strategy.set.assert_any_call(SentryStrategy.SEND_SUPPRESSED)
    assert sentry_reporter.last_event == {'sentry': 'event'}


def test_set_user(sentry_reporter):
    # test that sentry_reporter transforms `user_id` to a fake identity
    assert sentry_reporter.set_user(b'some_id') == {
        'id': 'db69fe66ec6b6b013c2f7d271ce17cae',
        'username': 'Wanda Brown',
    }

    assert sentry_reporter.set_user(b'11111100100') == {
        'id': '91f900f528d5580581197c2c6a4adbbc',
        'username': 'Jennifer Herrera',
    }


def test_get_actual_strategy(sentry_reporter):
    # test that sentry_reporter use `thread_strategy` in case it has been set, and `global_strategy` otherwise
    sentry_reporter.thread_strategy.set(None)
    sentry_reporter.global_strategy = SentryStrategy.SEND_ALLOWED_WITH_CONFIRMATION
    assert sentry_reporter.get_actual_strategy() == SentryStrategy.SEND_ALLOWED_WITH_CONFIRMATION

    sentry_reporter.thread_strategy.set(SentryStrategy.SEND_ALLOWED)
    assert sentry_reporter.get_actual_strategy() == SentryStrategy.SEND_ALLOWED

    sentry_reporter.thread_strategy.set(None)
    assert sentry_reporter.get_actual_strategy() == SentryStrategy.SEND_ALLOWED_WITH_CONFIRMATION


@patch('os.environ', {})
def test_get_sentry_url_not_specified():
    assert not SentryReporter.get_sentry_url()


@patch('tribler.core.version.sentry_url', 'sentry_url')
def test_get_sentry_url_from_version_file():
    assert SentryReporter.get_sentry_url() == 'sentry_url'


@patch('os.environ', {'TRIBLER_SENTRY_URL': 'env_url'})
def test_get_sentry_url_from_env():
    assert SentryReporter.get_sentry_url() == 'env_url'


@patch('os.environ', {})
def test_is_not_in_test_mode():
    assert SentryReporter.get_test_sentry_url() is None
    assert not SentryReporter.is_in_test_mode()


@patch('os.environ', {'TRIBLER_TEST_SENTRY_URL': 'url'})
def test_is_in_test_mode():
    assert SentryReporter.get_test_sentry_url() == 'url'
    assert SentryReporter.is_in_test_mode()


def test_before_send_no_event(sentry_reporter: SentryReporter):
    # test that in case of a None event, `_before_send` will never fail
    assert not sentry_reporter._before_send(None, None)


def test_before_send_ignored_exceptions(sentry_reporter: SentryReporter):
    # test that in case of an ignored exception, `_before_send` will return None
    assert not sentry_reporter._before_send({'some': 'event'}, {'exc_info': [KeyboardInterrupt]})


def test_before_send_suppressed(sentry_reporter: SentryReporter):
    # test that in case of strategy==SentryStrategy.SEND_SUPPRESSED, the event will be stored in `self.last_event`
    sentry_reporter.global_strategy = SentryStrategy.SEND_SUPPRESSED
    assert not sentry_reporter._before_send({'some': 'event'}, None)
    assert sentry_reporter.last_event == {'some': 'event'}


@patch.object(SentryReporter, 'get_confirmation', lambda _, __: True)
def test_before_send_allowed_with_confiration(sentry_reporter: SentryReporter):
    # test that in case of strategy==SentryStrategy.SEND_ALLOWED_WITH_CONFIRMATION, the event will be
    # sent after the positive confirmation
    sentry_reporter.global_strategy = SentryStrategy.SEND_ALLOWED_WITH_CONFIRMATION
    assert sentry_reporter._before_send({'some': 'event'}, None)


def test_before_send_allowed(sentry_reporter: SentryReporter):
    # test that in case of strategy==SentryStrategy.SEND_ALLOWED, the event will be
    # sent without a confirmation
    sentry_reporter.global_strategy = SentryStrategy.SEND_ALLOWED
    assert sentry_reporter._before_send({'some': 'event'}, None)


def test_before_send_scrubber_exists(sentry_reporter: SentryReporter):
    # test that in case of a set scrubber, it will be called for scrubbing an event
    event = {'some': 'event'}

    sentry_reporter.global_strategy = SentryStrategy.SEND_ALLOWED
    sentry_reporter.scrubber = Mock()
    assert sentry_reporter._before_send(event, None)
    sentry_reporter.scrubber.scrub_event.assert_called_with(event)


def test_before_send_scrubber_doesnt_exists(sentry_reporter: SentryReporter):
    # test that in case of a missed scrubber, it will not be called
    sentry_reporter.scrubber = None
    sentry_reporter.global_strategy = SentryStrategy.SEND_ALLOWED
    assert sentry_reporter._before_send({'some': 'event'}, None)


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
            },
        },
        'tags': {'machine': 'x86_64', 'os': 'posix', 'platform': None, PLATFORM_DETAILS: None,
                 'version': '0.0.0'},
    }
    assert actual == expected


def test_send_sys_info(sentry_reporter):
    sys_info = {
        'platform': ['darwin'],
        PLATFORM_DETAILS: ['details'],
        OS_ENVIRON: ['KEY:VALUE', 'KEY1:VALUE1'],
    }
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
            },
        },
        'tags': {'machine': None, 'os': None, 'platform': 'darwin', 'platform.details': 'details',
                 'version': None},
    }
    actual = sentry_reporter.send_event(event={}, sys_info=sys_info)
    assert actual == expected


def test_send_additional_tags(sentry_reporter):
    actual = sentry_reporter.send_event(event={}, additional_tags={'tag_key': 'tag_value', 'numeric_tag_key': 1})
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
            },
        },
        'tags': {
            'machine': None,
            'os': None,
            'platform': None,
            'platform.details': None,
            'version': None,
            'tag_key': 'tag_value',
            'numeric_tag_key': 1,
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
        'contexts': {'reporter': {'_stacktrace': ['/Users/<highlight>/']}}
    }

    # check release
    assert sentry_reporter._before_send({'release': '7.6.0'}, None) == {'release': '7.6.0'}
    assert sentry_reporter._before_send({'release': '7.6.0-GIT'}, None) == {'release': 'dev'}

    # check confirmation
    sentry_reporter.global_strategy = SentryStrategy.SEND_ALLOWED_WITH_CONFIRMATION
    sentry_reporter.get_confirmation = lambda e: False
    assert sentry_reporter._before_send({'a': 'b'}, None) is None

    sentry_reporter.get_confirmation = lambda e: True
    assert sentry_reporter._before_send({'a': 'b'}, None) == {'a': 'b'}


def test_sentry_strategy(sentry_reporter):
    sentry_reporter.thread_strategy.set(None)  # default
    sentry_reporter.global_strategy = SentryStrategy.SEND_ALLOWED_WITH_CONFIRMATION

    with this_sentry_strategy(sentry_reporter, SentryStrategy.SEND_ALLOWED) as reporter:
        assert reporter.global_strategy == SentryStrategy.SEND_ALLOWED_WITH_CONFIRMATION
        assert reporter.thread_strategy.get() == SentryStrategy.SEND_ALLOWED

    assert sentry_reporter.thread_strategy.get() is None
    assert sentry_reporter.global_strategy == SentryStrategy.SEND_ALLOWED_WITH_CONFIRMATION


def test_send_last_core_output(sentry_reporter):
    # Test that the `send_event` function:
    #   1. leaves only the last exception from the given Sentry error
    #   2. removes stacktrace from the last exception from the given Sentry error
    #   3. adds an exception extracted from the "last core output" to the Sentry event
    event = {
        'exception': {
            'values': [
                {
                    'module': 'tribler.gui.utilities',
                    'type': 'CreationTraceback',
                    'value': '\n  File "/Users/<user>/Projects/github.com/Tribler/tribler/src/run_tribler.py", ',
                    'mechanism': None
                },
                {
                    'module': 'tribler.gui.exceptions',
                    'type': 'CoreCrashedError',
                    'value': 'The Tribler core has unexpectedly finished with exit code 1 and status: 0.',
                    'mechanism': None,
                    'stacktrace': {
                        'frames': []
                    }
                }
            ]
        }
    }
    last_core_output = '''
File "/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.8/lib/python3.8/asyncio/base_events.py", line 1461, in create_server
    sock.bind(sa)
OverflowError: bind(): port must be 0-65535.Sentry is attempting to send 1 pending error messages
Waiting up to 2 seconds
Press Ctrl-C to quit
    '''
    actual = sentry_reporter.send_event(event=event, last_core_output=last_core_output)
    expected = {
        'exception': {
            'values': [
                {
                    'module': 'tribler.gui.exceptions',
                    'type': 'CoreCrashedError',
                    'value': 'The Tribler core has unexpectedly finished with exit code 1 and status: 0.',
                    'mechanism': None
                },
                {
                    'type': 'OverflowError',
                    'value': 'bind(): port must be 0-65535.'
                }
            ]
        },
        'contexts': {
            'browser': {'name': 'Tribler', 'version': None},
            'reporter': {
                'last_core_output': last_core_output.split('\n'),
                '_stacktrace': [],
                '_stacktrace_context': [],
                '_stacktrace_extra': [],
                'comments': None,
                OS_ENVIRON: {},
                'sysinfo': {},
            },
        },
        'tags': {'machine': None, 'os': None, 'platform': None, PLATFORM_DETAILS: None, 'version': None},
    }

    assert actual == expected

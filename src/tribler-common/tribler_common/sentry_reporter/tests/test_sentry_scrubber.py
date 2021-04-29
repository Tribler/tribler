import pytest

from tribler_common.sentry_reporter.sentry_reporter import (
    BREADCRUMBS,
    CONTEXTS,
    EXTRA,
    LOGENTRY,
    OS_ENVIRON,
    REPORTER,
    STACKTRACE,
    SYSINFO,
    SYS_ARGV,
)
from tribler_common.sentry_reporter.sentry_scrubber import SentryScrubber


@pytest.fixture(name="scrubber")  # this workaround implemented only for pylint
def fixture_scrubber():
    return SentryScrubber()


def test_patterns(scrubber):
    # folders negative
    assert not any(regex.search('') for regex in scrubber.re_folders)
    assert not any(regex.search('some text') for regex in scrubber.re_folders)
    assert not any(regex.search('/home//some/') for regex in scrubber.re_folders)

    # folders positive
    assert any(regex.search('/home/username/some/') for regex in scrubber.re_folders)
    assert any(regex.search('/usr/local/path/') for regex in scrubber.re_folders)
    assert any(regex.search('/Users/username/some/') for regex in scrubber.re_folders)
    assert any(regex.search('/users/username/some/long_path') for regex in scrubber.re_folders)
    assert any(regex.search('/home/username/some/') for regex in scrubber.re_folders)
    assert any(regex.search('/data/media/username3/some/') for regex in scrubber.re_folders)
    assert any(regex.search('WINNT\\Profiles\\username\\some') for regex in scrubber.re_folders)
    assert any(regex.search('Documents and Settings\\username\\some') for regex in scrubber.re_folders)
    assert any(regex.search('C:\\Users\\Some User\\') for regex in scrubber.re_folders)
    assert any(regex.search('C:\\Users\\USERNAM~1\\') for regex in scrubber.re_folders)

    # ip negative
    assert not scrubber.re_ip.search('0.0.0')
    assert not scrubber.re_ip.search('0.0.0.0.0')
    assert not scrubber.re_ip.search('0.1000.0.1')
    assert not scrubber.re_ip.search('0.a.0.1')
    assert not scrubber.re_ip.search('0123.0.0.1')
    assert not scrubber.re_ip.search('03.0.0.1234')
    assert not scrubber.re_ip.search('a0.0.0.1')

    # ip positive
    assert scrubber.re_ip.search('127.0.0.1')
    assert scrubber.re_ip.search('0.0.0.1')
    assert scrubber.re_ip.search('0.100.0.1')
    assert scrubber.re_ip.search('(0.100.0.1)')

    # hash negative
    assert not scrubber.re_hash.search('0a303030303030303030303030303030303030300')
    assert not scrubber.re_hash.search('0a3030303030303030303303030303030303030')
    assert not scrubber.re_hash.search('z030303030303030303030303030303030303030')

    # hash positive
    assert scrubber.re_hash.search('3030303030303030303030303030303030303030')
    assert scrubber.re_hash.search('0a30303030303030303030303030303030303030')
    assert scrubber.re_hash.search('hash:3030303030303030303030303030303030303030')


def test_scrub_path(scrubber):
    # scrub negative
    assert scrubber.scrub_text('/usr/local/path/') == '/usr/local/path/'
    assert scrubber.scrub_text('some text') == 'some text'

    assert not scrubber.sensitive_occurrences

    # scrub positive

    # this particular example is kinda bug (<<user>>)
    # but it is not really important what placeholder we use
    # hence, let's leave it at that for now.
    assert scrubber.scrub_text('/users/user/apps') == f'/users/{scrubber.placeholder_user}/apps'
    assert 'user' in scrubber.sensitive_occurrences

    assert scrubber.scrub_text('/users/username/some/long_path') == f'/users/{scrubber.placeholder_user}/some/long_path'
    assert 'username' in scrubber.sensitive_occurrences


def test_scrub_text_ip(scrubber):
    # negative
    assert scrubber.scrub_text('127.0.0.1') == '127.0.0.1'
    assert scrubber.scrub_text('0.0.0') == '0.0.0'

    # positive
    assert scrubber.scrub_text('0.0.0.1') == scrubber.placeholder_ip
    assert scrubber.scrub_text('0.100.0.1') == scrubber.placeholder_ip

    assert not scrubber.sensitive_occurrences


def test_scrub_text_hash(scrubber):
    # negative
    assert (
        scrubber.scrub_text('0a303030303030303030303030303030303030300') == '0a303030303030303030303030303030303030300'
    )
    assert scrubber.scrub_text('0a3030303030303030303303030303030303030') == '0a3030303030303030303303030303030303030'

    # positive
    assert scrubber.scrub_text('3030303030303030303030303030303030303030') == scrubber.placeholder_hash
    assert scrubber.scrub_text('hash:3030303030303030303030303030303030303030') == f'hash:{scrubber.placeholder_hash}'

    assert not scrubber.sensitive_occurrences


def test_scrub_text_complex_string(scrubber):
    source = (
        'this is a string that have been sent from '
        '192.168.1.1(3030303030303030303030303030303030303030) '
        'located at usr/someuser/path at '
        'someuser machine(someuserany)'
    )

    actual = scrubber.scrub_text(source)

    assert (
        actual == f'this is a string that have been sent from '
        f'{scrubber.placeholder_ip}({scrubber.placeholder_hash}) '
        f'located at usr/{scrubber.placeholder_user}/path at '
        f'{scrubber.placeholder_user} machine(someuserany)'
    )

    assert 'someuser' in scrubber.sensitive_occurrences
    assert scrubber.scrub_text('someuser') == scrubber.placeholder_user


def test_scrub_simple_event(scrubber):
    assert scrubber.scrub_event(None) is None
    assert scrubber.scrub_event({}) == {}
    assert scrubber.scrub_event({'some': 'field'}) == {'some': 'field'}


def test_scrub_event(scrubber):
    event = {
        'the very first item': 'username',
        CONTEXTS: {
            REPORTER: {
                OS_ENVIRON: {
                    'USERNAME': 'User Name',
                    'PATH': '/users/username/apps',
                    'TMP_WIN': r'C:\Users\USERNAM~1\AppData\Local\Temp',
                    'USERDOMAIN': 'a',
                },
                STACKTRACE: [
                    'Traceback (most recent call last):',
                    'File "/Users/username/Tribler/tribler/src/tribler-gui/tribler_gui/"',
                ],
                SYSINFO: {'sys.path': ['/Users/username/Tribler/', '/Users/username/', '.']},
            }
        },
        EXTRA: {SYS_ARGV: ['/Users/username/Tribler']},
        LOGENTRY: {'message': 'Exception with username', 'params': ['Traceback File: /Users/username/Tribler/']},
        BREADCRUMBS: {
            'values': [
                {'type': 'log', 'message': 'Traceback File: /Users/username/Tribler/', 'timestamp': '1'},
                {'type': 'log', 'message': 'Traceback File: /Users/username/Tribler/', 'timestamp': '1'},
                {'type': 'log', 'message': 'IP: 192.168.1.1', 'timestamp': '2'},
            ]
        },
    }

    assert scrubber.scrub_event(event) == {
        'the very first item': scrubber.placeholder_user,
        CONTEXTS: {
            REPORTER: {
                OS_ENVIRON: {
                    'USERNAME': '<USERNAME>',
                    'PATH': f'/users/{scrubber.placeholder_user}/apps',
                    'TMP_WIN': f'C:\\Users\\{scrubber.placeholder_user}\\AppData\\Local\\Temp',
                    'USERDOMAIN': '<USERDOMAIN>',
                },
                STACKTRACE: [
                    'Traceback (most recent call last):',
                    f'File "/Users/{scrubber.placeholder_user}/Tribler/tribler/src/tribler-gui/tribler_gui/"',
                ],
                SYSINFO: {
                    'sys.path': [
                        f'/Users/{scrubber.placeholder_user}/Tribler/',
                        f'/Users/{scrubber.placeholder_user}/',
                        '.',
                    ]
                },
            },
        },
        LOGENTRY: {
            'message': f'Exception with {scrubber.placeholder_user}',
            'params': [f'Traceback File: /Users/{scrubber.placeholder_user}/Tribler/'],
        },
        EXTRA: {SYS_ARGV: [f'/Users/{scrubber.placeholder_user}/Tribler']},
        BREADCRUMBS: {
            'values': [
                {
                    'type': 'log',
                    'message': f'Traceback File: /Users/{scrubber.placeholder_user}/Tribler/',
                    'timestamp': '1',
                },
                {'type': 'log', 'message': f'IP: {scrubber.placeholder_ip}', 'timestamp': '2'},
            ]
        },
    }


def test_entities_recursively(scrubber):
    # positive
    assert scrubber.scrub_entity_recursively(None) is None
    assert scrubber.scrub_entity_recursively({}) == {}
    assert scrubber.scrub_entity_recursively([]) == []
    assert scrubber.scrub_entity_recursively('') == ''
    assert scrubber.scrub_entity_recursively(42) == 42

    event = {'some': {'value': [{'path': '/Users/username/Tribler'}]}}
    assert scrubber.scrub_entity_recursively(event) == {
        'some': {'value': [{'path': f'/Users/{scrubber.placeholder_user}/Tribler'}]}
    }
    # stop on depth

    assert scrubber.scrub_entity_recursively(event) != event
    assert scrubber.scrub_entity_recursively(event, depth=2) == event


def test_scrub_unnecessary_fields(scrubber):
    # default
    assert scrubber.scrub_event({'default': 'field'}) == {'default': 'field'}

    # custom
    custom_scrubber = SentryScrubber()
    custom_scrubber.event_fields_to_cut = ['new', 'default']
    assert custom_scrubber.scrub_event({'default': 'event', 'new': 'field', 'modules': {}}) == {'modules': {}}


def test_scrub_text_none(scrubber):
    assert scrubber.scrub_text(None) is None


def test_scrub_some_text(scrubber):
    assert scrubber.scrub_text('some text') == 'some text'
    assert not scrubber.sensitive_occurrences


def test_scrub_dict(scrubber):
    assert scrubber.scrub_entity_recursively(None) is None
    assert scrubber.scrub_entity_recursively({}) == {}

    assert scrubber.scrub_entity_recursively(
        {'PATH': '/home/username/some/', 'USERDOMAIN': 'UD', 'USERNAME': 'U', 'REPEATED': 'user username UD U'}
    ) == {
        'PATH': f'/home/{scrubber.placeholder_user}/some/',
        'USERDOMAIN': '<USERDOMAIN>',
        'USERNAME': '<USERNAME>',
        'REPEATED': f'user {scrubber.placeholder_user} <USERDOMAIN> <USERNAME>',
    }

    assert 'username' in scrubber.sensitive_occurrences.keys()
    assert 'UD' in scrubber.sensitive_occurrences.keys()
    assert 'U' in scrubber.sensitive_occurrences.keys()


def test_scrub_list(scrubber):
    assert scrubber.scrub_entity_recursively(None) is None
    assert scrubber.scrub_entity_recursively([]) == []

    assert scrubber.scrub_entity_recursively(['/home/username/some/']) == [f'/home/{scrubber.placeholder_user}/some/']
    assert 'username' in scrubber.sensitive_occurrences

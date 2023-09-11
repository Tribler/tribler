import pytest

from tribler.core.sentry_reporter.sentry_reporter import (
    BREADCRUMBS,
    CONTEXTS,
    EXTRA,
    LOGENTRY,
    REPORTER,
    STACKTRACE,
    SYSINFO,
    SYS_ARGV,
)
from tribler.core.sentry_reporter.sentry_scrubber import SentryScrubber


# pylint: disable=redefined-outer-name
@pytest.fixture
def scrubber():
    return SentryScrubber()


FOLDERS_POSITIVE_MATCH = [
    '/home/username/some/',
    '/usr/local/path/',
    '/Users/username/some/',
    '/users/username/some/long_path',
    '/home/username/some/',
    '/data/media/username3/some/',
    'WINNT\\Profiles\\username\\some',
    'Documents and Settings\\username\\some',
    'C:\\Users\\Some User\\',
    'C:\\Users\\USERNAM~1\\',

    # double slashes (could be present as errors during a serialisation)
    'C:\\\\Users\\\\username\\\\',
    '//home//username//some//',

]

FOLDERS_NEGATIVE_MATCH = [
    '',
    'any text',
    '/home//some/',
]


@pytest.mark.parametrize('folder', FOLDERS_NEGATIVE_MATCH)
def test_patterns_folders_negative_match(folder: str, scrubber: SentryScrubber):
    """ Test that the scrubber does not match folders """
    assert not any(regex.search(folder) for regex in scrubber.re_folders)


@pytest.mark.parametrize('folder', FOLDERS_POSITIVE_MATCH)
def test_patterns_folders_positive_match(folder: str, scrubber: SentryScrubber):
    """ Test that the scrubber matches folders """
    assert any(regex.search(folder) for regex in scrubber.re_folders)


IP_POSITIVE_MATCH = [
    '127.0.0.1',
    '0.0.0.1',
    '0.100.0.1',
    '(0.100.0.1)'
]

IP_NEGATIVE_MATCH = [
    '0.0.0',
    '0.0.0.0.0',
    '0.1000.0.1',
    '0.a.0.1',
    '0123.0.0.1',
    '03.0.0.1234',
    'a0.0.0.1',
]


@pytest.mark.parametrize('ip', IP_NEGATIVE_MATCH)
def test_patterns_ip_negative_match(ip: str, scrubber: SentryScrubber):
    """ Test that the scrubber does not match IPs """
    assert not scrubber.re_ip.search(ip)


@pytest.mark.parametrize('ip', IP_POSITIVE_MATCH)
def test_patterns_ip_positive_match(ip: str, scrubber: SentryScrubber):
    """ Test that the scrubber matches IPs """
    assert scrubber.re_ip.search(ip)


HASH_POSITIVE_MATCH = [
    '3030303030303030303030303030303030303030',
    '0a30303030303030303030303030303030303030',
    'hash:3030303030303030303030303030303030303030'
]

HASH_NEGATIVE_MATCH = [
    '0a303030303030303030303030303030303030300',
    '0a3030303030303030303303030303030303030',
    'z030303030303030303030303030303030303030'
]


@pytest.mark.parametrize('h', HASH_NEGATIVE_MATCH)
def test_patterns_hash_negative_match(h: str, scrubber: SentryScrubber):
    """ Test that the scrubber does not match hashes """
    assert not scrubber.re_hash.search(h)


@pytest.mark.parametrize('h', HASH_POSITIVE_MATCH)
def test_patterns_hash_positive_match(h: str, scrubber: SentryScrubber):
    """ Test that the scrubber scrub hashes """
    assert scrubber.re_hash.search(h)


def test_scrub_path_negative_match(scrubber: SentryScrubber):
    """ Test that the scrubber does not scrub paths """
    assert scrubber.scrub_text('/usr/local/path/') == '/usr/local/path/'
    assert scrubber.scrub_text('some text') == 'some text'

    assert not scrubber.sensitive_occurrences


def test_scrub_path_positive_match(scrubber: SentryScrubber):
    """ Test that the scrubber scrubs paths """
    assert scrubber.scrub_text('/users/user/apps') == '/users/<boot>/apps'
    assert 'user' in scrubber.sensitive_occurrences

    assert scrubber.scrub_text('/users/username/some/long_path') == '/users/<highlight>/some/long_path'
    assert 'username' in scrubber.sensitive_occurrences


def test_scrub_text_ip_negative_match(scrubber: SentryScrubber):
    """ Test that the scrubber does not scrub IPs """
    assert scrubber.scrub_text('127.0.0.1') == '127.0.0.1'
    assert scrubber.scrub_text('0.0.0') == '0.0.0'


def test_scrub_text_ip_positive_match(scrubber: SentryScrubber):
    """ Test that the scrubber scrubs IPs """
    assert scrubber.scrub_text('0.0.0.1') == '<IP>'
    assert scrubber.scrub_text('0.100.0.1') == '<IP>'

    assert not scrubber.sensitive_occurrences


def test_scrub_text_hash_negative_match(scrubber: SentryScrubber):
    """ Test that the scrubber does not scrub hashes """
    too_long_hash = '1' * 41
    assert scrubber.scrub_text(too_long_hash) == too_long_hash
    too_short_hash = '2' * 39
    assert scrubber.scrub_text(too_short_hash) == too_short_hash


def test_scrub_text_hash_positive_match(scrubber: SentryScrubber):
    """ Test that the scrubber scrubs hashes """
    assert scrubber.scrub_text('3' * 40) == '<hash>'
    assert scrubber.scrub_text('hash:' + '4' * 40) == 'hash:<hash>'

    assert not scrubber.sensitive_occurrences


def test_scrub_text_complex_string(scrubber):
    """ Test that the scrubber scrubs complex strings """
    source = (
        'this is a string that has been sent from '
        '192.168.1.1(3030303030303030303030303030303030303030) '
        'located at usr/someuser/path on '
        "someuser's machine(someuser_with_postfix)"
    )

    actual = scrubber.scrub_text(source)

    assert actual == ('this is a string that has been sent from '
                      '<IP>(<hash>) '
                      'located at usr/<effect>/path on '
                      "<effect>'s machine(someuser_with_postfix)")

    assert 'someuser' in scrubber.sensitive_occurrences
    assert scrubber.scrub_text('someuser') == '<effect>'


def test_scrub_simple_event(scrubber):
    """ Test that the scrubber scrubs simple events """
    assert scrubber.scrub_event(None) is None
    assert scrubber.scrub_event({}) == {}
    assert scrubber.scrub_event({'some': 'field'}) == {'some': 'field'}


def test_scrub_event(scrubber):
    """ Test that the scrubber scrubs events """
    event = {
        'the very first item': 'username',
        'server_name': 'userhost',
        CONTEXTS: {
            REPORTER: {
                'any': {
                    'USERNAME': 'User Name',
                    'USERDOMAIN_ROAMINGPROFILE': 'userhost',
                    'PATH': '/users/username/apps',
                    'TMP_WIN': r'C:\Users\USERNAM~1\AppData\Local\Temp',
                    'USERDOMAIN': ' USER-DOMAIN',  # it is a corner case when there is a space before a text
                    'COMPUTERNAME': 'Computer name',
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
                {'type': 'log', 'message': 'IP: 192.168.1.1', 'timestamp': '2'},
            ]
        },
    }
    assert scrubber.scrub_event(event) == {
        'the very first item': '<highlight>',
        'server_name': '<protection>',
        CONTEXTS: {
            REPORTER: {
                'any': {
                    'USERNAME': '<father>',
                    'USERDOMAIN_ROAMINGPROFILE': '<protection>',
                    'PATH': '/users/<highlight>/apps',
                    'TMP_WIN': 'C:\\Users\\<restaurant>\\AppData\\Local\\Temp',
                    'USERDOMAIN': '<marriage>',
                    'COMPUTERNAME': '<message>',
                },
                STACKTRACE: [
                    'Traceback (most recent call last):',
                    'File "/Users/<highlight>/Tribler/tribler/src/tribler-gui/tribler_gui/"',
                ],
                SYSINFO: {
                    'sys.path': [
                        '/Users/<highlight>/Tribler/',
                        '/Users/<highlight>/',
                        '.',
                    ]
                },
            },
        },
        LOGENTRY: {
            'message': 'Exception with <highlight>',
            'params': ['Traceback File: /Users/<highlight>/Tribler/'],
        },
        EXTRA: {SYS_ARGV: ['/Users/<highlight>/Tribler']},
        BREADCRUMBS: {
            'values': [
                {
                    'type': 'log',
                    'message': 'Traceback File: /Users/<highlight>/Tribler/',
                    'timestamp': '1',
                },
                {'type': 'log', 'message': 'IP: <IP>', 'timestamp': '2'},
            ]
        },
    }


def test_entities_recursively(scrubber):
    """ Test that the scrubber scrubs entities recursively """

    # positive
    assert scrubber.scrub_entity_recursively(None) is None
    assert scrubber.scrub_entity_recursively({}) == {}
    assert scrubber.scrub_entity_recursively([]) == []
    assert scrubber.scrub_entity_recursively('') == ''
    assert scrubber.scrub_entity_recursively(42) == 42

    event = {
        'some': {
            'value': [
                {
                    'path': '/Users/username/Tribler'
                }
            ]
        }
    }
    assert scrubber.scrub_entity_recursively(event) == {
        'some': {'value': [{'path': '/Users/<highlight>/Tribler'}]}
    }
    # stop on depth
    assert scrubber.scrub_entity_recursively(event) != event
    assert scrubber.scrub_entity_recursively(event, depth=2) == event


def test_scrub_unnecessary_fields(scrubber):
    """ Test that the scrubber scrubs unnecessary fields """
    # default
    assert scrubber.scrub_event({'default': 'field'}) == {'default': 'field'}

    # custom
    custom_scrubber = SentryScrubber()
    custom_scrubber.event_fields_to_cut = ['new', 'default']
    assert custom_scrubber.scrub_event({'default': 'event', 'new': 'field', 'modules': {}}) == {'modules': {}}


def test_scrub_text_none(scrubber):
    assert scrubber.scrub_text(None) is None


def test_scrub_dict(scrubber):
    assert scrubber.scrub_entity_recursively(None) is None
    assert scrubber.scrub_entity_recursively({}) == {}

    given = {'PATH': '/home/username/some/', 'USERDOMAIN': 'UD', 'USERNAME': 'U', 'REPEATED': 'user username UD U'}
    assert scrubber.scrub_entity_recursively(given) == {'PATH': '/home/<highlight>/some/',
                                                        'REPEATED': 'user <highlight> <school> <night>',
                                                        'USERDOMAIN': '<school>',
                                                        'USERNAME': '<night>'}

    assert 'username' in scrubber.sensitive_occurrences.keys()
    assert 'UD' in scrubber.sensitive_occurrences.keys()
    assert 'U' in scrubber.sensitive_occurrences.keys()


def test_scrub_list(scrubber):
    assert scrubber.scrub_entity_recursively(None) is None
    assert scrubber.scrub_entity_recursively([]) == []

    assert scrubber.scrub_entity_recursively(['/home/username/some/']) == ['/home/<highlight>/some/']
    assert 'username' in scrubber.sensitive_occurrences


def test_remove_breadcrumbs():
    """ Test that the function `SentryScrubber.remove_breadcrumbs` removes breadcrumbs from a dictionary """
    event = {
        BREADCRUMBS: {
            'values': [
                {'type': 'log', 'message': 'Traceback File: /Users/username/Tribler/', 'timestamp': '1'},
                {'type': 'log', 'message': 'Traceback File: /Users/username/Tribler/', 'timestamp': '1'},
                {'type': 'log', 'message': 'IP: 192.168.1.1', 'timestamp': '2'},
            ]
        },
        'key': 'value'
    }

    assert SentryScrubber.remove_breadcrumbs(event) == {'key': 'value'}

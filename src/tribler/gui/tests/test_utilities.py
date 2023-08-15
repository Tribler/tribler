import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from urllib.parse import unquote_plus

import pytest

from tribler.gui.utilities import TranslatedString, compose_magnetlink, create_api_key, dict_item_is_any_of, \
    duration_to_string, format_api_key, get_i18n_file_path, get_languages_file_content, I18N_DIR, LANGUAGES_FILE, \
    quote_plus_unicode, set_api_key, unicode_quoter


def test_quoter_char():
    """
    Test if an ASCII character is quoted correctly
    """
    char = 'A'

    encoded = unicode_quoter(char)

    assert char == unquote_plus(encoded)


def test_quoter_unichar():
    """
    Test if a unicode character is quoted correctly
    """
    char = '\u9b54'

    encoded = unicode_quoter(char)

    assert char == unquote_plus(encoded)


def test_quoter_reserved():
    """
    Test if a URI reserved character is quoted correctly
    """
    char = '+'

    encoded = unicode_quoter(char)

    assert char != encoded
    assert char == unquote_plus(encoded)


def test_quote_plus_unicode_char():
    """
    Test if a ASCII characters are quoted correctly
    """
    s = 'Ab09'

    encoded = quote_plus_unicode(s)

    assert s == unquote_plus(encoded)


def test_quote_plus_unicode_unichar():
    """
    Test if unicode characters are quoted correctly
    """
    s = '\u9b54\u11b3\uaf92\u1111'

    encoded = quote_plus_unicode(s)

    assert s == unquote_plus(encoded)


def test_quote_plus_unicode_reserved():
    """
    Test if a URI reserved characters are quoted correctly
    """
    s = '+ &'

    encoded = quote_plus_unicode(s)

    assert s != encoded
    assert s == unquote_plus(encoded)


def test_quote_plus_unicode_compound():
    """
    Test if a jumble of unicode, reserved and normal chars are quoted correctly
    """
    s = '\u9b54\u11b3+ A5&\uaf92\u1111'

    encoded = quote_plus_unicode(s)

    assert s != encoded
    assert s == unquote_plus(encoded)


def test_compose_magnetlink():
    infohash = "DC4B96CF85A85CEEDB8ADC4B96CF85A85CEEDB8A"
    name = "Some torrent name"
    trackers = ['http://tracker1.example.com:8080/announce', 'http://tracker1.example.com:8080/announce']

    expected_link0 = ""
    expected_link1 = "magnet:?xt=urn:btih:DC4B96CF85A85CEEDB8ADC4B96CF85A85CEEDB8A"
    expected_link2 = "magnet:?xt=urn:btih:DC4B96CF85A85CEEDB8ADC4B96CF85A85CEEDB8A&dn=Some+torrent+name"
    expected_link3 = (
        "magnet:?xt=urn:btih:DC4B96CF85A85CEEDB8ADC4B96CF85A85CEEDB8A&dn=Some+torrent+name"
        "&tr=http://tracker1.example.com:8080/announce&tr=http://tracker1.example.com:8080/announce"
    )

    composed_link0 = compose_magnetlink(None)
    composed_link1 = compose_magnetlink(infohash)
    composed_link2 = compose_magnetlink(infohash, name=name)
    composed_link3 = compose_magnetlink(infohash, name=name, trackers=trackers)

    assert composed_link0 == expected_link0
    assert composed_link1 == expected_link1
    assert composed_link2 == expected_link2
    assert composed_link3 == expected_link3


def test_is_dict_has():
    assert not dict_item_is_any_of(None, None, None)
    assert not dict_item_is_any_of({}, None, None)

    d = {
        'k': 'v',
        'k1': 'v1'
    }

    assert not dict_item_is_any_of(d, 'missed_key', None)
    assert not dict_item_is_any_of(d, 'missed_key', ['any_value'])
    assert not dict_item_is_any_of(d, 'k', ['missed_value'])
    assert not dict_item_is_any_of(d, 'k', ['missed_value', 'missed_value1'])

    assert dict_item_is_any_of(d, 'k', ['v'])
    assert dict_item_is_any_of(d, 'k', ['v', 'a'])
    assert dict_item_is_any_of(d, 'k', ['a', 'v'])


def test_create_api_key():
    x = create_api_key()
    assert len(x) == 32 and bytes.fromhex(x).hex() == x


def test_format_api_key():
    api_key = "abcdef"
    x = format_api_key(api_key)
    assert x == "abcdef"

    api_key = b"abcdef"
    x = format_api_key(api_key)
    assert x == "abcdef"

    api_key = 123
    match_str = r"^Got unexpected value type of api_key from gui settings \(should be str or bytes\): int$"
    with pytest.raises(ValueError, match=match_str):
        format_api_key(api_key)


def test_set_api_key():
    gui_settings = MagicMock()
    set_api_key(gui_settings, "abcdef")
    gui_settings.setValue.assert_called_once_with("api_key", b"abcdef")


TRANSLATIONS = [
    (0, '0s'),
    (61, '1m 1s'),
    (3800, '1h 3m'),
    (110000, '1d 6h'),
    (1110000, '1w 5d'),
    (91110000, '2y 46w'),
    (11191110000, 'Forever'),
]


@pytest.mark.parametrize('seconds, translation', TRANSLATIONS)
@patch('tribler.gui.utilities.tr', new=Mock(side_effect=lambda x: x))
def test_duration_to_string(seconds, translation):
    # test if the duration_to_string function returns the correct translation for all possible formats
    assert duration_to_string(seconds) == translation


def test_correct_translation():
    original_string = 'original %(key1)s'
    translated_string = 'translated %(key1)s'
    s = TranslatedString(translated_string, original_string)
    assert s % {'key1': '123'} == 'translated 123'


@patch('tribler.gui.utilities.logger.warning')
def test_missed_key_in_translated_string(warning: Mock):
    original_string = 'original %(key1)s'
    translated_string = 'translated %(key2)s'
    s = TranslatedString(translated_string, original_string)

    # In this test, we pass the correct param 'key1' presented in the original string but missed in the translation.
    # The KeyError is intercepted, the original string is used instead of the translation, and the error is logged
    # as a warning.
    assert s % {'key1': '123'} == 'original 123'

    warning.assert_called_once_with('KeyError: No value provided for \'key2\' in translation "translated %(key2)s", '
                                    'original string: "original %(key1)s"')


@patch('tribler.gui.utilities.logger.warning')
def test_missed_key_in_both_translated_and_original_strings(warning: Mock):
    original_string = 'original %(key1)s'
    translated_string = 'translated %(key2)s'
    s = TranslatedString(translated_string, original_string)

    with pytest.raises(KeyError, match=r"^'key1'$"):
        # In this test, we pass an incorrect param 'key3' for interpolation, and also, the translation
        # string (with param 'key2') differs from the original string (with param 'key1'). First,
        # translated string tries to interpolate params and issues a warning that 'key2' is missed.
        # Then, the original string tries to interpolate params and again gets a KeyError because 'key1'
        # is also missed. This second exception is propagated because the main reason for the error is
        # in the outside code that passes an incorrect parameter.
        _ = s % {'key3': '123'}

    warning.assert_called_once_with('KeyError: No value provided for \'key2\' in translation "translated %(key2)s", '
                                    'original string: "original %(key1)s"')


@patch("tribler.gui.utilities.get_base_path")
def test_i18n_file_path_and_languages_content(mock_get_base_path, tmp_path):
    mock_get_base_path.return_value = tmp_path

    filename = "languages.json"
    expected_path = Path(tmp_path) / I18N_DIR / filename

    assert get_i18n_file_path(filename) == expected_path

    languages_json = {
        "unknown": "Unknown",
        "en": "English",
        "nl": "Dutch"
    }

    language_path = get_i18n_file_path(LANGUAGES_FILE)
    language_path.parents[0].mkdir(parents=True, exist_ok=True)
    language_path.write_text(json.dumps(languages_json))

    assert languages_json == get_languages_file_content()

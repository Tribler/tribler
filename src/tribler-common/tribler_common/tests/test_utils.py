from pathlib import Path
from unittest.mock import MagicMock, patch

from tribler_common.patch_import import patch_import
from tribler_common.utilities import (
    Query,
    extract_plain_fts_query_text,
    extract_tags,
    parse_query,
    show_system_popup,
    to_fts_query,
    uri_to_path,
)

# pylint: disable=import-outside-toplevel, import-error
# fmt: off

def test_uri_to_path():
    path = Path(__file__).parent / "bla%20foo.bar"
    uri = path.as_uri()
    assert uri_to_path(uri) == path


def test_to_fts_query():
    assert to_fts_query(None) is None
    assert to_fts_query('') is None
    assert to_fts_query('   ') is None
    assert to_fts_query('  abc') == '"abc"*'
    assert to_fts_query('abc def') == '"abc" "def"*'
    assert to_fts_query('[abc, def]: xyz?!') == '"abc" "def" "xyz"*'


def test_extract_tags():
    assert extract_tags('') == (set(), '')
    assert extract_tags('text') == (set(), '')
    assert extract_tags('[text') == (set(), '')
    assert extract_tags('text]') == (set(), '')
    assert extract_tags('[]') == (set(), '')
    assert extract_tags('[ta]') == (set(), '')
    assert extract_tags('[' + 't' * 51 + ']') == (set(), '')
    assert extract_tags('[tag1[tag2]text]') == (set(), '')
    assert extract_tags('[not a tag]') == (set(), '')

    assert extract_tags('[tag]') == ({'tag'}, '[tag]')
    assert extract_tags('[tag1][tag2]') == ({'tag1', 'tag2'}, '[tag1][tag2]')
    assert extract_tags('[tag_with_underscore][tag-with-dash]') == ({'tag_with_underscore', 'tag-with-dash'},
                                                                    '[tag_with_underscore][tag-with-dash]')

    assert extract_tags(' [tag][not tag]for complex query with [not tag at the end]') == ({'tag'}, ' [tag]')


def test_extract_plain_fts_query_text():
    assert not extract_plain_fts_query_text('', '')
    assert extract_plain_fts_query_text('query', '') == 'query'
    assert extract_plain_fts_query_text('[tag] query', '[tag]') == 'query'


def test_parse_query():
    assert parse_query('') == Query(original_query='')

    actual = parse_query('[tag1][tag2]')
    expected = Query(original_query='[tag1][tag2]', tags={'tag1', 'tag2'})
    assert actual == expected

    actual = parse_query('fts query  with potential [brackets]')
    expected = Query(original_query='fts query  with potential [brackets]',
                     fts_text='fts query  with potential [brackets]')
    assert actual == expected

    actual = parse_query('[tag1][tag2] fts query with potential [brackets]')
    expected = Query(original_query='[tag1][tag2] fts query with potential [brackets]',
                     tags={'tag1', 'tag2'},
                     fts_text='fts query with potential [brackets]', )
    assert actual == expected


@patch_import(modules=['win32api'], MessageBox=MagicMock())
@patch('platform.system', new=MagicMock(return_value='Windows'))
@patch('tribler_common.utilities.print', new=MagicMock)
def test_show_system_popup_win():
    # in this test "double mocking techniques" has been applied
    # there are different mocks that will work depending on the target machine's OS
    #
    # In case of *nix machine, "@patch_import(modules=['win32api'], MessageBox=MagicMock())" will work.
    # In case of win machine, "with patch('win32api.MessageBox'):" will work.
    #
    # No matter what kind of Mock was used, the line "win32api.MessageBox.assert_called_once()" should work.
    #
    # This approach also applies to the test functions below.

    import win32api

    with patch('win32api.MessageBox'):  # this patch starts to work only in case win32api exists on the target machine
        show_system_popup('title', 'text')
        win32api.MessageBox.assert_called_once_with(0, 'text', 'title')


@patch_import(modules=['subprocess'], Popen=MagicMock())
@patch('platform.system', new=MagicMock(return_value='Linux'))
@patch('tribler_common.utilities.print', new=MagicMock)
def test_show_system_popup_linux():
    import subprocess

    with patch('subprocess.Popen'):
        show_system_popup('title', 'text')
        subprocess.Popen.assert_called_once_with(['xmessage', '-center', 'text'])


@patch_import(modules=['subprocess'], Popen=MagicMock())
@patch('platform.system', new=MagicMock(return_value='Darwin'))
@patch('tribler_common.utilities.print', new=MagicMock)
def test_show_system_popup_darwin():
    import subprocess

    with patch('subprocess.Popen'):
        show_system_popup('title', 'text')
        subprocess.Popen.assert_called_once_with(['/usr/bin/osascript', '-e', 'text'])


@patch('platform.system', new=MagicMock(return_value='Unknown'))
@patch('tribler_common.utilities.print')
def test_show_system_popup_unknown(mocked_print):
    show_system_popup('title', 'text')
    mocked_print.assert_called_with('cannot create native pop-up for system Unknown')


@patch_import(modules=['subprocess'], Popen=MagicMock(side_effect=ValueError))
@patch('platform.system', new=MagicMock(return_value='Darwin'))
@patch('tribler_common.utilities.print')
def test_show_system_popup_exception(mocked_print):
    with patch('subprocess.Popen', new=MagicMock(side_effect=ValueError)):
        show_system_popup('title', 'text')
    last_call_args = mocked_print.call_args_list[-1]
    last_argument = last_call_args.args[0]
    assert last_argument.startswith('Error while')

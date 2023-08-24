import binascii
from unittest.mock import MagicMock, Mock, patch

import pytest
from aiohttp import ClientSession, web

from tribler.core.logger.logger import load_logger_config
from tribler.core.utilities.patch_import import patch_import
from tribler.core.utilities.tracker_utils import add_url_params
from tribler.core.utilities.utilities import (Query, extract_tags, get_normally_distributed_positive_integers,
                                              is_channel_public_key,
                                              is_infohash, is_simple_match_query, is_valid_url, parse_magnetlink,
                                              parse_query, parse_bool, random_infohash, show_system_popup, to_fts_query)


# pylint: disable=import-outside-toplevel, import-error, redefined-outer-name
# fmt: off

@pytest.fixture
async def magnet_redirect_server(free_port):
    """
    Return a HTTP redirect server that redirects to a magnet.
    """
    magnet_link = "magnet:?xt=urn:btih:DC4B96CF85A85CEEDB8ADC4B96CF85A85CEEDB8A"

    async def redirect_handler(_):
        return web.HTTPFound(magnet_link)

    app = web.Application()
    app.add_routes([web.get('/', redirect_handler)])
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    http_server = web.TCPSite(runner, 'localhost', free_port)
    await http_server.start()
    yield free_port
    await http_server.stop()


def test_parse_magnetlink_lowercase():
    """
    Test if a lowercase magnet link can be parsed
    """
    _, hashed, _ = parse_magnetlink('magnet:?xt=urn:btih:apctqfwnowubxzoidazgaj2ba6fs6juc')

    assert hashed == b"\x03\xc58\x16\xcdu\xa8\x1b\xe5\xc8\x182`'A\x07\x8b/&\x82"


def test_parse_magnetlink_uppercase():
    """
    Test if an uppercase magnet link can be parsed
    """
    _, hashed, _ = parse_magnetlink('magnet:?xt=urn:btih:APCTQFWNOWUBXZOIDAZGAJ2BA6FS6JUC')

    assert hashed == b"\x03\xc58\x16\xcdu\xa8\x1b\xe5\xc8\x182`'A\x07\x8b/&\x82"


def test_parse_invalid_magnetlink_short():
    """
    Test if a magnet link with invalid and short infohash (v1) can be parsed
    """
    _, hashed, _ = parse_magnetlink('magnet:?xt=urn:btih:APCTQFWNOWUBXZOIDA')

    assert hashed is None


def test_parse_invalid_magnetlink_long():
    """
    Test if a magnet link with invalid and long infohash (v1) can be parsed
    """
    _, hashed, _ = parse_magnetlink(
        'magnet:?xt=urn:btih:APCTQFWNOWUBXZOIDAZGAJ2BA6FS6JUCAPCTQFWNOWUBXZOIDAZGAJ2BA6FS6JUC')

    assert hashed is None


def test_valid_url():
    """ Test if the URL is valid """
    test_url = "http://anno nce.torrentsmd.com:8080/announce"
    assert not is_valid_url(test_url)

    test_url2 = "http://announce.torrentsmd.com:8080/announce "
    assert is_valid_url(test_url2)

    test_url3 = "http://localhost:1920/announce"
    assert is_valid_url(test_url3)

    test_url4 = "udp://localhost:1264"
    assert is_valid_url(test_url4)


async def test_http_get_with_redirect(magnet_redirect_server):
    """
    Test if http_get is working properly if url redirects to a magnet link.
    """
    # Setup a redirect server which redirects to a magnet link
    magnet_link = "magnet:?xt=urn:btih:DC4B96CF85A85CEEDB8ADC4B96CF85A85CEEDB8A"

    test_url = "http://localhost:%d" % magnet_redirect_server
    async with ClientSession() as session:
        response = await session.get(test_url, allow_redirects=False)
    assert response.headers['Location'] == magnet_link


def test_simple_search_query():
    query = '"\xc1ubuntu"* AND "debian"*'
    assert is_simple_match_query(query)

    query = '""* AND "Petersburg"*'
    assert not is_simple_match_query(query)

    query2 = '"\xc1ubuntu"* OR "debian"*'
    assert not is_simple_match_query(query2)


def test_is_infohash():
    hex_40 = "DC4B96CF85A85CEEDB8ADC4B96CF85A85CEEDB8A"
    assert is_infohash(hex_40)

    hex_not_40 = "DC4B96CF85A85CEEDB8ADC4B96CF85"
    assert not is_infohash(hex_not_40)

    not_hex = "APPLE6CF85A85CEEDB8ADC4B96CF85A85CEEDB8A"
    assert not is_infohash(not_hex)


def test_is_channel_public_key():
    hex_128 = "224b20c30b90d0fc7b2cf844f3d651de4481e21c7cdbbff258fa737d117d2c4ac7536de5cc93f4e9d5" \
              "1012a1ae0c46e9a05505bd017f0ecb78d8eec4506e848a"
    assert is_channel_public_key(hex_128)

    hex_not_128 = "DC4B96CF85A85CEEDB8ADC4B96CF85"
    assert not is_channel_public_key(hex_not_128)

    not_hex = "APPLE6CF85A85CEEDB8ADC4B96CF85A85CEEDB8A"
    assert not is_channel_public_key(not_hex)


def test_random_infohash():
    test_infohash = random_infohash()
    assert isinstance(test_infohash, bytes)
    assert len(test_infohash) == 20


def test_to_fts_query():
    assert to_fts_query(None) is None
    assert to_fts_query('') is None
    assert to_fts_query('   ') is None
    assert to_fts_query('  abc') == '"abc"'
    assert to_fts_query('abc def') == '"abc" "def"'
    assert to_fts_query('[abc, def]: xyz?!') == '"abc" "def" "xyz"'


def test_extract_tags():
    assert extract_tags('') == (set(), '')
    assert extract_tags('text') == (set(), 'text')
    assert extract_tags('#') == (set(), '#')
    assert extract_tags('# ') == (set(), '# ')
    assert extract_tags('#t ') == (set(), '#t ')
    assert extract_tags('#' + 't' * 51) == (set(), '#' + 't' * 51)
    assert extract_tags('####') == (set(), '####')

    assert extract_tags('#tag') == ({'tag'}, '')
    assert extract_tags('#Tag') == ({'tag'}, '')
    assert extract_tags('a #tag in the middle') == ({'tag'}, 'a  in the middle')
    assert extract_tags('at the end of the query #tag') == ({'tag'}, 'at the end of the query ')
    assert extract_tags('multiple tags: #tag1 #tag2#tag3') == ({'tag1', 'tag2', 'tag3'}, 'multiple tags:  ')
    assert extract_tags('#tag_with_underscores #tag-with-dashes') == ({'tag_with_underscores', 'tag-with-dashes'}, ' ')


def test_parse_query():
    assert parse_query('') == Query(original_query='')

    actual = parse_query('#tag1 #tag2')
    expected = Query(original_query='#tag1 #tag2', tags={'tag1', 'tag2'}, fts_text='')
    assert actual == expected

    actual = parse_query('query without tags')
    expected = Query(original_query='query without tags',
                     tags=set(),
                     fts_text='query without tags')
    assert actual == expected

    actual = parse_query('query with #tag1 and #tag2')
    expected = Query(original_query='query with #tag1 and #tag2',
                     tags={'tag1', 'tag2'},
                     fts_text='query with  and')
    assert actual == expected


def test_parse_bool():
    assert not parse_bool('')
    assert not parse_bool('false')
    assert not parse_bool('False')
    assert not parse_bool('0')
    assert not parse_bool(0)
    assert not parse_bool(False)
    assert parse_bool('true')
    assert parse_bool('True')
    assert parse_bool('1')
    assert parse_bool('-1')
    assert parse_bool(1)
    assert parse_bool(True)


@patch_import(modules=['win32api'], MessageBox=MagicMock())
@patch('platform.system', new=MagicMock(return_value='Windows'))
@patch('tribler.core.utilities.utilities.print', new=MagicMock)
def test_show_system_popup_win():
    # in this test "double mocking techniques" has been applied
    # there are different mocks that will work depending on the target machine's OS
    #
    # In case of *nix machine, "@patch_import(modules=['win32api'], MessageBox=MagicMock())" will work.
    # In case of win machine, "with patch('win32api.MessageBox'):" will work.
    #
    # No matter what kind of Mock was used, the line "win32api.MessageBox.assert_called_with()" should work.
    #
    # This approach also applies to the test functions below.

    import win32api

    with patch('win32api.MessageBox'):  # this patch starts to work only in case win32api exists on the target machine
        show_system_popup('title', 'text')
        win32api.MessageBox.assert_called_with(0, 'text', 'title')


@patch_import(modules=['subprocess'], Popen=MagicMock())
@patch('platform.system', new=MagicMock(return_value='Linux'))
@patch('tribler.core.utilities.utilities.print', new=MagicMock)
def test_show_system_popup_linux():
    import subprocess

    with patch('subprocess.Popen'):
        show_system_popup('title', 'text')
        subprocess.Popen.assert_called_once_with(['xmessage', '-center', 'text'])


@patch_import(modules=['subprocess'], Popen=MagicMock())
@patch('platform.system', new=MagicMock(return_value='Darwin'))
@patch('tribler.core.utilities.print', new=MagicMock)
def test_show_system_popup_darwin():
    import subprocess

    with patch('subprocess.Popen'):
        show_system_popup('title', 'text')
        subprocess.Popen.assert_called_once_with(['/usr/bin/osascript', '-e', 'text'])


@patch('platform.system', new=MagicMock(return_value='Unknown'))
@patch('tribler.core.utilities.utilities.print')
def test_show_system_popup_unknown(mocked_print):
    show_system_popup('title', 'text')
    mocked_print.assert_called_with('cannot create native pop-up for system Unknown')


@patch_import(modules=['subprocess'], Popen=MagicMock(side_effect=ValueError))
@patch('platform.system', new=MagicMock(return_value='Darwin'))
@patch('tribler.core.utilities.utilities.print')
def test_show_system_popup_exception(mocked_print):
    with patch('subprocess.Popen', new=MagicMock(side_effect=ValueError)):
        show_system_popup('title', 'text')
    last_call_args = mocked_print.call_args_list[-1]
    last_argument = last_call_args.args[0]
    assert last_argument.startswith('Error while')


def test_parse_magnetlink_valid():
    result = parse_magnetlink("magnet:?xt=urn:ed2k:354B15E68FB8F36D7CD88FF94116CDC1&xl=10826029&dn=mediawiki-1.15.1"
                              ".tar.gz&xt=urn:tree:tiger:7N5OAMRNGMSSEUE3ORHOKWN4WWIQ5X4EBOOTLJY&xt=urn:btih:QHQXPY"
                              "WMACKDWKP47RRVIV7VOURXFE5Q&tr=http%3A%2F%2Ftracker.example.org%2Fannounce.php%3Fuk"
                              "%3D1111111111%26&as=http%3A%2F%2Fdownload.wikimedia.org%2Fmediawiki%2F1.15%2Fmediawi"
                              "ki-1.15.1.tar.gz&xs=http%3A%2F%2Fcache.example.org%2FXRX2PEFXOOEJFRVUCX6HMZMKS5TWG4K"
                              "5&xs=dchub://example.org")
    assert result == ('mediawiki-1.15.1.tar.gz', b'\x81\xe1w\xe2\xcc\x00\x94;)\xfc\xfccTW\xf5u#r\x93\xb0',
                      ['http://tracker.example.org/announce.php?uk=1111111111&'])


def test_parse_magnetlink_nomagnet():
    result = parse_magnetlink("http://")
    assert result == (None, None, [])


def test_add_url_param_some_present():
    url = 'http://stackoverflow.com/test?answers=true'
    new_params = {'answers': False, 'data': ['some', 'values']}
    result = add_url_params(url, new_params)
    assert "data=values" in result
    assert "answers=false" in result


@patch('tribler.core.utilities.utilities.b32decode', new=Mock(side_effect=binascii.Error))
def test_parse_magnetlink_binascii_error_32(caplog):
    # Test that binascii.Error exceptions are logged for 32 symbol hash
    infohash_32 = 'A' * 32
    parse_magnetlink(f'magnet:?xt=urn:btih:{infohash_32}')
    assert f'Invalid infohash: {infohash_32}' in caplog.text


@patch('binascii.unhexlify', new=Mock(side_effect=binascii.Error))
def test_parse_magnetlink_binascii_error_40(caplog):
    # Test that binascii.Error exceptions are logged for 40 symbol hash
    infohash_40 = 'B' * 40
    parse_magnetlink(f'magnet:?xt=urn:btih:{infohash_40}')
    assert f'Invalid infohash: {infohash_40}' in caplog.text


def test_add_url_param_clean():
    url = 'http://stackoverflow.com/test'
    new_params = {'data': ['some', 'values']}
    result = add_url_params(url, new_params)
    assert "data=some" in result
    assert "data=values" in result


@patch('logging.config.dictConfig')
def test_load_logger(dict_config: Mock, tmpdir):
    """
    Test loading the Tribler logger configuration.
    """
    load_logger_config('test', tmpdir)

    dict_config.assert_called_once()
    config = dict_config.call_args.args[0]
    assert config['handlers'].keys() == {'info_file_handler', 'info_memory_handler',
                                         'error_file_handler', 'error_memory_handler',
                                         'stdout_handler', 'stderr_handler'}


@patch('logging.config.dictConfig')
@patch('tribler.core.logger.logger.logger')
def test_load_logger_no_primary_process(logger: Mock, dict_config: Mock, tmpdir):
    """
    Test loading the Tribler logger configuration.
    """
    load_logger_config('test', tmpdir, current_process_is_primary=False)
    logger.info.assert_called_once()
    assert logger.info.call_args.args[0].startswith(
        'Skip the initialization of a normal file-based logging as the current process is non-primary.')
    dict_config.assert_not_called()


def test_get_normally_distributed_positive_integers():
    """
    Test if the random number returned are all positive integers
    """
    random_integer_numbers = get_normally_distributed_positive_integers()

    # check if the numbers are unique
    assert len(set(random_integer_numbers)) == len(random_integer_numbers)

    # check if all numbers are integers and positive
    is_positive_and_unique = all(number >= 0 and isinstance(number, int) for number in random_integer_numbers)
    assert is_positive_and_unique

    with pytest.raises(ValueError):
        _ = get_normally_distributed_positive_integers(size=11, upper_limit=10)

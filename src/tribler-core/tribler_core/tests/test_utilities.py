import logging

from ipv8.messaging.deprecated.encoding import add_url_params

from tribler_core import load_logger_config
from tribler_core.utilities.utilities import parse_magnetlink


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


def test_add_url_param_clean():
    url = 'http://stackoverflow.com/test'
    new_params = {'data': ['some', 'values']}
    result = add_url_params(url, new_params)
    assert "data=some" in result
    assert "data=values" in result


def test_load_logger(tmpdir):
    """
    Test loading the Tribler logger configuration.
    """
    logger_count = len(logging.root.manager.loggerDict)
    load_logger_config(tmpdir)
    assert len(logging.root.manager.loggerDict) >= logger_count

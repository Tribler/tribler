
from aiohttp.web_app import Application

import pytest

from tribler_common.simpledefs import MAX_LIBTORRENT_RATE_LIMIT

from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler_core.components.restapi.rest.base_api_test import do_request
from tribler_core.components.restapi.rest.rest_manager import error_middleware
from tribler_core.components.restapi.rest.settings_endpoint import SettingsEndpoint


@pytest.fixture
def tribler_config(tmp_path):
    config = TriblerConfig(tmp_path)
    return config


@pytest.fixture
def endpoint(tribler_config):
    endpoint = SettingsEndpoint()
    endpoint.tribler_config = tribler_config
    return endpoint


@pytest.fixture
def rest_api(loop, aiohttp_client, endpoint):  # pylint: disable=unused-argument
    app = Application(middlewares=[error_middleware])
    app.add_subapp('/settings', endpoint.app)
    return loop.run_until_complete(aiohttp_client(app))


def verify_settings(settings_dict):
    """
    Verify that the expected sections are present.
    """
    check_section = ['libtorrent', 'general', 'torrent_checking',
                     'tunnel_community', 'api', 'trustchain', 'watch_folder']

    assert settings_dict['settings']
    for section in check_section:
        assert settings_dict['settings'][section]


async def test_unicode_chars(rest_api):
    """
    Test setting watch_folder to a unicode path.
    """
    post_data = {'watch_folder': {'directory': '\u2588'}}

    await do_request(rest_api, 'settings', expected_code=200, request_type='POST', post_data=post_data)

    settings = await do_request(rest_api, 'settings')

    watch_folder = settings['settings']['watch_folder']['directory']
    assert watch_folder == post_data['watch_folder']['directory']


async def test_get_settings(rest_api):
    """
    Testing whether the API returns a correct settings dictionary when the settings are requested
    """
    response = await do_request(rest_api, 'settings', expected_code=200)
    verify_settings(response)


async def test_set_settings_invalid_dict(rest_api):
    """
    Testing whether an error is returned if we are passing an invalid dictionary that is too deep
    """
    post_data = {'a': {'b': {'c': 'd'}}}
    response_dict = await do_request(rest_api, 'settings', expected_code=500, request_type='POST', post_data=post_data)
    assert 'error' in response_dict


async def test_set_settings_no_key(rest_api):
    """
    Testing whether an error is returned when we try to set a non-existing key
    """
    def verify_response(response_dict):
        assert 'error' in response_dict

    post_data = {'general': {'b': 'c'}}
    verify_response(await do_request(rest_api, 'settings', expected_code=500, request_type='POST', post_data=post_data))

    post_data = {'Tribler': {'b': 'c'}}
    verify_response(await do_request(rest_api, 'settings', expected_code=500, request_type='POST', post_data=post_data))


async def test_set_settings(rest_api, tribler_config):
    """
    Testing whether settings in the API can be successfully set
    """

    post_data = {'download_defaults': {'seeding_mode': 'ratio',
                                       'seeding_ratio': 3,
                                       'seeding_time': 123}}
    await do_request(rest_api, 'settings', expected_code=200, request_type='POST', post_data=post_data)
    assert tribler_config.download_defaults.seeding_mode == 'ratio'
    assert tribler_config.download_defaults.seeding_ratio == 3
    assert tribler_config.download_defaults.seeding_time == 123


async def test_set_rate_settings(rest_api, tribler_config):
    """
    Testing whether libtorrent rate limits works for large number without overflow error.
    """

    extra_rate = 1024 * 1024 * 1024  # 1GB/s
    post_data = {
        'libtorrent': {
            'max_download_rate': MAX_LIBTORRENT_RATE_LIMIT + extra_rate,
            'max_upload_rate': MAX_LIBTORRENT_RATE_LIMIT + extra_rate
        }
    }
    await do_request(rest_api, 'settings', expected_code=200, request_type='POST', post_data=post_data)

    assert DownloadManager.get_libtorrent_max_download_rate(tribler_config.libtorrent) == MAX_LIBTORRENT_RATE_LIMIT
    assert DownloadManager.get_libtorrent_max_upload_rate(tribler_config.libtorrent) == MAX_LIBTORRENT_RATE_LIMIT

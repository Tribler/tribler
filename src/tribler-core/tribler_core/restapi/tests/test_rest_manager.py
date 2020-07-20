import os

import pytest

from tribler_core.exceptions import TriblerException
from tribler_core.restapi.base_api_test import do_request
from tribler_core.restapi.rest_endpoint import HTTP_UNAUTHORIZED
from tribler_core.restapi.settings_endpoint import SettingsEndpoint


def RaiseException(*args, **kwargs):
    raise TriblerException(u"Oops! Something went wrong. Please restart Tribler")


@pytest.mark.asyncio
async def test_https(enable_api, enable_https, tribler_config, session):
    await do_request(session, f'https://localhost:{tribler_config.get_api_https_port()}/state')


@pytest.mark.asyncio
async def test_api_key_disabled(enable_api, session):
    session.config.set_api_key('')
    await do_request(session, 'state')
    await do_request(session, 'state?apikey=111')
    await do_request(session, 'state', headers={'X-Api-Key': '111'})


@pytest.mark.asyncio
async def test_api_key_success(enable_api, session):
    api_key = '0' * 32
    session.config.set_api_key(api_key)
    await do_request(session, 'state?apikey=' + api_key)
    await do_request(session, 'state', headers={'X-Api-Key': api_key})


@pytest.mark.asyncio
async def test_api_key_fail(enable_api, session):
    api_key = '0' * 32
    session.config.set_api_key(api_key)
    await do_request(session, 'state', expected_code=HTTP_UNAUTHORIZED, expected_json={'error': 'Unauthorized access'})
    await do_request(session, 'state?apikey=111',
                     expected_code=HTTP_UNAUTHORIZED, expected_json={'error': 'Unauthorized access'})
    await do_request(session, 'state', headers={'X-Api-Key': '111'},
                     expected_code=HTTP_UNAUTHORIZED, expected_json={'error': 'Unauthorized access'})


@pytest.mark.asyncio
async def test_unhandled_exception(enable_api, session):
    """
    Testing whether the API returns a formatted 500 error if an unhandled Exception is raised
    """
    post_data = {"settings": "bla", "ports": "bla"}
    orig_parse_settings_dict = SettingsEndpoint.parse_settings_dict
    SettingsEndpoint.parse_settings_dict = RaiseException
    response_dict = await do_request(session, 'settings', expected_code=500, post_data=post_data, request_type='POST')

    SettingsEndpoint.parse_settings_dict = orig_parse_settings_dict
    assert not response_dict['error']['handled']
    assert response_dict['error']['code'] == "TriblerException"


@pytest.mark.asyncio
async def test_tribler_shutting_down(enable_api, session):
    """
    Testing whether the API returns a formatted 500 error for any request if tribler is shutting down.
    """

    # Indicates tribler is shutting down
    os.environ['TRIBLER_SHUTTING_DOWN'] = 'TRUE'

    error_response = await do_request(session, 'state', expected_code=500)

    expected_response = {
        "error": {
            "handled": False,
            "code": "Exception",
            "message": "Tribler is shutting down"
        }
    }
    assert error_response == expected_response

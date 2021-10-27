import shutil
from unittest.mock import patch

import pytest

from tribler_core.components.restapi.rest.base_api_test import do_real_request
from tribler_core.components.restapi.rest.rest_endpoint import HTTP_UNAUTHORIZED
from tribler_core.components.restapi.rest.rest_manager import ApiKeyMiddleware, RESTManager, error_middleware
from tribler_core.components.restapi.rest.root_endpoint import RootEndpoint
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.tests.tools.common import TESTS_DIR


@pytest.fixture()
def tribler_config():
    return TriblerConfig()


@pytest.fixture()
def api_port(free_port):
    return free_port


@pytest.fixture
async def rest_manager(request, tribler_config, api_port, tmp_path):
    config = tribler_config
    api_key_marker = request.node.get_closest_marker("api_key")
    if api_key_marker is not None:
        tribler_config.api.key = api_key_marker.args[0]

    enable_https_marker = request.node.get_closest_marker("enable_https")
    if enable_https_marker:
        tribler_config.api.https_enabled = True
        tribler_config.api.https_port = api_port
        shutil.copy(TESTS_DIR / 'data' / 'certfile.pem', tmp_path)
        config.api.put_path_as_relative('https_certfile', TESTS_DIR / 'data' / 'certfile.pem', tmp_path)
    else:
        tribler_config.api.http_enabled = True
        tribler_config.api.http_port = api_port
    root_endpoint = RootEndpoint(config, middlewares=[ApiKeyMiddleware(config.api.key), error_middleware])
    rest_manager = RESTManager(config=config.api, root_endpoint=root_endpoint, state_dir=tmp_path)
    await rest_manager.start()
    yield rest_manager
    await rest_manager.stop()


@pytest.mark.enable_https
@pytest.mark.asyncio
async def test_https(tribler_config, rest_manager, api_port):
    await do_real_request(api_port, f'https://localhost:{api_port}/state')


@pytest.mark.api_key('')
@pytest.mark.asyncio
async def test_api_key_disabled(rest_manager, api_port):
    await do_real_request(api_port, 'state')
    await do_real_request(api_port, 'state?apikey=111')
    await do_real_request(api_port, 'state', headers={'X-Api-Key': '111'})


@pytest.mark.api_key('0' * 32)
@pytest.mark.asyncio
async def test_api_key_success(rest_manager, api_port):
    api_key = rest_manager.config.key
    await do_real_request(api_port, 'state?apikey=' + api_key)
    await do_real_request(api_port, 'state', headers={'X-Api-Key': api_key})


@pytest.mark.api_key('0' * 32)
@pytest.mark.asyncio
async def test_api_key_fail(rest_manager, api_port):
    await do_real_request(api_port, 'state', expected_code=HTTP_UNAUTHORIZED, expected_json={'error': 'Unauthorized access'})
    await do_real_request(api_port, 'state?apikey=111',
                          expected_code=HTTP_UNAUTHORIZED, expected_json={'error': 'Unauthorized access'})
    await do_real_request(api_port, 'state', headers={'X-Api-Key': '111'},
                          expected_code=HTTP_UNAUTHORIZED, expected_json={'error': 'Unauthorized access'})


@pytest.mark.asyncio
async def test_unhandled_exception(rest_manager, api_port):
    rest_manager.config.http_port
    """
    Testing whether the API returns a formatted 500 error if an unhandled Exception is raised
    """
    response_dict = await do_real_request(api_port, 'settings', expected_code=500, post_data={'general': 'invalid schema'},
                                          request_type='POST')
    assert response_dict
    assert not response_dict['error']['handled']
    assert response_dict['error']['code'] == "TypeError"


@pytest.mark.asyncio
async def test_tribler_shutting_down(rest_manager, api_port):
    """
    Testing whether the API returns a 404 error for any request if tribler is shutting down.
    """

    # Indicates tribler is shutting down
    with patch('tribler_core.components.restapi.rest.rest_manager.tribler_shutting_down', new=lambda: True):
        error_response = await do_real_request(api_port, 'state', expected_code=404)

    expected_response = {
        "error": {
            "handled": True,
            "code": "ShuttingDownException",
            "message": "Tribler is shutting down"
        }
    }
    assert error_response == expected_response

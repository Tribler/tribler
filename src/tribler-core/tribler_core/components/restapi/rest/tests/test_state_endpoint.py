from aiohttp.web_app import Application

import pytest

from tribler_common.simpledefs import STATE_EXCEPTION

from tribler_core.components.restapi.rest.base_api_test import do_request
from tribler_core.components.restapi.rest.rest_manager import error_middleware
from tribler_core.components.restapi.rest.state_endpoint import StateEndpoint


@pytest.fixture
def endpoint():
    endpoint = StateEndpoint()
    return endpoint


@pytest.fixture
def rest_api(loop, aiohttp_client, endpoint):  # pylint: disable=unused-argument

    app = Application(middlewares=[error_middleware])
    app.add_subapp('/state', endpoint.app)
    return loop.run_until_complete(aiohttp_client(app))


async def test_get_state(rest_api, endpoint):
    """
    Testing whether the API returns a correct state when requested
    """
    endpoint.readable_status = "Started"
    endpoint.on_tribler_exception("abcd")
    expected_json = {"state": STATE_EXCEPTION, "last_exception": "abcd", "readable_state": "Started"}
    await do_request(rest_api, 'state', expected_code=200, expected_json=expected_json)

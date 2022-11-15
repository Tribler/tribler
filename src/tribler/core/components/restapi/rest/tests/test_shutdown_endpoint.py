from unittest.mock import Mock

import pytest
from aiohttp.web_app import Application

from tribler.core.components.restapi.rest.base_api_test import do_request
from tribler.core.components.restapi.rest.rest_manager import error_middleware
from tribler.core.components.restapi.rest.shutdown_endpoint import ShutdownEndpoint


@pytest.fixture
def endpoint():
    return ShutdownEndpoint(Mock())


@pytest.fixture
def rest_api(event_loop, aiohttp_client, endpoint):  # pylint: disable=unused-argument
    app = Application(middlewares=[error_middleware])
    app.add_subapp('/shutdown', endpoint.app)
    yield event_loop.run_until_complete(aiohttp_client(app))
    app.shutdown()


async def test_shutdown(rest_api, endpoint):
    """
    Testing whether the API triggers a Tribler shutdown
    """

    expected_json = {"shutdown": True}
    await do_request(rest_api, 'shutdown', expected_code=200, expected_json=expected_json, request_type='PUT')
    endpoint.shutdown_callback.assert_called()

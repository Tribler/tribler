from unittest.mock import Mock

from aiohttp.web_app import Application

import pytest

from tribler_core.components.restapi.rest.base_api_test import do_request
from tribler_core.components.restapi.rest.rest_manager import error_middleware
from tribler_core.components.upgrade.implementation.upgrader_endpoint import SKIP_DB_UPGRADE_STR, UpgraderEndpoint


@pytest.fixture
def endpoint():
    endpoint = UpgraderEndpoint()
    return endpoint


@pytest.fixture
def rest_api(loop, aiohttp_client, endpoint):  # pylint: disable=unused-argument

    app = Application(middlewares=[error_middleware])
    app.add_subapp('/upgrader', endpoint.app)
    return loop.run_until_complete(aiohttp_client(app))


async def test_upgrader_skip(rest_api, endpoint):
    """
    Test if the API call sets the "skip DB upgrade" flag in upgrader
    """

    post_params = {SKIP_DB_UPGRADE_STR: True}
    await do_request(rest_api, 'upgrader', expected_code=404, post_data=post_params, request_type='POST')

    def mock_skip():
        mock_skip.skip_called = True

    mock_skip.skip_called = False

    endpoint.upgrader = Mock()
    endpoint.upgrader.skip = mock_skip

    await do_request(rest_api, 'upgrader', expected_code=400, expected_json={'error': 'attribute to change is missing'},
                     post_data={}, request_type='POST')

    await do_request(rest_api, 'upgrader', expected_code=200, expected_json={SKIP_DB_UPGRADE_STR: True},
                     post_data=post_params, request_type='POST')
    assert mock_skip.skip_called

from unittest.mock import Mock

import pytest

from tribler.core.components.restapi.rest.base_api_test import do_request
from tribler.core.components.restapi.rest.shutdown_endpoint import ShutdownEndpoint


# pylint: disable=redefined-outer-name


@pytest.fixture
def endpoint():
    return ShutdownEndpoint(Mock())


async def test_shutdown(rest_api, endpoint):
    """
    Testing whether the API triggers a Tribler shutdown
    """

    expected_json = {"shutdown": True}
    await do_request(rest_api, 'shutdown', expected_code=200, expected_json=expected_json, request_type='PUT')
    endpoint.shutdown_callback.assert_called()

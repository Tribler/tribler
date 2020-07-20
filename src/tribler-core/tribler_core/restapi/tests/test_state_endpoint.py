import pytest

from tribler_core.restapi.base_api_test import do_request


@pytest.mark.asyncio
async def test_get_state(enable_api, session):
    """
    Testing whether the API returns a correct state when requested
    """
    session.api_manager.root_endpoint.endpoints['/state'].on_tribler_exception("abcd")
    expected_json = {"state": "EXCEPTION", "last_exception": "abcd", "readable_state": "Started"}
    await do_request(session, 'state', expected_code=200, expected_json=expected_json)

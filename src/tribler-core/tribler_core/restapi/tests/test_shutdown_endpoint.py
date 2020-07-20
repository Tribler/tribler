from ipv8.util import succeed

import pytest

from tribler_core.restapi.base_api_test import do_request


@pytest.mark.asyncio
async def test_shutdown(enable_api, session):
    """
    Testing whether the API triggers a Tribler shutdown
    """
    orig_shutdown = session.shutdown

    def fake_shutdown():
        # Record session.shutdown was called
        fake_shutdown.shutdown_called = True
        # Restore original shutdown for test teardown
        session.shutdown = orig_shutdown
        return succeed(True)

    session.shutdown = fake_shutdown
    fake_shutdown.shutdown_called = False

    expected_json = {"shutdown": True}
    await do_request(session, 'shutdown', expected_code=200, expected_json=expected_json, request_type='PUT')
    assert fake_shutdown.shutdown_called

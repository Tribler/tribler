from unittest.mock import Mock

import pytest

from tribler_core.restapi.base_api_test import do_request
from tribler_core.upgrade.upgrader_endpoint import SKIP_DB_UPGRADE_STR


@pytest.mark.asyncio
async def test_upgrader_skip(enable_api, session):
    """
    Test if the API call sets the "skip DB upgrade" flag in upgrader
    """

    post_params = {SKIP_DB_UPGRADE_STR: True}
    await do_request(session, 'upgrader', expected_code=404, post_data=post_params, request_type='POST')

    def mock_skip():
        mock_skip.skip_called = True

    mock_skip.skip_called = False

    session.upgrader = Mock()
    session.upgrader.skip = mock_skip

    await do_request(session, 'upgrader', expected_code=400, expected_json={'error': 'attribute to change is missing'},
                     post_data={}, request_type='POST')

    await do_request(session, 'upgrader', expected_code=200, expected_json={SKIP_DB_UPGRADE_STR: True},
                     post_data=post_params, request_type='POST')
    assert mock_skip.skip_called

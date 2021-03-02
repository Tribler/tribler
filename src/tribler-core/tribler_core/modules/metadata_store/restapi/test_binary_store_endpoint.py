from pony.orm import db_session

import pytest

from tribler_core.modules.metadata_store.restapi.test_binary_data import PNG_DATA
from tribler_core.restapi.base_api_test import do_request
from tribler_core.utilities.unicode import hexlify


@pytest.mark.asyncio
async def test_get_binary_entry(enable_chant, enable_api, session):
    """
    Test getting a binary entry from Metadata Store with Web API GET request
    """

    with db_session:
        obj = session.mds.BinaryData(data=PNG_DATA)
        data_hash = obj.hash

    result = await do_request(session, f'binary_store/{hexlify(data_hash)}.png', json_response=False)
    assert result == PNG_DATA


@pytest.mark.asyncio
async def test_post_binary_entry(enable_chant, enable_api, session):
    result = await do_request(
        session, f'binary_store', request_type="POST", json_response=False, post_data=PNG_DATA, expected_code=201
    )

    with db_session:
        obj = session.mds.BinaryData.get()
        assert obj.data == PNG_DATA

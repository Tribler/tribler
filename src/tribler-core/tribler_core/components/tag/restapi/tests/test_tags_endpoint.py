from unittest.mock import Mock

import pytest
from aiohttp.web_app import Application
from freezegun import freeze_time
from pony.orm import db_session

from ipv8.keyvault.crypto import default_eccrypto
from tribler_core.components.restapi.rest.base_api_test import do_request

from tribler_core.components.tag.community.tag_payload import TagOperation, TagOperationEnum
from tribler_core.components.tag.restapi.tags_endpoint import TagsEndpoint
from tribler_core.conftest import TEST_PERSONAL_KEY
from tribler_core.utilities.unicode import hexlify


# pylint: disable=redefined-outer-name

@pytest.fixture
def tags_endpoint(tags_db):
    endpoint = TagsEndpoint()
    endpoint.db = tags_db
    endpoint.community = Mock()
    endpoint.community.my_peer.key = TEST_PERSONAL_KEY
    endpoint.community.sign = Mock(return_value=b'')
    return endpoint


@pytest.fixture
def rest_api(loop, aiohttp_client, tags_endpoint):
    app = Application()
    app.add_subapp('/tags', tags_endpoint.app)
    return loop.run_until_complete(aiohttp_client(app))


async def test_add_tag_invalid_infohash(rest_api):
    """
    Test whether an error is returned if we try to add a tag to content with an invalid infohash
    """
    post_data = {"tags": ["abc", "def"]}
    await do_request(rest_api, 'tags/3f3', request_type="PATCH", expected_code=400, post_data=post_data)
    await do_request(rest_api, 'tags/3f3f', request_type="PATCH", expected_code=400, post_data=post_data)


async def test_add_invalid_tag(rest_api):
    """
    Test whether an error is returned if we try to add a tag that is too short or long.
    """
    post_data = {"tags": ["a"]}
    infohash = b'a' * 20
    await do_request(rest_api, f'tags/{hexlify(infohash)}', request_type="PATCH", expected_code=400,
                     post_data=post_data)

    post_data = {"tags": ["a" * 60]}
    await do_request(rest_api, f'tags/{hexlify(infohash)}', request_type="PATCH", expected_code=400,
                     post_data=post_data)


async def test_modify_tags(rest_api, tags_db):
    """
    Test modifying tags
    """
    post_data = {"tags": ["abc", "def"]}
    infohash = b'a' * 20
    with freeze_time("2015-01-01") as frozen_time:
        await do_request(rest_api, f'tags/{hexlify(infohash)}', request_type="PATCH", expected_code=200,
                         post_data=post_data)
        with db_session:
            tags = tags_db.get_tags(infohash)
        assert len(tags) == 2

        # Now remove a tag
        frozen_time.move_to("2016-01-01")
        post_data = {"tags": ["abc"]}
        await do_request(rest_api, f'tags/{hexlify(infohash)}', request_type="PATCH", expected_code=200,
                         post_data=post_data)
        with db_session:
            tags = tags_db.get_tags(infohash)
        assert tags == ["abc"]


async def test_modify_tags_no_community(tags_db, tags_endpoint):
    tags_endpoint.community = None
    infohash = b'a' * 20
    tags_endpoint.modify_tags(infohash, {"abc", "def"})

    with db_session:
        tags = tags_db.get_tags(infohash)

    assert len(tags) == 0


async def test_get_suggestions_invalid_infohash(rest_api):
    """
    Test whether an error is returned if we fetch suggestions from content with an invalid infohash
    """
    post_data = {"tags": ["abc", "def"]}
    await do_request(rest_api, 'tags/3f3/suggestions', expected_code=400, post_data=post_data)
    await do_request(rest_api, 'tags/3f3f/suggestions', expected_code=400, post_data=post_data)


async def test_get_suggestions(rest_api, tags_db):
    """
    Test whether we can successfully fetch suggestions from content
    """
    infohash = b'a' * 20
    response = await do_request(rest_api, f'tags/{hexlify(infohash)}/suggestions')
    assert "suggestions" in response
    assert not response["suggestions"]

    # Add a suggestion to the database
    with db_session:
        random_key = default_eccrypto.generate_key('low')
        operation = TagOperation(infohash=infohash, tag="test", operation=TagOperationEnum.ADD, clock=0,
                                 creator_public_key=random_key.pub().key_to_bin())
        tags_db.add_tag_operation(operation, b"")

    response = await do_request(rest_api, f'tags/{hexlify(infohash)}/suggestions')
    assert response["suggestions"] == ["test"]

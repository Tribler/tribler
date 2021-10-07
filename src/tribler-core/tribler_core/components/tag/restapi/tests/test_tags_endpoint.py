import pytest
from aiohttp.web_app import Application
from freezegun import freeze_time
from pony.orm import db_session

from tribler_core.components.tag.restapi.tags_endpoint import TagsEndpoint
from tribler_core.conftest import TEST_PERSONAL_KEY
from tribler_core.restapi.base_api_test import do_request
from tribler_core.utilities.unicode import hexlify


@pytest.fixture
def rest_api(loop, aiohttp_client, tags_db):
    tags_endpoint = TagsEndpoint()
    tags_endpoint.tags_db = tags_db
    tags_endpoint.key = TEST_PERSONAL_KEY
    app = Application()
    app.add_subapp('/tags', tags_endpoint.app)
    return loop.run_until_complete(aiohttp_client(app))


async def test_add_tag_invalid_infohash(rest_api):  # pylint: disable=redefined-outer-name
    """
    Test whether an error is returned if we try to add a tag to content with an invalid infohash
    """
    post_data = {"tags": ["abc", "def"]}
    await do_request(rest_api, 'tags/3f3', request_type="PATCH", expected_code=400, post_data=post_data)
    await do_request(rest_api, 'tags/3f3f', request_type="PATCH", expected_code=400, post_data=post_data)


async def test_add_invalid_tag(rest_api):  # pylint: disable=redefined-outer-name
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


async def test_modify_tags(rest_api, tags_db):  # pylint: disable=redefined-outer-name
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

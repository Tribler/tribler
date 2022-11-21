from typing import Dict
from unittest.mock import Mock

import pytest
from aiohttp.web_app import Application
from freezegun import freeze_time
from ipv8.keyvault.crypto import default_eccrypto
from pony.orm import db_session

from tribler.core.components.knowledge.community.knowledge_payload import StatementOperation
from tribler.core.components.knowledge.db.knowledge_db import Operation, ResourceType
from tribler.core.components.knowledge.restapi.knowledge_endpoint import KnowledgeEndpoint
from tribler.core.components.restapi.rest.base_api_test import do_request
from tribler.core.conftest import TEST_PERSONAL_KEY
from tribler.core.utilities.unicode import hexlify


# pylint: disable=redefined-outer-name

@pytest.fixture
def knowledge_endpoint(knowledge_db):
    community = Mock()
    community.key = TEST_PERSONAL_KEY
    community.sign = Mock(return_value=b'')
    endpoint = KnowledgeEndpoint(knowledge_db, community)
    return endpoint


@pytest.fixture
def rest_api(event_loop, aiohttp_client, knowledge_endpoint):
    app = Application()
    app.add_subapp('/knowledge', knowledge_endpoint.app)
    yield event_loop.run_until_complete(aiohttp_client(app))
    app.shutdown()


def tag_to_statement(tag: str) -> Dict:
    return {"predicate": ResourceType.TAG, "object": tag}


async def test_add_tag_invalid_infohash(rest_api):
    """
    Test whether an error is returned if we try to add a tag to content with an invalid infohash
    """
    post_data = {"knowledge": [tag_to_statement("abc"), tag_to_statement("def")]}
    await do_request(rest_api, 'knowledge/3f3', request_type="PATCH", expected_code=400, post_data=post_data)
    await do_request(rest_api, 'knowledge/3f3f', request_type="PATCH", expected_code=400, post_data=post_data)


async def test_add_invalid_tag(rest_api):
    """
    Test whether an error is returned if we try to add a tag that is too short or long.
    """
    post_data = {"statements": [tag_to_statement("a")]}
    infohash = b'a' * 20
    await do_request(rest_api, f'knowledge/{hexlify(infohash)}', request_type="PATCH", expected_code=400,
                     post_data=post_data)

    post_data = {"statements": [tag_to_statement("a" * 60)]}
    await do_request(rest_api, f'knowledge/{hexlify(infohash)}', request_type="PATCH", expected_code=400,
                     post_data=post_data)


async def test_modify_tags(rest_api, knowledge_db):
    """
    Test modifying tags
    """
    post_data = {"statements": [tag_to_statement("abc"), tag_to_statement("def")]}
    infohash = 'a' * 40
    with freeze_time("2015-01-01") as frozen_time:
        await do_request(rest_api, f'knowledge/{infohash}', request_type="PATCH", expected_code=200,
                         post_data=post_data)
        with db_session:
            tags = knowledge_db.get_objects(subject=infohash, predicate=ResourceType.TAG)
        assert len(tags) == 2

        # Now remove a tag
        frozen_time.move_to("2016-01-01")
        post_data = {"statements": [tag_to_statement("abc")]}
        await do_request(rest_api, f'knowledge/{infohash}', request_type="PATCH", expected_code=200,
                         post_data=post_data)
        with db_session:
            tags = knowledge_db.get_objects(subject=infohash, predicate=ResourceType.TAG)
        assert tags == ["abc"]


async def test_modify_tags_no_community(knowledge_db, knowledge_endpoint):
    knowledge_endpoint.community = None
    infohash = 'a' * 20
    knowledge_endpoint.modify_statements(infohash, [tag_to_statement("abc"), tag_to_statement("def")])

    with db_session:
        tags = knowledge_db.get_objects(subject=infohash, predicate=ResourceType.TAG)

    assert len(tags) == 0


async def test_get_suggestions_invalid_infohash(rest_api):
    """
    Test whether an error is returned if we fetch suggestions from content with an invalid infohash
    """
    await do_request(rest_api, 'knowledge/3f3/tag_suggestions', expected_code=400)
    await do_request(rest_api, 'knowledge/3f3f/tag_suggestions', expected_code=400)


async def test_get_suggestions(rest_api, knowledge_db):
    """
    Test whether we can successfully fetch suggestions from content
    """
    infohash = b'a' * 20
    infohash_str = hexlify(infohash)
    response = await do_request(rest_api, f'knowledge/{infohash_str}/tag_suggestions')
    assert "suggestions" in response
    assert not response["suggestions"]

    # Add a suggestion to the database
    with db_session:
        def _add_operation(op=Operation.ADD):
            random_key = default_eccrypto.generate_key('low')
            operation = StatementOperation(subject_type=ResourceType.TORRENT, subject=infohash_str,
                                           predicate=ResourceType.TAG, object="test", operation=op, clock=0,
                                           creator_public_key=random_key.pub().key_to_bin())
            knowledge_db.add_operation(operation, b"")

        _add_operation(op=Operation.ADD)
        _add_operation(op=Operation.REMOVE)

    response = await do_request(rest_api, f'knowledge/{infohash_str}/tag_suggestions')
    assert response["suggestions"] == ["test"]

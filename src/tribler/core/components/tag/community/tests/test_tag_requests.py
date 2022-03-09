import pytest

from tribler_core.components.tag.community.tag_requests import TagRequests


# pylint: disable=protected-access, redefined-outer-name

@pytest.fixture
def tag_requests():
    return TagRequests()


pytestmark = pytest.mark.asyncio


async def test_add_peer(tag_requests):
    tag_requests.register_peer('peer', number_of_responses=10)
    assert tag_requests.requests['peer'] == 10


async def test_clear_requests(tag_requests):
    tag_requests.register_peer('peer', number_of_responses=10)
    assert len(tag_requests.requests) == 1

    tag_requests.clear_requests()
    assert len(tag_requests.requests) == 0


async def test_valid_peer(tag_requests):
    tag_requests.register_peer('peer', number_of_responses=10)
    tag_requests.validate_peer('peer')


async def test_missed_peer(tag_requests):
    with pytest.raises(ValueError):
        tag_requests.validate_peer('peer')


async def test_invalid_peer(tag_requests):
    tag_requests.register_peer('peer', number_of_responses=1)
    tag_requests.validate_peer('peer')

    with pytest.raises(ValueError):
        tag_requests.validate_peer('peer')

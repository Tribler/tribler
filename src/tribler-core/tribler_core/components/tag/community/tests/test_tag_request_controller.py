import pytest

from tribler_core.components.tag.community.tag_request_controller import TagRequestController


@pytest.fixture(name="controller")  # this workaround implemented only for pylint
def fixture_controller():
    return TagRequestController()


pytestmark = pytest.mark.asyncio


async def test_add_peer(controller: TagRequestController):
    controller.register_peer('peer', number_of_responses=10)
    assert controller.requests['peer'] == 10


async def test_clear_requests(controller: TagRequestController):
    controller.register_peer('peer', number_of_responses=10)
    assert len(controller.requests) == 1

    controller.clear_requests()
    assert len(controller.requests) == 0


async def test_valid_peer(controller: TagRequestController):
    controller.register_peer('peer', number_of_responses=10)
    controller.validate_peer('peer')


async def test_missed_peer(controller: TagRequestController):
    with pytest.raises(ValueError):
        controller.validate_peer('peer')


async def test_invalid_peer(controller: TagRequestController):
    controller.register_peer('peer', number_of_responses=1)
    controller.validate_peer('peer')

    with pytest.raises(ValueError):
        controller.validate_peer('peer')

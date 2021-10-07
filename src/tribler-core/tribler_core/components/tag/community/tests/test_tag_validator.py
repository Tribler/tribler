import pytest

from ipv8.messaging.lazy_payload import VariablePayload
from tribler_core.components.tag.community.tag_payload import TagOperationMessage
from tribler_core.components.tag.community.tag_validator import TagValidator
from tribler_core.components.tag.db.tag_db import Operation


@pytest.fixture(name="validator")  # this workaround implemented only for pylint
def fixture_validator():
    return TagValidator()


pytestmark = pytest.mark.asyncio


def create_message(infohash=b'infohash', operation: int = Operation.ADD, time: int = 0,
                   creator_public_key=b'creator_public_key', signature=b'signature',
                   tag: str = 'tag') -> VariablePayload:
    return TagOperationMessage(infohash, operation, time, creator_public_key, signature, tag.encode())


async def test_correct_tag_size(validator: TagValidator):
    validator.validate_mesage(create_message(tag='123'))
    validator.validate_mesage(create_message(tag='1' * 50))


async def test_empty_tag(validator: TagValidator):
    with pytest.raises(ValueError):
        validator.validate_mesage(create_message(tag=''))


async def test_tag_less_than_3(validator: TagValidator):
    with pytest.raises(ValueError):
        validator.validate_mesage(create_message(tag='12'))


async def test_tag_more_than_50(validator: TagValidator):
    with pytest.raises(ValueError):
        validator.validate_mesage(create_message(tag='1' * 51))


async def test_correct_operation(validator: TagValidator):
    validator.validate_mesage(create_message(operation=Operation.ADD))
    validator.validate_mesage(create_message(operation=1))


async def test_incorrect_operation(validator: TagValidator):
    with pytest.raises(ValueError):
        validator.validate_mesage(create_message(operation=100))

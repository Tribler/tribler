import pytest

from tribler_core.components.tag.community.tag_payload import TagOperation
from tribler_core.components.tag.db.tag_db import TagOperationEnum

pytestmark = pytest.mark.asyncio


def create_message(operation: int = TagOperationEnum.ADD, tag: str = 'tag') -> TagOperation:
    return TagOperation(infohash=b'infohash', operation=operation, clock=0, creator_public_key=b'peer', tag=tag)


async def test_correct_tag_size():
    create_message(tag='123').validate()
    create_message(tag='1' * 50).validate()


async def test_empty_tag():
    with pytest.raises(AssertionError):
        create_message(tag='').validate()


async def test_tag_less_than_3():
    with pytest.raises(AssertionError):
        create_message(tag='12').validate()


async def test_tag_more_than_50():
    with pytest.raises(AssertionError):
        create_message(tag='1' * 51).validate()


async def test_correct_operation():
    create_message(operation=TagOperationEnum.ADD).validate()
    create_message(operation=1).validate()


async def test_incorrect_operation():
    with pytest.raises(ValueError):
        create_message(operation=100).validate()


async def test_contain_upper_case():
    with pytest.raises(AssertionError):
        create_message(tag='Tag').validate()


async def test_contain_upper_case_not_latin():
    with pytest.raises(AssertionError):
        create_message(tag='Тэг').validate()


async def test_contain_any_space():
    with pytest.raises(AssertionError):
        create_message(tag="tag with space").validate()

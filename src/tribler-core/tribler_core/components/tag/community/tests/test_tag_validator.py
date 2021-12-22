import pytest

from tribler_core.components.tag.community.tag_payload import TagOperationEnum
from tribler_core.components.tag.community.tag_validator import validate_operation, validate_tag

pytestmark = pytest.mark.asyncio


async def test_correct_tag_size():
    validate_tag('123')
    validate_tag('1' * 50)


async def test_empty_tag():
    with pytest.raises(ValueError):
        validate_tag('')


async def test_tag_less_than_3():
    with pytest.raises(ValueError):
        validate_tag('12')


async def test_tag_more_than_50():
    with pytest.raises(ValueError):
        validate_tag('1' * 51)


async def test_correct_operation():
    validate_operation(TagOperationEnum.ADD)
    validate_operation(1)


async def test_incorrect_operation():
    with pytest.raises(ValueError):
        validate_operation(100)


async def test_contains_upper_case():
    with pytest.raises(ValueError):
        validate_tag('Tag')


async def test_contains_upper_case_not_latin():
    with pytest.raises(ValueError):
        validate_tag('Тэг')


async def test_contain_any_space():
    with pytest.raises(ValueError):
        validate_tag('tag with space')

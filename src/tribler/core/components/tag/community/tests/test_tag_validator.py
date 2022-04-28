import pytest

from tribler.core.components.tag.community.tag_payload import TagOperationEnum
from tribler.core.components.tag.community.tag_validator import is_valid_tag, validate_operation, validate_tag



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


async def test_is_valid_tag():
    # test that is_valid_tag works similar to validate_tag but it returns `bool`
    # instead of raise the ValueError exception
    assert is_valid_tag('valid-tag')
    assert not is_valid_tag('invalid tag')

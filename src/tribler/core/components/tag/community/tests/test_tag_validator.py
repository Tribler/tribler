import pytest

from tribler.core.components.tag.db.tag_db import Operation, Predicate
from tribler.core.components.tag.community.tag_validator import is_valid_tag, validate_operation, validate_relation, \
    validate_tag

VALID_TAGS = [
    'tag',
    'Tag',
    'Тэг',
    'Tag with space',
]

INVALID_TAGS = [
    '',
    'ta',  # less than 3
    't' * 51,  # more than 50
]


@pytest.mark.parametrize('tag', VALID_TAGS)
async def test_valid_tags(tag):
    validate_tag(tag)  # no exception
    assert is_valid_tag(tag)


@pytest.mark.parametrize('tag', INVALID_TAGS)
async def test_invalid(tag):
    assert not is_valid_tag(tag)
    with pytest.raises(ValueError):
        validate_tag(tag)


async def test_correct_operation():
    for operation in Operation:
        validate_operation(operation)  # no exception
        validate_operation(operation.value)  # no exception


async def test_incorrect_operation():
    max_operation = max(Operation)
    with pytest.raises(ValueError):
        validate_operation(max_operation.value + 1)


async def test_correct_relation():
    for relation in Predicate:
        validate_relation(relation)  # no exception
        validate_relation(relation.value)  # no exception


async def test_incorrect_relation():
    max_relation = max(Predicate)
    with pytest.raises(ValueError):
        validate_operation(max_relation.value + 1)

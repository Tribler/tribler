import pytest

from tribler.core.components.database.db.layers.knowledge_data_access_layer import Operation, ResourceType
from tribler.core.components.knowledge.community.knowledge_validator import is_valid_resource, validate_operation, \
    validate_resource, validate_resource_type

VALID_TAGS = [
    'nl',
    'tag',
    'Tag',
    'Тэг',
    'Tag with space',
]

INVALID_TAGS = [
    '',
    't',
    't' * 51,  # more than 50
]


@pytest.mark.parametrize('tag', VALID_TAGS)
def test_valid_tags(tag):
    validate_resource(tag)  # no exception
    assert is_valid_resource(tag)


@pytest.mark.parametrize('tag', INVALID_TAGS)
def test_invalid(tag):
    assert not is_valid_resource(tag)
    with pytest.raises(ValueError):
        validate_resource(tag)


def test_correct_operation():
    for operation in Operation:
        validate_operation(operation)  # no exception
        validate_operation(operation.value)  # no exception


def test_incorrect_operation():
    max_operation = max(Operation)
    with pytest.raises(ValueError):
        validate_operation(max_operation.value + 1)


def test_correct_relation():
    for relation in ResourceType:
        validate_resource_type(relation)  # no exception
        validate_resource_type(relation.value)  # no exception


def test_incorrect_relation():
    max_relation = max(ResourceType)
    with pytest.raises(ValueError):
        validate_operation(max_relation.value + 1)

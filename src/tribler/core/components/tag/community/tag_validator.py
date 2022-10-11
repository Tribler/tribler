from tribler.core.components.tag.db.tag_db import Operation, ResourceType
from tribler.core.components.tag.tag_constants import MAX_TAG_LENGTH, MIN_TAG_LENGTH


def validate_tag(tag: str):
    """Validate the tag. Raises ValueError, in the case the tag is not valid."""
    if len(tag) < MIN_TAG_LENGTH or len(tag) > MAX_TAG_LENGTH:
        raise ValueError('Tag length should be in range [3..50]')


def is_valid_tag(tag: str) -> bool:
    """Validate the tag. Returns False, in the case the tag is not valid."""
    try:
        validate_tag(tag)
    except ValueError:
        return False
    return True


def validate_operation(operation: int):
    """Validate the incoming operation. Raises ValueError, in the case the operation is not valid."""
    Operation(operation)


def validate_relation(relation: int):
    """Validate the incoming relation. Raises ValueError, in the case the relation is not valid."""
    ResourceType(relation)

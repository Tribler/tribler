from tribler_common.tag_constants import MAX_TAG_LENGTH, MIN_TAG_LENGTH

from tribler_core.components.tag.community.tag_payload import TagOperationEnum


def validate_tag(tag: str):
    if len(tag) < MIN_TAG_LENGTH or len(tag) > MAX_TAG_LENGTH:
        raise ValueError('Tag length should be in range [3..50]')
    if any(ch.isupper() for ch in tag):
        raise ValueError('Tag should not contain upper-case letters')
    if ' ' in tag:
        raise ValueError('Tag should not contain any spaces')


def is_valid_tag(tag: str) -> bool:
    try:
        validate_tag(tag)
    except ValueError:
        return False
    return True


def validate_operation(operation: int):
    TagOperationEnum(operation)

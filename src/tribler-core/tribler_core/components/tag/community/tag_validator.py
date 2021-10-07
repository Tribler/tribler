from ipv8.messaging.lazy_payload import VariablePayload
from tribler_common.tag_constants import MAX_TAG_LENGTH, MIN_TAG_LENGTH
from tribler_core.components.tag.db.tag_db import Operation


class TagValidator:
    @staticmethod
    def validate_mesage(message: VariablePayload):
        if not message.tag:
            raise ValueError("Tag can't be empty")

        tag_length = len(message.tag.decode())
        if not MIN_TAG_LENGTH <= tag_length <= MAX_TAG_LENGTH:
            raise ValueError('Tag length should be in range [3..50]')

        # try co convert operation into Enum
        Operation(message.operation)

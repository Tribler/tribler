from pony.orm import Optional

from tribler_core.modules.metadata_store.serialization import DESCRIPTION_NODE, DescriptionNodePayload


def define_binding(db):
    class DescriptionNode(db.JsonNode):
        """
        This ORM class represents channel descriptions.
        """
        _discriminator_ = DESCRIPTION_NODE

    return DescriptionNode

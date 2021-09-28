from tribler_core.components.metadata_store.db.serialization import CHANNEL_DESCRIPTION


def define_binding(db):
    class ChannelDescription(db.JsonNode):
        """
        This ORM class represents channel descriptions.
        """

        _discriminator_ = CHANNEL_DESCRIPTION

    return ChannelDescription

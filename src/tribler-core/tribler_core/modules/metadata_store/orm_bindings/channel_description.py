from tribler_core.modules.metadata_store.serialization import CHANNEL_DESCRIPTION


def define_binding(db, db_version: int):
    class ChannelDescription(db.JsonNode):
        """
        This ORM class represents channel descriptions.
        """

        _discriminator_ = CHANNEL_DESCRIPTION

    return ChannelDescription

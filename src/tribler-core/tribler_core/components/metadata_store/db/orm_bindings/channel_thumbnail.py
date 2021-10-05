from tribler_core.components.metadata_store.db.serialization import CHANNEL_THUMBNAIL


def define_binding(db):
    class ChannelThumbnail(db.BinaryNode):
        """
        This ORM class represents channel descriptions.
        """

        _discriminator_ = CHANNEL_THUMBNAIL

    return ChannelThumbnail

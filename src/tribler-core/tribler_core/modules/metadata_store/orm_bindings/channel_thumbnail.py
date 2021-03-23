from tribler_core.modules.metadata_store.serialization import CHANNEL_THUMBNAIL


def define_binding(db):
    class ChannelThumbnail(db.BinaryNode):
        """
        This ORM class represents channel descriptions.
        """

        _discriminator_ = CHANNEL_THUMBNAIL

    return ChannelThumbnail

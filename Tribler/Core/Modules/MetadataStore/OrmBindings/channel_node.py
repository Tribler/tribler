from pony import orm

from Tribler.Core.Modules.MetadataStore.serialization import CHANNEL_NODE


def define_binding(db):
    class ChannelNode(db.Metadata):
        _discriminator_ = CHANNEL_NODE

        # Local
        parents = orm.Set('ChannelNode', reverse='children')
        children = orm.Set('ChannelNode', reverse='parents')
        origin_id = orm.Optional(int, size=64, default=0)

    return ChannelNode

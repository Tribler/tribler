from pony import orm

from Tribler.Core.Modules.MetadataStore.serialization import CHANNEL_NODE, ChannelNodePayload


def define_binding(db):
    class ChannelNode(db.Metadata):
        _discriminator_ = CHANNEL_NODE

        # Serializable
        id_ = orm.Optional(int, size=64, default=0)
        origin_id = orm.Optional(int, size=64, default=0)

        # Local
        parents = orm.Set('ChannelNode', reverse='children')
        children = orm.Set('ChannelNode', reverse='parents')

        def __init__(self, *args, **kwargs):
            if "id_" not in kwargs:
                kwargs["id_"] = self._clock.tick()
            super(ChannelNode, self).__init__(*args, **kwargs)

        # Special properties
        _payload_class = ChannelNodePayload

    return ChannelNode

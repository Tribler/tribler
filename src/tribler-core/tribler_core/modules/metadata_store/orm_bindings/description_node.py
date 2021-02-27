from pony.orm import Optional

from tribler_core.modules.metadata_store.serialization import DESCRIPTION_NODE, DescriptionNodePayload


def define_binding(db):
    class DescriptionNode(db.ChannelNode):
        """
        This ORM class represents channel descriptions.
        """

        _discriminator_ = DESCRIPTION_NODE

        # Serializable
        text = Optional(str, default="")

        # Special class-level properties
        _payload_class = DescriptionNodePayload
        payload_arguments = _payload_class.__init__.__code__.co_varnames[
            : _payload_class.__init__.__code__.co_argcount
        ][1:]
        nonpersonal_attributes = db.ChannelNode.nonpersonal_attributes + ('text',)

        def to_simple_dict(self):
            simple_dict = super().to_simple_dict()
            simple_dict.update({"text": self.text})

            return simple_dict

    return DescriptionNode

from pony.orm import Optional

from tribler_core.modules.metadata_store.serialization import DESCRIPTION_NODE, DescriptionNodePayload, JSONNODE, \
    JsonNodePayload


def define_binding(db):
    class JsonNode(db.ChannelNode):
        """
        This ORM class represents channel descriptions.
        """

        _discriminator_ = JSONNODE

        # Serializable
        json_text = Optional(str, default="{}")

        # Special class-level properties
        _payload_class = JsonNodePayload
        payload_arguments = _payload_class.__init__.__code__.co_varnames[
                            : _payload_class.__init__.__code__.co_argcount
                            ][1:]
        nonpersonal_attributes = db.ChannelNode.nonpersonal_attributes + ('json_text',)

        def to_simple_dict(self):
            simple_dict = super().to_simple_dict()
            simple_dict.update({"json_text": self.json_text})

            return simple_dict

    return JsonNode

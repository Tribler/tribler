from pony.orm import Optional

from tribler_core.components.metadata_store.db.serialization import JSON_NODE, JsonNodePayload


def define_binding(db, db_version: int):
    class JsonNode(db.ChannelNode):
        """
        This ORM class represents channel descriptions.
        """

        _discriminator_ = JSON_NODE

        # Serializable
        if db_version >= 12:
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

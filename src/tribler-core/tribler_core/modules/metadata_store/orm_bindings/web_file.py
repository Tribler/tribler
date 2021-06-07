from pony import orm

from tribler_core.modules.metadata_store.orm_bindings.channel_node import BROTLI_COMPRESSED_FLAG
from tribler_core.modules.metadata_store.serialization import WEB_FILE, WebFilePayload


def define_binding(db, db_version: int):
    class WebFile(db.BinaryNode, db.MetadataNode):
        """
        This ORM class represents various files that a Web browser is able to show
        """

        _discriminator_ = WEB_FILE

        # Serializable
        if db_version >= 12:
            filename = orm.Optional(str, default='')

        # Special class-level properties
        _payload_class = WebFilePayload
        payload_arguments = _payload_class.__init__.__code__.co_varnames[
            : _payload_class.__init__.__code__.co_argcount
        ][1:]
        nonpersonal_attributes = db.BinaryNode.nonpersonal_attributes + ('title', 'tags', 'filename')

        @property
        def brotli_compressed_flag(self):
            return bool(self.reserved_flags & BROTLI_COMPRESSED_FLAG)

        def to_simple_dict(self):
            simple_dict = super().to_simple_dict()
            simple_dict.update({"filename": self.filename, "brotli_compressed": self.brotli_compressed_flag})

            return simple_dict

    return WebFile

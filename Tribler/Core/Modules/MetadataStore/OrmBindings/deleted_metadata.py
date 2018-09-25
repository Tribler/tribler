from pony import orm

from Tribler.Core.Modules.MetadataStore.OrmBindings.metadata import EMPTY_SIG
from Tribler.Core.Modules.MetadataStore.serialization import MetadataTypes, DeletedMetadataPayload, time2float
from Tribler.pyipv8.ipv8.messaging.serialization import Serializer


def define_binding(db):
    class DeletedMetadata(db.Metadata):
        _discriminator_ = MetadataTypes.DELETED.value
        delete_signature = orm.Required(buffer)

        def serialized(self, signature=True):
            """
            Encode this deleted metadata for transport.
            """
            serializer = Serializer()
            payload = DeletedMetadataPayload(self.type, str(self.public_key), time2float(self.timestamp),
                                             self.tc_pointer, str(self.signature) if signature else EMPTY_SIG,
                                             str(self.delete_signature))
            return serializer.pack_multiple(payload.to_pack_list())[0]

    return DeletedMetadata

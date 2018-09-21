from pony import orm

from Tribler.Core.Modules.MetadataStore.serialization import MetadataTypes


def define_binding(db):
    class DeletedMD(db.SignedGossip):
        _discriminator_ = MetadataTypes.DELETED.value
        delete_signature = orm.Required(buffer)

    return DeletedMD
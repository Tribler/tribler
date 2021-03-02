import hashlib

from pony import orm

import magic


class InvalidHashException(Exception):
    pass


def define_binding(db):
    class BinaryData(db.Entity):
        """
        This binding is used to store read-only binary data, key-value style
        """

        hash = orm.PrimaryKey(bytes)
        data = orm.Optional(bytes)
        content_type = orm.Optional(str)

        def __init__(self, *args, **kwargs):
            data = kwargs["data"]
            calculated_hash = hashlib.sha1(data).digest()
            if "hash" in kwargs and calculated_hash != kwargs["hash"]:
                raise InvalidHashException
            kwargs["hash"] = calculated_hash
            kwargs["content_type"] = magic.from_buffer(data, mime=True)
            super().__init__(*args, **kwargs)

    return BinaryData

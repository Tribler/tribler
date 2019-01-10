from __future__ import absolute_import

from binascii import hexlify
from datetime import datetime

from pony import orm
from pony.orm import db_session, select, desc

from Tribler.Core.Modules.MetadataStore.serialization import MetadataPayload, DeletedMetadataPayload, TYPELESS, DELETED
from Tribler.Core.exceptions import InvalidSignatureException
from Tribler.pyipv8.ipv8.database import database_blob
from Tribler.pyipv8.ipv8.keyvault.crypto import default_eccrypto

# Metadata, torrents and channel statuses
NEW = 0
TODELETE = 1
COMMITTED = 2
JUST_RECEIVED = 3
UPDATE_AVAILABLE = 4
PREVIEW_UPDATE_AVAILABLE = 5
LEGACY_ENTRY = 6

PUBLIC_KEY_LEN = 64


def define_binding(db):
    class Metadata(db.Entity):
        _discriminator_ = TYPELESS

        # Serializable
        metadata_type = orm.Discriminator(int)
        # We want to make signature unique=True for safety, but can't do it in Python2 because of Pony bug #390
        signature = orm.Optional(database_blob)
        public_key = orm.Optional(database_blob, default='\x00' * PUBLIC_KEY_LEN)

        # Local
        rowid = orm.PrimaryKey(int, auto=True)
        addition_timestamp = orm.Optional(datetime, default=datetime.utcnow)
        status = orm.Optional(int, default=COMMITTED)

        # Special properties
        _payload_class = MetadataPayload
        _my_key = None
        _logger = None
        _clock = None

        def __init__(self, *args, **kwargs):
            """
            Initialize a metadata object.

            Note: this is a way to manually define Pony entity default attributes in case we really
            have to generate the signature before creating the object
            from pony.orm.core import DEFAULT
            def generate_dict_from_pony_args(cls, **kwargs):
                d = {}
                for attr in cls._attrs_:
                    val = kwargs.get(attr.name, DEFAULT)
                    d[attr.name] = attr.validate(val, entity=cls)
                return d
            """

            # Special "sign_with" argument given, sign with it
            private_key_override = None
            if "sign_with" in kwargs:
                kwargs["public_key"] = database_blob(kwargs["sign_with"].pub().key_to_bin()[10:])
                private_key_override = kwargs["sign_with"]
                kwargs.pop("sign_with")

            # FIXME: potential race condition here? To avoid it, generate the signature _before_ calling "super"
            super(Metadata, self).__init__(*args, **kwargs)

            if private_key_override:
                self.sign(private_key_override)
                return
            # No key/signature given, sign with our own key.
            elif ("signature" not in kwargs) and \
                    (("public_key" not in kwargs) or (
                            kwargs["public_key"] == database_blob(self._my_key.pub().key_to_bin()[10:]))):
                self.sign(self._my_key)
                return

            # Key/signature given, check them for correctness
            elif ("public_key" in kwargs) and ("signature" in kwargs) and self.has_valid_signature():
                return

            # Otherwise, something is wrong
            raise InvalidSignatureException(
                ("Attempted to create %s object with invalid signature/PK: " % str(self.__class__.__name__)) +
                (hexlify(self.signature) if self.signature else "empty signature ") + " / " +
                (hexlify(self.public_key) if self.public_key else " empty PK"))

        def _serialized(self, key=None):
            """
            Serializes the object and returns the result with added signature (tuple output)
            :param key: private key to sign object with
            :return: (serialized_data, signature) tuple
            """
            return self._payload_class(**self.to_dict())._serialized(key)

        def serialized(self, key=None):
            """
            Serializes the object and returns the result with added signature (blob output)
            :param key: private key to sign object with
            :return: serialized_data+signature binary string
            """
            return ''.join(self._serialized(key))

        def _serialized_delete(self):
            """
            Create a special command to delete this metadata and encode it for transfer (tuple output).
            :return: (serialized_data, signature) tuple
            """
            my_dict = Metadata.to_dict(self)
            my_dict.update({"metadata_type": DELETED,
                            "delete_signature": self.signature})
            return DeletedMetadataPayload(**my_dict)._serialized(self._my_key)

        def serialized_delete(self):
            """
            Create a special command to delete this metadata and encode it for transfer (blob output).
            :return: serialized_data+signature binary string
            """
            return ''.join(self._serialized_delete())

        def to_file(self, filename, key=None):
            with open(filename, 'wb') as output_file:
                output_file.write(self.serialized(key))

        def to_delete_file(self, filename):
            with open(filename, 'wb') as output_file:
                output_file.write(self.serialized_delete())

        def sign(self, key=None):
            if not key:
                key = self._my_key
            self.public_key = database_blob(key.pub().key_to_bin()[10:])
            _, self.signature = self._serialized(key)

        def has_valid_signature(self):
            crypto = default_eccrypto
            return (crypto.is_valid_public_bin(b"LibNaCLPK:" + str(self.public_key))
                    and self._payload_class(**self.to_dict()).has_valid_signature())

        @classmethod
        def from_payload(cls, payload):
            return cls(**payload.to_dict())

        @classmethod
        def from_dict(cls, dct):
            return cls(**dct)

        @classmethod
        @db_session
        def get_entries_query(cls, metadata_type, sort_by=None, sort_asc=True, query_filter=None):
            """
            Get some metadata entries. Optionally sort the results by a specific field, or filter the channels based
            on a keyword/whether you are subscribed to it.
            :return: A tuple. The first entry is a list of ChannelMetadata entries. The second entry indicates
                     the total number of results, regardless the passed first/last parameter.
            """
            # Warning! For Pony magic to work, iteration variable name (e.g. 'g') should be the same everywhere!
            pony_query = select(g for g in metadata_type)

            # Filter the results on a keyword or some keywords
            if query_filter:
                pony_query = metadata_type.search_keyword(query_filter + "*", lim=1000)

            # Sort the query
            if sort_by:
                sort_expression = "g." + sort_by
                sort_expression = sort_expression if sort_asc else desc(sort_expression)
                pony_query = pony_query.sort_by(sort_expression)

            return pony_query

    return Metadata

from __future__ import absolute_import

from binascii import hexlify
from datetime import datetime

from pony import orm
from pony.orm import db_session, select, desc
from pony.orm.core import DEFAULT

from Tribler.Core.Modules.MetadataStore.serialization import DeletedMetadataPayload, DELETED, \
    ChannelNodePayload, CHANNEL_NODE
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


def generate_dict_from_pony_args(cls, skip_list=None, **kwargs):
    """
    Note: this is a way to manually define Pony entity default attributes in case we really
    have to generate the signature before creating the object
    """
    d = {}
    skip_list = skip_list or []
    for attr in cls._attrs_:
        val = kwargs.get(attr.name, DEFAULT)
        if attr.name in skip_list:
            continue
        d[attr.name] = attr.validate(val, entity=cls)
    return d


def define_binding(db):
    class ChannelNode(db.Entity):
        _discriminator_ = CHANNEL_NODE

        rowid = orm.PrimaryKey(int, size=64, auto=True)

        # Serializable
        metadata_type = orm.Discriminator(int, size=16)
        reserved_flags = orm.Optional(int, size=16, default=0)
        origin_id = orm.Optional(int, size=64, default=0)

        public_key = orm.Required(database_blob)
        id_ = orm.Required(int, size=64)
        orm.composite_index(public_key, id_)

        timestamp = orm.Required(int, size=64, default=0)
        signature = orm.Required(database_blob, unique=True)

        # Local
        added_on = orm.Optional(datetime, default=datetime.utcnow)
        status = orm.Optional(int, default=COMMITTED)

        parents = orm.Set('ChannelNode', reverse='children')
        children = orm.Set('ChannelNode', reverse='parents')

        # Special properties
        _payload_class = ChannelNodePayload
        _my_key = None
        _logger = None
        _clock = None

        def __init__(self, *args, **kwargs):
            """
            Initialize a metadata object.
            All this dance is required to ensure that the signature is there and it is correct.
            """

            # Process special keyworded arguments
            # "sign_with" argument given, sign with it
            private_key_override = None
            if "sign_with" in kwargs:
                kwargs["public_key"] = database_blob(kwargs["sign_with"].pub().key_to_bin()[10:])
                private_key_override = kwargs["sign_with"]
                kwargs.pop("sign_with")

            # For putting legacy/test stuff in
            skip_key_check = False
            if "skip_key_check" in kwargs and kwargs["skip_key_check"]:
                skip_key_check = True
                kwargs.pop("skip_key_check")

            if "id_" not in kwargs:
                kwargs["id_"] = self._clock.tick()

            if not private_key_override and not skip_key_check:
                # No key/signature given, sign with our own key.
                if ("signature" not in kwargs) and \
                        (("public_key" not in kwargs) or (
                                kwargs["public_key"] == database_blob(self._my_key.pub().key_to_bin()[10:]))):
                    private_key_override = self._my_key

                # Key/signature given, check them for correctness
                elif ("public_key" in kwargs) and ("signature" in kwargs):
                    try:
                        self._payload_class(**kwargs)
                    except InvalidSignatureException:
                        raise InvalidSignatureException(
                            ("Attempted to create %s object with invalid signature/PK: " % str(
                                self.__class__.__name__)) +
                            (hexlify(kwargs["signature"]) if "signature" in kwargs else "empty signature ") + " / " +
                            (hexlify(kwargs["public_key"]) if "public_key" in kwargs else " empty PK"))

            if private_key_override:
                # Get default values for Pony class attributes. We have to do it manually because we need
                # to know the payload signature *before* creating the object.
                kwargs = generate_dict_from_pony_args(self.__class__, skip_list=["signature", "public_key"], **kwargs)
                payload = self._payload_class(
                    **dict(kwargs,
                           public_key=str(private_key_override.pub().key_to_bin()[10:]),
                           key=private_key_override,
                           metadata_type=self.metadata_type))
                kwargs["public_key"] = payload.public_key
                kwargs["signature"] = payload.signature

            super(ChannelNode, self).__init__(*args, **kwargs)

        def _serialized(self, key=None):
            """
            Serializes the object and returns the result with added signature (tuple output)
            :param key: private key to sign object with
            :return: (serialized_data, signature) tuple
            """
            return self._payload_class(key=key, **self.to_dict())._serialized()

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
            my_dict = ChannelNode.to_dict(self)
            my_dict.update({"metadata_type": DELETED,
                            "delete_signature": self.signature})
            return DeletedMetadataPayload(key=self._my_key, **my_dict)._serialized()

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
            signature_correct = False
            key_correct = crypto.is_valid_public_bin(b"LibNaCLPK:" + str(self.public_key))

            if key_correct:
                try:
                    self._payload_class(**self.to_dict())
                except InvalidSignatureException:
                    signature_correct = False
                else:
                    signature_correct = True

            return key_correct and signature_correct

        @classmethod
        def from_payload(cls, payload):
            return cls(**payload.to_dict())

        @classmethod
        def from_dict(cls, dct):
            return cls(**dct)

        @classmethod
        @db_session
        def get_entries_query(cls, sort_by=None, sort_asc=True, query_filter=None):
            """
            Get some metadata entries. Optionally sort the results by a specific field, or filter the channels based
            on a keyword/whether you are subscribed to it.
            :return: A tuple. The first entry is a list of ChannelMetadata entries. The second entry indicates
                     the total number of results, regardless the passed first/last parameter.
            """
            # Warning! For Pony magic to work, iteration variable name (e.g. 'g') should be the same everywhere!
            pony_query = select(g for g in cls)

            # Filter the results on a keyword or some keywords
            if query_filter:
                pony_query = cls.search_keyword(query_filter + "*", lim=1000)

            # Sort the query
            if sort_by:
                sort_expression = "g." + sort_by
                sort_expression = sort_expression if sort_asc else desc(sort_expression)
                pony_query = pony_query.sort_by(sort_expression)

            return pony_query

    return ChannelNode

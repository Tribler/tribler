from __future__ import absolute_import

from binascii import hexlify
from datetime import datetime

from pony import orm
from pony.orm.core import DEFAULT

from Tribler.Core.Modules.MetadataStore.serialization import (
    CHANNEL_NODE, DELETED, EMPTY_KEY, ChannelNodePayload, DeletedMetadataPayload)
from Tribler.Core.exceptions import InvalidChannelNodeException, InvalidSignatureException

from ipv8.database import database_blob
from ipv8.keyvault.crypto import default_eccrypto

# Metadata, torrents and channel statuses
NEW = 0  # The entry is newly created and is not published yet. It will be committed at the next commit.
TODELETE = 1  # The entry is marked to be removed at the next commit.
COMMITTED = 2  # The entry is committed and seeded.
UPDATED = 6  # One of the entry's properties was updated. It will be committed at the next commit.
LEGACY_ENTRY = 1000  # The entry was converted from the old Tribler DB. It has no signature and should not be shared.

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


def define_binding(db, logger=None, key=None, clock=None):
    class ChannelNode(db.Entity):
        _discriminator_ = CHANNEL_NODE

        rowid = orm.PrimaryKey(int, size=64, auto=True)

        # Serializable
        metadata_type = orm.Discriminator(int, size=16)
        reserved_flags = orm.Optional(int, size=16, default=0)
        origin_id = orm.Optional(int, size=64, default=0)

        public_key = orm.Required(database_blob)
        id_ = orm.Required(int, size=64)
        orm.composite_key(public_key, id_)

        timestamp = orm.Required(int, size=64, default=0)
        # Signature is nullable. This means that "None" entries are stored in DB as NULLs instead of empty strings.
        # NULLs are not checked for uniqueness and not indexed.
        # This is necessary to store unsigned signatures without violating the uniqueness constraints.
        signature = orm.Optional(database_blob, unique=True, nullable=True, default=None)

        # Local
        added_on = orm.Optional(datetime, default=datetime.utcnow)
        status = orm.Optional(int, default=COMMITTED)

        # Special properties
        _payload_class = ChannelNodePayload
        _my_key = key
        _logger = logger
        _clock = clock

        def __init__(self, *args, **kwargs):
            """
            Initialize a metadata object.
            All this dance is required to ensure that the signature is there and it is correct.
            """
            skip_key_check = False

            # FIXME: refactor this method by moving different ways to create an entry into separate methods

            # Process special keyworded arguments
            # "sign_with" argument given, sign with it
            private_key_override = None
            if "sign_with" in kwargs:
                kwargs["public_key"] = database_blob(kwargs["sign_with"].pub().key_to_bin()[10:])
                private_key_override = kwargs.pop("sign_with")

            # Free-for-all entries require special treatment
            if "public_key" in kwargs and kwargs["public_key"] == "":
                # We have to give the entry an unique sig to honor the DB constraints. We use the entry's id_
                # as the sig to keep it unique and short. The uniqueness is guaranteed by DB as it already
                # imposes uniqueness constraints on the id_+public_key combination.
                if "id_" in kwargs:
                    kwargs["signature"] = None
                    skip_key_check = True
                else:
                    # Trying to create an FFA entry without specifying the id_ should be considered an error,
                    # because assigning id_ automatically by _clock breaks anonymity.
                    # FFA entries should be "timeless" and anonymous.
                    raise InvalidChannelNodeException(
                        ("Attempted to create %s free-for-all (unsigned) object without specifying id_ : " %
                         str(self.__class__.__name__)))

            # For putting legacy/test stuff in
            skip_key_check = kwargs.pop("skip_key_check", skip_key_check)

            if "id_" not in kwargs:
                kwargs["id_"] = self._clock.tick()

            if "timestamp" not in kwargs:
                kwargs["timestamp"] = kwargs["id_"]

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
            return self._payload_class(key=key, unsigned=(self.signature==None), **self.to_dict())._serialized()

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

    return ChannelNode

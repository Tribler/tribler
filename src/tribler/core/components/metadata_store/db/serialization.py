from __future__ import annotations

import struct
from datetime import datetime, timedelta
from typing import List, Tuple

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.messaging.lazy_payload import VariablePayload, vp_compile
from ipv8.messaging.payload import Payload
from ipv8.messaging.serialization import default_serializer

from tribler_core.exceptions import InvalidSignatureException
from tribler_core.utilities.unicode import hexlify

EPOCH = datetime(1970, 1, 1)

SIGNATURE_SIZE = 64
NULL_SIG = b'\x00' * 64
NULL_KEY = b'\x00' * 64

# Metadata types. Should have been an enum, but in Python its unwieldy.
TYPELESS = 100
CHANNEL_NODE = 200
METADATA_NODE = 210
COLLECTION_NODE = 220
JSON_NODE = 230
CHANNEL_DESCRIPTION = 231
BINARY_NODE = 240
CHANNEL_THUMBNAIL = 241
REGULAR_TORRENT = 300
CHANNEL_TORRENT = 400
DELETED = 500


def time2int(date_time, epoch=EPOCH):
    """
    Convert a datetime object to an int .
    :param date_time: The datetime object to convert.
    :param epoch: The epoch time, defaults to Jan 1, 1970.
    :return: The int representation of date_time.

    WARNING: TZ-aware timestamps are madhouse...
    """

    return int((date_time - epoch).total_seconds())


def int2time(timestamp, epoch=EPOCH):
    """
    Convert an int into a datetime object.
    :param timestamp: The timestamp to be converted.
    :param epoch: The epoch time, defaults to Jan 1, 1970.
    :return: The datetime representation of timestamp.
    """
    return epoch + timedelta(seconds=timestamp)


class KeysMismatchException(Exception):
    pass


class UnknownBlobTypeException(Exception):
    pass


def read_payload_with_offset(data, offset=0):
    # First we have to determine the actual payload type
    metadata_type = struct.unpack_from('>H', data, offset=offset)[0]
    payload_class = DISCRIMINATOR_TO_PAYLOAD_CLASS.get(metadata_type)
    if payload_class is not None:
        return payload_class.from_signed_blob_with_offset(data, offset=offset)

    # Unknown metadata type, raise exception
    raise UnknownBlobTypeException


class SignedPayload(Payload):
    """
    Payload for metadata.
    """

    format_list = ['H', 'H', '64s']

    def __init__(self, metadata_type, reserved_flags, public_key, **kwargs):
        super().__init__()
        self.metadata_type = metadata_type
        self.reserved_flags = reserved_flags
        self.public_key = bytes(public_key)
        self.signature = bytes(kwargs["signature"]) if "signature" in kwargs and kwargs["signature"] else None

        # Special case: free-for-all entries are allowed to go with zero key and without sig check
        if "unsigned" in kwargs and kwargs["unsigned"]:
            self.public_key = NULL_KEY
            self.signature = NULL_SIG
            return

        if "skip_key_check" in kwargs and kwargs["skip_key_check"]:
            return

        # This is integrity check for FFA payloads.
        if self.public_key == NULL_KEY:
            if self.signature == NULL_SIG:
                return
            raise InvalidSignatureException("Tried to create FFA payload with non-null signature")

        serialized_data = default_serializer.pack_serializable(self)
        if "key" in kwargs and kwargs["key"]:
            key = kwargs["key"]
            if self.public_key != key.pub().key_to_bin()[10:]:
                raise KeysMismatchException(self.public_key, key.pub().key_to_bin()[10:])
            self.signature = default_eccrypto.create_signature(key, serialized_data)
        elif "signature" in kwargs:
            # This check ensures that an entry with a wrong signature will not proliferate further
            if not default_eccrypto.is_valid_signature(
                default_eccrypto.key_from_public_bin(b"LibNaCLPK:" + self.public_key), serialized_data, self.signature
            ):
                raise InvalidSignatureException("Tried to create payload with wrong signature")
        else:
            raise InvalidSignatureException("Tried to create payload without signature")

    def to_pack_list(self):
        data = [('H', self.metadata_type), ('H', self.reserved_flags), ('64s', self.public_key)]
        return data

    @classmethod
    def from_unpack_list(cls, metadata_type, reserved_flags, public_key, **kwargs):  # pylint: disable=W0221
        return SignedPayload(metadata_type, reserved_flags, public_key, **kwargs)

    @classmethod
    def from_signed_blob(cls, data, check_signature=True):
        return cls.from_signed_blob_with_offset(data, check_signature)[0]

    @classmethod
    def from_signed_blob_with_offset(cls, data, check_signature=True, offset=0):
        unpack_list = []
        for format_str in cls.format_list:
            offset = default_serializer.get_packer_for(format_str).unpack(data, offset, unpack_list)
        if check_signature:
            signature = data[offset: offset + SIGNATURE_SIZE]
            payload = cls.from_unpack_list(*unpack_list, signature=signature)  # pylint: disable=E1120
        else:
            payload = cls.from_unpack_list(*unpack_list, skip_key_check=True)  # pylint: disable=E1120
        return payload, offset + SIGNATURE_SIZE

    def to_dict(self):
        return {
            "metadata_type": self.metadata_type,
            "reserved_flags": self.reserved_flags,
            "public_key": self.public_key,
            "signature": self.signature,
        }

    def _serialized(self):
        serialized_data = default_serializer.pack_serializable(self)
        return serialized_data, self.signature

    def serialized(self):
        return b''.join(self._serialized())

    @classmethod
    def from_file(cls, filepath):
        with open(filepath, 'rb') as f:
            return cls.from_signed_blob(f.read())


# fmt: off
class ChannelNodePayload(SignedPayload):
    format_list = SignedPayload.format_list + ['Q', 'Q', 'Q']

    def __init__(
            self,
            metadata_type, reserved_flags, public_key,  # SignedPayload
            id_, origin_id, timestamp,                  # ChannelNodePayload
            **kwargs):
        self.id_ = id_
        self.origin_id = origin_id
        self.timestamp = timestamp
        super().__init__(
            metadata_type, reserved_flags, public_key,  # SignedPayload
            **kwargs)

    def to_pack_list(self):
        data = super().to_pack_list()
        data.append(('Q', self.id_))
        data.append(('Q', self.origin_id))
        data.append(('Q', self.timestamp))
        return data

    @classmethod
    def from_unpack_list( # pylint: disable=arguments-differ
            cls,
            metadata_type, reserved_flags, public_key,  # SignedPayload
            id_, origin_id, timestamp,                  # ChannelNodePayload
            **kwargs):
        return ChannelNodePayload(
            metadata_type, reserved_flags, public_key,  # SignedPayload
            id_, origin_id, timestamp,                  # ChannelNodePayload
            **kwargs)

    def to_dict(self):
        dct = super().to_dict()
        dct.update(
            {"id_": self.id_,
             "origin_id": self.origin_id,
             "timestamp": self.timestamp
             })
        return dct


class JsonNodePayload(ChannelNodePayload):
    format_list = ChannelNodePayload.format_list + ['varlenI']

    def __init__(
            self,
            metadata_type, reserved_flags, public_key,  # SignedPayload
            id_, origin_id, timestamp,                  # ChannelNodePayload
            json_text,                                  # JsonNodePayload
            **kwargs):
        self.json_text = json_text.decode('utf-8') if isinstance(json_text, bytes) else json_text
        super().__init__(
            metadata_type, reserved_flags, public_key,  # SignedPayload
            id_, origin_id, timestamp,                  # ChannelNodePayload
            **kwargs
        )

    def to_pack_list(self):
        data = super().to_pack_list()
        data.append(('varlenI', self.json_text.encode('utf-8')))
        return data

    @classmethod
    def from_unpack_list( # pylint: disable=arguments-differ
            cls,
            metadata_type, reserved_flags, public_key,  # SignedPayload
            id_, origin_id, timestamp,                  # ChannelNodePayload
            json_text,                                  # JsonNodePayload
            **kwargs
    ):
        return cls(
            metadata_type, reserved_flags, public_key,  # SignedPayload
            id_, origin_id, timestamp,                  # ChannelNodePayload
            json_text,                                  # JsonNodePayload
            **kwargs
        )

    def to_dict(self):
        dct = super().to_dict()
        dct.update({"json_text": self.json_text})
        return dct


class BinaryNodePayload(ChannelNodePayload):
    format_list = ChannelNodePayload.format_list + ['varlenI', 'varlenI']

    def __init__(
            self,
            metadata_type, reserved_flags, public_key,  # SignedPayload
            id_, origin_id, timestamp,                  # ChannelNodePayload
            binary_data, data_type,                     # BinaryNodePayload
            **kwargs):
        self.binary_data = binary_data
        self.data_type = data_type.decode('utf-8') if isinstance(data_type, bytes) else data_type
        super().__init__(
            metadata_type, reserved_flags, public_key,  # SignedPayload
            id_, origin_id, timestamp,                  # ChannelNodePayload
            **kwargs
        )

    def to_pack_list(self):
        data = super().to_pack_list()
        data.append(('varlenI', self.binary_data))
        data.append(('varlenI', self.data_type.encode('utf-8')))
        return data

    @classmethod
    def from_unpack_list( # pylint: disable=arguments-differ
            cls,
            metadata_type, reserved_flags, public_key,  # SignedPayload
            id_, origin_id, timestamp,                  # ChannelNodePayload
            binary_data, data_type,                     # BinaryNodePayload
            **kwargs
    ):
        return cls(
            metadata_type, reserved_flags, public_key,  # SignedPayload
            id_, origin_id, timestamp,                  # ChannelNodePayload
            binary_data, data_type,                     # BinaryNodePayload
            **kwargs
        )

    def to_dict(self):
        dct = super().to_dict()
        dct.update({"binary_data": self.binary_data})
        dct.update({"data_type": self.data_type})
        return dct


class MetadataNodePayload(ChannelNodePayload):

    format_list = ChannelNodePayload.format_list + ['varlenI', 'varlenI']

    def __init__(
            self,
            metadata_type, reserved_flags, public_key,  # SignedPayload
            id_, origin_id, timestamp,                  # ChannelNodePayload
            title, tags,                                # MetadataNodePayload
            **kwargs):
        self.title = title.decode('utf-8') if isinstance(title, bytes) else title
        self.tags = tags.decode('utf-8') if isinstance(tags, bytes) else tags
        super().__init__(
            metadata_type, reserved_flags, public_key,  # SignedPayload
            id_, origin_id, timestamp,                  # ChannelNodePayload
            **kwargs
        )

    def to_pack_list(self):
        data = super().to_pack_list()
        data.append(('varlenI', self.title.encode('utf-8')))
        data.append(('varlenI', self.tags.encode('utf-8')))
        return data

    @classmethod
    def from_unpack_list( # pylint: disable=arguments-differ
        cls,
        metadata_type, reserved_flags, public_key,      # SignedPayload
        id_, origin_id, timestamp,                      # ChannelNodePayload
        title, tags,                                    # MetadataNodePayload
        **kwargs
    ):
        return MetadataNodePayload(
            metadata_type, reserved_flags, public_key,  # SignedPayload
            id_, origin_id, timestamp,                  # ChannelNodePayload
            title, tags,                                # MetadataNodePayload
            **kwargs
        )

    def to_dict(self):
        dct = super().to_dict()
        dct.update(
            {"title": self.title,
             "tags": self.tags})
        return dct


class CollectionNodePayload(MetadataNodePayload):
    """
    Payload for metadata that stores a collection
    """

    format_list = MetadataNodePayload.format_list + ['Q']

    def __init__(
            self,
            metadata_type, reserved_flags, public_key,  # SignedPayload
            id_, origin_id, timestamp,                  # ChannelNodePayload
            title, tags,                                # MetadataNodePayload
            num_entries,                                # CollectionNodePayload
            **kwargs
    ):
        self.num_entries = num_entries
        super().__init__(
            metadata_type, reserved_flags, public_key,  # SignedPayload
            id_, origin_id, timestamp,                  # ChannelNodePayload
            title, tags,                                # MetadataNodePayload
            **kwargs
        )

    def to_pack_list(self):
        data = super().to_pack_list()
        data.append(('Q', self.num_entries))
        return data

    @classmethod
    def from_unpack_list( # pylint: disable=arguments-differ
            cls,
            metadata_type, reserved_flags, public_key,  # SignedPayload
            id_, origin_id, timestamp,                  # ChannelNodePayload
            title, tags,                                # MetadataNodePayload
            num_entries,                                # CollectionNodePayload
            **kwargs
    ):
        return CollectionNodePayload(
            metadata_type, reserved_flags, public_key,  # SignedPayload
            id_, origin_id, timestamp,                  # ChannelNodePayload
            title, tags,                                # MetadataNodePayload
            num_entries,                                # CollectionNodePayload
            **kwargs
        )

    def to_dict(self):
        dct = super().to_dict()
        dct.update({"num_entries": self.num_entries})
        return dct


class TorrentMetadataPayload(ChannelNodePayload):
    """
    Payload for metadata that stores a torrent.
    """

    format_list = ChannelNodePayload.format_list + ['20s', 'Q', 'I', 'varlenI', 'varlenI', 'varlenI']

    def __init__(
            self,
            metadata_type, reserved_flags, public_key,                # SignedPayload
            id_, origin_id, timestamp,                                # ChannelNodePayload
            infohash, size, torrent_date, title, tags, tracker_info,  # TorrentMetadataPayload
            **kwargs):
        self.infohash = bytes(infohash)
        self.size = size
        self.torrent_date = time2int(torrent_date) if isinstance(torrent_date, datetime) else torrent_date
        self.title = title.decode('utf-8') if isinstance(title, bytes) else title
        self.tags = tags.decode('utf-8') if isinstance(tags, bytes) else tags
        self.tracker_info = tracker_info.decode('utf-8') if isinstance(tracker_info, bytes) else tracker_info
        super().__init__(
            metadata_type, reserved_flags, public_key,  # SignedPayload
            id_, origin_id, timestamp,  # ChannelNodePayload
            **kwargs
        )

    def to_pack_list(self):
        data = super().to_pack_list()
        data.append(('20s', self.infohash))
        data.append(('Q', self.size))
        data.append(('I', self.torrent_date))
        data.append(('varlenI', self.title.encode('utf-8')))
        data.append(('varlenI', self.tags.encode('utf-8')))
        data.append(('varlenI', self.tracker_info.encode('utf-8')))
        return data

    @classmethod
    def from_unpack_list( # pylint: disable=arguments-differ
            cls,
            metadata_type, reserved_flags, public_key,                # SignedPayload
            id_, origin_id, timestamp,                                # ChannelNodePayload
            infohash, size, torrent_date, title, tags, tracker_info,  # TorrentMetadataPayload
            **kwargs):
        return TorrentMetadataPayload(
            metadata_type, reserved_flags, public_key,                # SignedPayload
            id_, origin_id, timestamp,                                # ChannelNodePayload
            infohash, size, torrent_date, title, tags, tracker_info,  # TorrentMetadataPayload
            **kwargs)

    def to_dict(self):
        dct = super().to_dict()
        dct.update(
            {
                "infohash": self.infohash,
                "size": self.size,
                "torrent_date": int2time(self.torrent_date),
                "title": self.title,
                "tags": self.tags,
                "tracker_info": self.tracker_info,
            }
        )
        return dct

    def get_magnet(self):
        return (f"magnet:?xt=urn:btih:{hexlify(self.infohash)}&dn={self.title.encode('utf8')}") + (
            f"&tr={self.tracker_info.encode('utf8')}" if self.tracker_info else ""
        )


class ChannelMetadataPayload(TorrentMetadataPayload):
    """
    Payload for metadata that stores a channel.
    """

    format_list = TorrentMetadataPayload.format_list + ['Q'] + ['Q']

    def __init__(
            self,
            metadata_type, reserved_flags, public_key,                # SignedPayload
            id_, origin_id, timestamp,                                # ChannelNodePayload
            infohash, size, torrent_date, title, tags, tracker_info,  # TorrentMetadataPayload
            num_entries, start_timestamp,                             # ChannelMetadataPayload
            **kwargs):
        self.num_entries = num_entries
        self.start_timestamp = start_timestamp
        super().__init__(
            metadata_type, reserved_flags, public_key,                 # SignedPayload
            id_, origin_id, timestamp,                                 # ChannelNodePayload
            infohash, size, torrent_date, title, tags, tracker_info,   # TorrentMetadataPayload
            **kwargs)

    def to_pack_list(self):
        data = super().to_pack_list()
        data.append(('Q', self.num_entries))
        data.append(('Q', self.start_timestamp))
        return data

    @classmethod
    def from_unpack_list( # pylint: disable=arguments-differ
            cls,
            metadata_type, reserved_flags, public_key,                # SignedPayload
            id_, origin_id, timestamp,                                # ChannelNodePayload
            infohash, size, torrent_date, title, tags, tracker_info,  # TorrentMetadataPayload
            num_entries, start_timestamp,                             # ChannelMetadataPayload
            **kwargs):
        return ChannelMetadataPayload(
            metadata_type, reserved_flags, public_key,                # SignedPayload
            id_, origin_id, timestamp,                                # ChannelNodePayload
            infohash, size, torrent_date, title, tags, tracker_info,  # TorrentMetadataPayload
            num_entries, start_timestamp,                             # ChannelMetadataPayload
            **kwargs)

    def to_dict(self):
        dct = super().to_dict()
        dct.update({
            "num_entries": self.num_entries,
            "start_timestamp": self.start_timestamp
        })
        return dct


class DeletedMetadataPayload(SignedPayload):
    """
    Payload for metadata that stores deleted metadata.
    """

    format_list = SignedPayload.format_list + ['64s']

    def __init__(
            self,
            metadata_type, reserved_flags, public_key,  # SignedPayload
            delete_signature,                           # DeletedMetadataPayload
            **kwargs):
        self.delete_signature = bytes(delete_signature)
        super().__init__(
            metadata_type, reserved_flags, public_key,  # SignedPayload
            **kwargs)

    def to_pack_list(self):
        data = super().to_pack_list()
        data.append(('64s', self.delete_signature))
        return data

    @classmethod
    def from_unpack_list( # pylint: disable=arguments-differ
            cls,
            metadata_type, reserved_flags, public_key,  # SignedPayload
            delete_signature,                           # DeletedMetadataPayload
            **kwargs):
        return DeletedMetadataPayload(
            metadata_type, reserved_flags, public_key,  # SignedPayload
            delete_signature,                           # DeletedMetadataPayload
            **kwargs)

    def to_dict(self):
        dct = super().to_dict()
        dct.update({"delete_signature": self.delete_signature})
        return dct
# fmt: on


DISCRIMINATOR_TO_PAYLOAD_CLASS = {
    REGULAR_TORRENT: TorrentMetadataPayload,
    CHANNEL_TORRENT: ChannelMetadataPayload,
    COLLECTION_NODE: CollectionNodePayload,
    CHANNEL_THUMBNAIL: BinaryNodePayload,
    CHANNEL_DESCRIPTION: JsonNodePayload,
    DELETED: DeletedMetadataPayload,
}


@vp_compile
class HealthItemsPayload(VariablePayload):
    """
    Payload for health item information. See the details of binary format in MetadataCompressor class description.
    """

    format_list = ['varlenI']
    names = ['data']

    def serialize(self):
        return default_serializer.pack_serializable(self)

    @classmethod
    def unpack(cls, data) -> List[Tuple[int, int, int]]:
        data = default_serializer.unpack_serializable(cls, data)[0].data
        items = data.split(b';')[:-1]
        return [cls.parse_health_data_item(item) for item in items]

    @classmethod
    def parse_health_data_item(cls, item: bytes) -> Tuple[int, int, int]:
        if not item:
            return 0, 0, 0

        # The format is forward-compatible: currently only three first elements of data are used,
        # and later it is possible to add more fields without breaking old clients
        try:
            seeders, leechers, last_check = map(int, item.split(b',')[:3])
        except:  # pylint: disable=bare-except
            return 0, 0, 0

        # Safety check: seelders, leechers and last_check values cannot be negative
        if seeders < 0 or leechers < 0 or last_check < 0:
            return 0, 0, 0

        return seeders, leechers, last_check

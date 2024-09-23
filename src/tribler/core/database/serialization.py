from __future__ import annotations

import struct
from binascii import hexlify
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.messaging.lazy_payload import VariablePayload, vp_compile
from ipv8.messaging.serialization import VarLenUtf8, default_serializer
from typing_extensions import Self

if TYPE_CHECKING:
    from ipv8.types import PrivateKey

default_serializer.add_packer("varlenIutf8", VarLenUtf8(">I"))
EPOCH = datetime(1970, 1, 1)  # noqa: DTZ001

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
SNIPPET = 600


def time2int(date_time: datetime, epoch: datetime = EPOCH) -> int:
    """
    Convert a datetime object to an int.

    :param date_time: The datetime object to convert.
    :param epoch: The epoch time, defaults to Jan 1, 1970.
    :return: The int representation of date_time.

    WARNING: TZ-aware timestamps are madhouse...
    """
    return int((date_time - epoch).total_seconds())


def int2time(timestamp: int, epoch: datetime = EPOCH) -> datetime:
    """
    Convert an int into a datetime object.

    :param timestamp: The timestamp to be converted.
    :param epoch: The epoch time, defaults to Jan 1, 1970.
    :return: The datetime representation of timestamp.
    """
    return epoch + timedelta(seconds=timestamp)


class UnknownBlobTypeException(Exception):
    """
    A block was received with an unknown blob type.

    We only support type:

        - 300, REGULAR_TORRENT
    """


def read_payload_with_offset(data: bytes, offset: int = 0) -> tuple[TorrentMetadataPayload, int]:
    """
    Read the next payload from the data buffer (at the given offset).
    """
    # First we have to determine the actual payload type
    metadata_type = struct.unpack_from('>H', data, offset=offset)[0]
    payload_class = METADATA_TYPE_TO_PAYLOAD_CLASS.get(metadata_type)
    if payload_class is not None:
        payload, offset = default_serializer.unpack_serializable(payload_class, data, offset=offset)
        payload.signature = data[offset: offset + 64]
        return payload, offset + 64

    # Unknown metadata type, raise exception
    raise UnknownBlobTypeException


@vp_compile
class SignedPayload(VariablePayload):
    """
    A payload that captures a public key and metadata type and supports adding a signature over its contents.

    This payload can be extended to allow more data to be signed.
    """

    names = ["metadata_type", "reserved_flags", "public_key"]
    format_list = ["H", "H", "64s"]

    signature: bytes = NULL_SIG
    metadata_type: int
    reserved_flags: int
    public_key: bytes

    def serialized(self) -> bytes:
        """
        Pack this serializable.
        """
        return default_serializer.pack_serializable(self)

    @classmethod
    def from_signed_blob(cls: type[Self], serialized: bytes) -> Self:
        """
        Read a SignedPayload from the given serialized form.
        """
        payload, offset = default_serializer.unpack_serializable(cls, serialized)
        payload.signature = serialized[offset:]
        return payload

    def to_dict(self) -> dict:
        """
        Convert this payload to a dictionary.
        """
        return {name: getattr(self, name) for name in ([*self.names, "signature"])}

    @classmethod
    def from_dict(cls: type[Self], **kwargs) -> Self:
        """
        Create a payload from the given data (an unpacked dict).
        """
        out = cls(**{key: value for key, value in kwargs.items() if key in cls.names})
        signature = kwargs.get("signature")
        if signature is not None:
            out.signature = signature
        return out

    def add_signature(self, key: PrivateKey) -> None:
        """
        Create a signature for this payload.
        """
        self.public_key = key.pub().key_to_bin()[10:]
        self.signature = default_eccrypto.create_signature(key, self.serialized())

    def has_signature(self) -> bool:
        """
        Check if this payload has an attached signature already.
        """
        return self.public_key != NULL_KEY or self.signature != NULL_SIG

    def check_signature(self) -> bool:
        """
        Check if the signature attached to this payload is valid for this payload.
        """
        return default_eccrypto.is_valid_signature(
                default_eccrypto.key_from_public_bin(b"LibNaCLPK:" + self.public_key),
                self.serialized(),
                self.signature
        )


@vp_compile
class ChannelNodePayload(SignedPayload):
    """
    A signed payload that also includes an id, origin id, and a timestamp.
    """

    names = [*SignedPayload.names, "id_", "origin_id", "timestamp"]
    format_list = [*SignedPayload.format_list, "Q", "Q", "Q"]

    id_: int
    origin_id: int
    timestamp: int


@vp_compile
class MetadataNodePayload(ChannelNodePayload):
    """
    Deprecated, do not use.
    """

    names = [*ChannelNodePayload.names, "title", "tags"]
    format_list = [*ChannelNodePayload.format_list, "varlenIutf8", "varlenIutf8"]


@vp_compile
class JsonNodePayload(ChannelNodePayload):
    """
    Deprecated, do not use.
    """

    names = [*ChannelNodePayload.names, "json_text"]
    format_list = [*ChannelNodePayload.format_list, "varlenIutf8"]


@vp_compile
class BinaryNodePayload(ChannelNodePayload):
    """
    Deprecated, do not use.
    """

    names = [*ChannelNodePayload.names, "binary_data", "data_type"]
    format_list = [*ChannelNodePayload.format_list, "varlenI", "varlenIutf8"]


@vp_compile
class CollectionNodePayload(MetadataNodePayload):
    """
    Deprecated, do not use.
    """

    names = [*MetadataNodePayload.names, "num_entries"]
    format_list = [*MetadataNodePayload.format_list, "Q"]


@vp_compile
class TorrentMetadataPayload(ChannelNodePayload):
    """
    Payload for metadata that stores a torrent.
    """

    names = [*ChannelNodePayload.names, "infohash", "size", "torrent_date", "title", "tags", "tracker_info"]
    format_list = [*ChannelNodePayload.format_list, "20s", "Q", "I", "varlenIutf8", "varlenIutf8", "varlenIutf8"]

    infohash: bytes
    size: int
    torrent_date: int
    title: str
    tags: str
    tracker_info: str

    def fix_pack_torrent_date(self, value: datetime | int) -> int:
        """
        Auto-convert the torrent date to an integer if it is a ``datetime`` object.
        """
        if isinstance(value, datetime):
            return time2int(value)
        return value

    @classmethod
    def fix_unpack_torrent_date(cls: type[Self], value: int) -> datetime:
        """
        Auto-convert the torrent data from the integer wire format to a ``datetime`` object.
        """
        return int2time(value)

    def get_magnet(self) -> str:
        """
        Create a magnet link for this payload.
        """
        return (f"magnet:?xt=urn:btih:{hexlify(self.infohash).decode()}&dn={self.title}"
                + (f"&tr={self.tracker_info}" if self.tracker_info else ""))


@vp_compile
class ChannelMetadataPayload(TorrentMetadataPayload):
    """
    Deprecated, do not use.
    """

    names = [*TorrentMetadataPayload.names, "num_entries", "start_timestamp"]
    format_list = [*TorrentMetadataPayload.format_list, "Q", "Q"]


@vp_compile
class DeletedMetadataPayload(SignedPayload):
    """
    Deprecated, do not use.
    """

    names = [*SignedPayload.names, "delete_signature"]
    format_list = [*SignedPayload.format_list, "64s"]


METADATA_TYPE_TO_PAYLOAD_CLASS = {
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

    format_list = ["varlenI"]
    names = ["data"]

    data: bytes

    def serialize(self) -> bytes:
        """
        Convert this payload to bytes.
        """
        return default_serializer.pack_serializable(self)

    @classmethod
    def unpack(cls: type[Self], data: bytes) -> list[tuple[int, int, int]]:
        """
        Unpack this payload from the given data buffer.
        """
        data = default_serializer.unpack_serializable(cls, data)[0].data
        items = data.split(b';')[:-1]
        return [cls.parse_health_data_item(item) for item in items]

    @classmethod
    def parse_health_data_item(cls: type[Self], item: bytes) -> tuple[int, int, int]:
        """
        Convert the given bytes to ``(seeders, leechers, last_check)`` format.
        """
        if not item:
            return 0, 0, 0

        # The format is forward-compatible: currently only three first elements of data are used,
        # and later it is possible to add more fields without breaking old clients
        try:
            seeders, leechers, last_check = map(int, item.split(b',')[:3])
        except Exception:
            return 0, 0, 0

        # Safety check: seelders, leechers and last_check values cannot be negative
        if seeders < 0 or leechers < 0 or last_check < 0:
            return 0, 0, 0

        return seeders, leechers, last_check

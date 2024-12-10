from __future__ import annotations

import random
from binascii import hexlify, unhexlify
from datetime import datetime
from struct import unpack
from typing import TYPE_CHECKING, Any

from lz4.frame import LZ4FrameCompressor
from pony import orm
from pony.orm import Database, db_session
from typing_extensions import Self

from tribler.core.database.serialization import (
    EPOCH,
    REGULAR_TORRENT,
    HealthItemsPayload,
    TorrentMetadataPayload,
    time2int,
)
from tribler.core.libtorrent.trackers import get_uniformed_tracker_url
from tribler.core.notifier import Notification, Notifier

NULL_KEY_SUBST = b"\00"

CHANNEL_DIR_NAME_PK_LENGTH = 32  # It's not 40, so it could be distinguished from infohash
CHANNEL_DIR_NAME_ID_LENGTH = 16  # Zero-padded long int in hex form
CHANNEL_DIR_NAME_LENGTH = CHANNEL_DIR_NAME_PK_LENGTH + CHANNEL_DIR_NAME_ID_LENGTH

LZ4_EMPTY_ARCHIVE = unhexlify("04224d184040c000000000")
LZ4_END_MARK_SIZE = 4  # in bytes, from original specification. We don't use CRC

HEALTH_ITEM_HEADER_SIZE = 4  # in bytes, len of varlenI header

# Metadata, torrents and channel statuses
NEW = 0  # The entry is newly created and is not published yet. It will be committed at the next commit.
TODELETE = 1  # The entry is marked to be removed at the next commit.
COMMITTED = 2  # The entry is committed and seeded.
UPDATED = 6  # One of the entry's properties was updated. It will be committed at the next commit.

PUBLIC_KEY_LEN = 64

if TYPE_CHECKING:
    from dataclasses import dataclass

    from tribler.core.database.orm_bindings.torrent_state import TorrentState
    from tribler.core.libtorrent.torrentdef import TorrentDef

    @dataclass
    class TorrentMetadata:
        """
        Database type for torrent metadata.
        """

        rowid: int
        infohash: bytes
        size: int | None
        torrent_date: datetime | None
        tracker_info: str | None
        title: str | None
        tags: str | None
        metadata_type: int
        reserved_flags: int | None
        origin_id: int | None
        public_key: bytes
        id_: int
        timestamp: int
        signature: bytes | None
        added_on: datetime | None
        status: int | None
        xxx: float | None
        health: TorrentState | None
        tag_processor_version: int

        def serialized_health(self) -> bytes: ...  # noqa: D102

        def serialized(self, key: bytes | None = None) -> bytes: ...  # noqa: D102

        def to_simple_dict(self) -> dict[str, str | bytes | float | None]: ...  # noqa: D102


def infohash_to_id(infohash: bytes) -> int:
    """
    This function is used to devise ``id_`` from infohash in deterministic way. Used in FFA channels.
    """
    return abs(unpack(">q", infohash[:8])[0])


def tdef_to_metadata_dict(tdef: TorrentDef) -> dict:
    """
    Helper function to create a TorrentMetadata-compatible dict from TorrentDef.
    """
    tags = "Unknown"

    try:
        torrent_date = datetime.fromtimestamp(tdef.get_creation_date())  # noqa: DTZ006
    except (ValueError, TypeError):
        torrent_date = EPOCH

    tracker = tdef.get_tracker()
    if not isinstance(tracker, bytes):
        tracker = b""
    tracker_url = tracker.decode()
    tracker_info = get_uniformed_tracker_url(tracker_url) or ''
    return {
        "infohash": tdef.get_infohash(),
        "title": tdef.get_name_as_unicode()[:300],
        "tags": tags[:200],
        "size": tdef.get_length(),
        "torrent_date": max(torrent_date, EPOCH),
        "tracker_info": tracker_info,
    }


def entries_to_chunk(metadata_list: list[TorrentMetadata], chunk_size: int, start_index: int = 0,
                     include_health: bool = False) -> tuple[bytes, int]:
    """
    Put serialized data of one or more metadata entries into a single binary chunk. The data is added
    incrementally until it stops fitting into the designated chunk size. The first entry is added
    regardless of violating the chunk size limit.

    The chunk format is:

        <LZ4-compressed sequence of serialized metadata entries>
        [<optional HealthItemsPayload>]

    For the details of the health info format see the documentation: doc/metadata_store/serialization_format.rst

    :param metadata_list: the list of metadata to process.
    :param chunk_size: the desired chunk size limit, in bytes.
    :param start_index: the index of the element of metadata_list from which the processing should start.
    :param include_health: if True, put metadata health information into the chunk.
    :return: (chunk, last_entry_index) tuple, where chunk is the resulting chunk in string form and
        last_entry_index is the index of the element of the input list that was put into the chunk the last.
    """
    if start_index >= len(metadata_list):
        msg = "Could not serialize chunk: incorrect start_index"
        raise Exception(msg, metadata_list, chunk_size, start_index)

    compressor = LZ4FrameCompressor(auto_flush=True)
    metadata_buffer = compressor.begin()
    health_buffer = b''

    index = 0
    size = len(metadata_buffer) + LZ4_END_MARK_SIZE
    if include_health:
        size += HEALTH_ITEM_HEADER_SIZE

    for count in range(start_index, len(metadata_list)):
        metadata = metadata_list[count]
        metadata_bytes = compressor.compress(metadata.serialized())
        health_bytes = metadata.serialized_health() if include_health else b''
        size += len(metadata_bytes) + len(health_bytes)

        if size > chunk_size and count > 0:
            # The first entry is always added even if the resulted size exceeds the chunk size.
            # This lets higher levels to decide what to do in this case, e.g. send it through EVA protocol.
            break

        metadata_buffer += metadata_bytes
        if include_health:
            health_buffer += health_bytes
        index = count

    result = metadata_buffer + compressor.flush()
    if include_health:
        result += HealthItemsPayload(health_buffer).serialize()

    return result, index + 1


def define_binding(db: Database, notifier: Notifier | None,  # noqa: C901
                   tag_processor_version: int) -> type[TorrentMetadata]:
    """
    Define the torrent metadata binding.
    """

    class TorrentMetadata(db.Entity):
        """
        This ORM binding class is intended to store Torrent objects, i.e. infohashes along with some related metadata.
        """

        _discriminator_ = REGULAR_TORRENT
        _table_ = "ChannelNode"
        _CHUNK_SIZE_LIMIT = 1 * 1024 * 1024  # We use 1MB chunks as a workaround for Python's lack of string pointers

        rowid = orm.PrimaryKey(int, size=64, auto=True)

        # Serializable
        infohash = orm.Required(bytes, index=True)
        size = orm.Optional(int, size=64, default=0)
        torrent_date = orm.Optional(datetime, default=datetime.utcnow, index=True)
        tracker_info = orm.Optional(str, default='')
        title = orm.Optional(str, default='')
        tags = orm.Optional(str, default='')
        metadata_type = orm.Discriminator(int, size=16)
        reserved_flags = orm.Optional(int, size=16, default=0)
        origin_id = orm.Optional(int, size=64, default=0, index=True)
        public_key = orm.Required(bytes)
        id_ = orm.Required(int, size=64)
        timestamp = orm.Required(int, size=64, default=0)
        # Signature is nullable. This means that "None" entries are stored in DB as NULLs instead of empty strings.
        # NULLs are not checked for uniqueness and not indexed.
        # This is necessary to store unsigned signatures without violating the uniqueness constraints.
        signature = orm.Optional(bytes, unique=True, nullable=True, default=None)

        orm.composite_key(public_key, id_)
        orm.composite_index(public_key, origin_id)

        # Local
        added_on = orm.Optional(datetime, default=datetime.utcnow)
        status = orm.Optional(int, default=COMMITTED)
        xxx = orm.Optional(float, default=0)
        health = orm.Optional('TorrentState', reverse='metadata')
        tag_processor_version = orm.Required(int, default=0)

        # Special class-level properties
        payload_class = TorrentMetadataPayload

        def __init__(self, *args: Any, **kwargs) -> None:  # noqa: ANN401
            # Any public keys + signatures are considered to be correct at this point, and should
            # be checked after receiving the payload from the network.

            if "health" not in kwargs and "infohash" in kwargs:
                infohash = kwargs["infohash"]
                health = db.TorrentState.get_for_update(infohash=infohash) or db.TorrentState(infohash=infohash)
                kwargs["health"] = health

            if "timestamp" not in kwargs:
                kwargs["timestamp"] = time2int(datetime.utcnow()) * 1000  # noqa: DTZ003

            if "id_" not in kwargs:
                kwargs["id_"] = int(random.getrandbits(63))

            # Free-for-all entries require special treatment
            kwargs["public_key"] = kwargs.get("public_key", b"")
            if kwargs["public_key"] == b"":
                # We have to give the entry an unique sig to honor the DB constraints. We use the entry's id_
                # as the sig to keep it unique and short. The uniqueness is guaranteed by DB as it already
                # imposes uniqueness constraints on the id_+public_key combination.
                kwargs["signature"] = None

            super().__init__(*args, **kwargs)

            if 'tracker_info' in kwargs:
                self.add_tracker(kwargs["tracker_info"])

            if notifier:
                notifier.notify(Notification.new_torrent_metadata_created,
                                infohash=kwargs.get("infohash"), title=self.title)
                self.tag_processor_version = tag_processor_version

        def add_tracker(self, tracker_url: str) -> None:
            sanitized_url = get_uniformed_tracker_url(tracker_url)
            if sanitized_url:
                tracker = db.TrackerState.get_for_update(url=sanitized_url) or db.TrackerState(url=sanitized_url)
                self.health.trackers.add(tracker)

        def before_update(self) -> None:
            self.add_tracker(self.tracker_info)

        def get_magnet(self) ->  str:
            return f"magnet:?xt=urn:btih:{hexlify(self.infohash).decode()}&dn={self.title}" + (
                f"&tr={self.tracker_info}" if self.tracker_info else ""
            )

        @classmethod
        @db_session
        def add_ffa_from_dict(cls: type[Self], metadata: dict) -> Self | None:
            # To produce a relatively unique id_ we take some bytes of the infohash and convert these to a number.
            # abs is necessary as the conversion can produce a negative value, and we do not support that.
            id_ = infohash_to_id(metadata["infohash"])
            # Check that this torrent is yet unknown to GigaChannel, and if there is no duplicate FFA entry.
            # Test for a duplicate id_+public_key is necessary to account for a (highly improbable) situation when
            # two entries have different infohashes but the same id_. We do not want people to exploit this.
            ih_blob = metadata["infohash"]
            pk_blob = b""
            if cls.exists(lambda g: (g.infohash == ih_blob) or (g.id_ == id_ and g.public_key == pk_blob)):
                return None
            if isinstance(metadata.get("tracker_info", ""), bytes):
                metadata["tracker_info"] = metadata["tracker_info"].decode()
            # Add the torrent as a free-for-all entry if it is unknown to GigaChannel
            return cls.from_dict(dict(metadata, public_key=b'', status=COMMITTED, id_=id_))

        @db_session
        def to_simple_dict(self) -> dict[str, str | float]:
            """
            Return a basic dictionary with information about the channel.
            """
            epoch = datetime.utcfromtimestamp(0)  # noqa: DTZ004
            return {
                "name": self.title,
                "category": self.tags,
                "infohash": hexlify(self.infohash).decode(),
                "size": self.size,
                "num_seeders": self.health.seeders,
                "num_leechers": self.health.leechers,
                "last_tracker_check": self.health.last_check,
                "created": int((self.torrent_date - epoch).total_seconds()),
                "tag_processor_version": self.tag_processor_version,
                "type": self.get_type(),
                "id": self.id_,
                "origin_id": self.origin_id,
                "public_key": hexlify(self.public_key).decode(),
                "status": self.status,
            }

        def get_type(self) -> int:
            return self._discriminator_

        @classmethod
        def from_payload(cls: type[Self], payload: TorrentMetadataPayload) -> Self:
            return cls(**payload.to_dict())

        @classmethod
        def from_dict(cls: type[Self], dct: dict) -> Self:
            return cls(**dct)

        @classmethod
        @db_session
        def get_with_infohash(cls: type[Self], infohash: bytes) -> Self:
            return cls.select(lambda g: g.infohash == infohash).first()

        @classmethod
        @db_session
        def get_torrent_title(cls: type[Self], infohash: bytes) -> str | None:
            md = cls.get_with_infohash(infohash)
            return md.title if md else None

        def serialized_health(self) -> bytes:
            health = self.health
            if not health or (not health.seeders and not health.leechers and not health.last_check):
                return b";"
            return b"%d,%d,%d;" % (health.seeders or 0, health.leechers or 0, health.last_check or 0)

        def serialized(self, key: bytes | None = None) -> bytes:
            """
            Serializes the object and returns the result with added signature (blob output).

            :param key: private key to sign object with
            :return: serialized_data+signature binary string
            """
            kwargs = self.to_dict()
            payload = self.payload_class.from_dict(**kwargs)
            payload.signature = kwargs.pop("signature", None) or payload.signature
            if key:
                payload.add_signature(key)
            return payload.serialized() + payload.signature

    return TorrentMetadata

from __future__ import division

import xdrlib
from datetime import datetime, timedelta

from enum import Enum, unique

from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto

EPOCH = datetime(1970, 1, 1)
INFOHASH_SIZE = 20  # bytes
crypto = ECCrypto()


@unique
class MetadataTypes(Enum):
    TYPELESS = 1
    REGULAR_TORRENT = 2
    CHANNEL_TORRENT = 3
    DELETED = 4


TYPELESS = MetadataTypes.TYPELESS
REGULAR_TORRENT = MetadataTypes.REGULAR_TORRENT
CHANNEL_TORRENT = MetadataTypes.CHANNEL_TORRENT
DELETED = MetadataTypes.DELETED

# We have to write our own serialization procedure for timestamps, since
# there is no standard for this, except Unix time, and that is
# deprecated by 2038, that is very soon
def time2float(dt, epoch=EPOCH):
    # WARNING: TZ-aware timestamps are madhouse...
    # For Python3 we could use a simpler method:
    # timestamp = (dt - datetime(1970,1,1, tzinfo=timezone.utc)) / timedelta(seconds=1)
    td = dt - epoch
    # return td.total_seconds()
    return float((td.microseconds + (td.seconds + td.days * 86400) * 10 ** 6) / 10 ** 6)


def float2time(ts, epoch=EPOCH):
    microseconds_total = int(ts * 10 ** 6)
    microseconds = microseconds_total % 10 ** 6
    seconds_total = (microseconds_total - microseconds) / 10 ** 6
    seconds = seconds_total % 86400
    days = (seconds_total - seconds) / 86400
    dt = epoch + timedelta(days=days, seconds=seconds,
                           microseconds=microseconds)
    return dt


class SerializationError(Exception):
    pass

class DeserializationError(Exception):
    pass

# We don't split the de/serialization procedures into a bunch of smaller methods
# bound to the classes hierarchy to simplify compatibility with future
# versions.
def serialize_metadata_gossip(md, key=None, check_signature=False):
    p = xdrlib.Packer()
    if key:
        md["public_key"] = key.pub().key_to_bin()
    else:
        if "signature" not in md:
            raise SerializationError

    p.pack_int(md["type"])
    p.pack_opaque(md["public_key"])
    p.pack_double(time2float(md["timestamp"]))
    p.pack_uhyper(md["tc_pointer"])  # TrustChain pointer

    if md["type"] == MetadataTypes.REGULAR_TORRENT.value or \
            md["type"] == MetadataTypes.CHANNEL_TORRENT.value:
        p.pack_fopaque(INFOHASH_SIZE, md["infohash"])
        p.pack_uhyper(md["size"])
        p.pack_double(time2float(md["torrent_date"]))
        p.pack_string(md["title"].encode('utf-8'))
        p.pack_string(md["tags"].encode('utf-8'))

    if md["type"] == MetadataTypes.CHANNEL_TORRENT.value:
        p.pack_hyper(md["version"])

    if md["type"] == MetadataTypes.DELETED.value:
        p.pack_opaque(md["delete_signature"])

    if key:
        signature = crypto.create_signature(key, p.get_buf())
        md["signature"] = signature
    p.pack_opaque(md["signature"])

    if check_signature:
        try:
            deserialize_metadata_gossip(p.get_buf(), check_signature=True)
        except DeserializationError:
            raise SerializationError("Serialization with wrong pk/signature")

    return p.get_buf()


def deserialize_metadata_gossip(buf, check_signature=True):
    u = xdrlib.Unpacker(buf)

    md = {}
    md["type"] = u.unpack_int()
    md["public_key"] = u.unpack_opaque()
    md["timestamp"] = float2time(u.unpack_double())
    md["tc_pointer"] = u.unpack_uhyper()

    if md["type"] == MetadataTypes.REGULAR_TORRENT.value or \
            md["type"] == MetadataTypes.CHANNEL_TORRENT.value:
        md["infohash"] = u.unpack_fopaque(INFOHASH_SIZE)
        md["size"] = u.unpack_uhyper()
        md["torrent_date"] = float2time(u.unpack_double())
        md["title"] = u.unpack_string().decode('utf-8')
        md["tags"] = u.unpack_string().decode('utf-8')

    if md["type"] == MetadataTypes.CHANNEL_TORRENT.value:
        md["version"] = u.unpack_hyper()

    if md["type"] == MetadataTypes.DELETED.value:
        md["delete_signature"] = u.unpack_opaque()

    contents_end = u.get_position()
    md["signature"] = u.unpack_opaque()
    u.done()

    if check_signature:
        # Checking signature and PK correctness
        if not crypto.is_valid_public_bin(md["public_key"]):
            raise DeserializationError("Bad public key", md["public_key"])
        if not crypto.is_valid_signature(
                crypto.key_from_public_bin(md["public_key"]),
                buf[:contents_end],
                md["signature"]):
            raise DeserializationError("Bad signature", md["signature"])

    return md

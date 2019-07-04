from __future__ import absolute_import, division

import struct
from binascii import hexlify
from datetime import datetime, timedelta

from ipv8.database import database_blob
from ipv8.keyvault.crypto import default_eccrypto
from ipv8.messaging.payload import Payload
from ipv8.messaging.serialization import default_serializer

from Tribler.Core.exceptions import InvalidSignatureException

EPOCH = datetime(1970, 1, 1)
INFOHASH_SIZE = 20  # bytes

SIGNATURE_SIZE = 64
NULL_SIG = b'\x00' * 64
NULL_KEY = b'\x00' * 64

# Metadata types. Should have been an enum, but in Python its unwieldy.
TYPELESS = 100
CHANNEL_NODE = 200
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
    metadata_type = struct.unpack_from('>H', database_blob(data), offset=offset)[0]
    if metadata_type == DELETED:
        return DeletedMetadataPayload.from_signed_blob_with_offset(data, offset=offset)
    elif metadata_type == REGULAR_TORRENT:
        return TorrentMetadataPayload.from_signed_blob_with_offset(data, offset=offset)
    elif metadata_type == CHANNEL_TORRENT:
        return ChannelMetadataPayload.from_signed_blob_with_offset(data, offset=offset)

    # Unknown metadata type, raise exception
    raise UnknownBlobTypeException


def read_payload(data):
    return read_payload_with_offset(data)[0]


class SignedPayload(Payload):
    """
    Payload for metadata.
    """

    format_list = ['H', 'H', '64s']

    def __init__(self, metadata_type, reserved_flags, public_key, **kwargs):
        super(SignedPayload, self).__init__()
        self.metadata_type = metadata_type
        self.reserved_flags = reserved_flags
        self.public_key = str(public_key)
        self.signature = str(kwargs["signature"]) if "signature" in kwargs and kwargs["signature"] else None

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
            else:
                raise InvalidSignatureException("Tried to create FFA payload with non-null signature")

        serialized_data = default_serializer.pack_multiple(self.to_pack_list())[0]
        if "key" in kwargs and kwargs["key"]:
            key = kwargs["key"]
            if self.public_key != str(key.pub().key_to_bin()[10:]):
                raise KeysMismatchException(self.public_key, str(key.pub().key_to_bin()[10:]))
            self.signature = default_eccrypto.create_signature(key, serialized_data)
        elif "signature" in kwargs:
            # This check ensures that an entry with a wrong signature will not proliferate further
            if not default_eccrypto.is_valid_signature(
                    default_eccrypto.key_from_public_bin(b"LibNaCLPK:" + self.public_key),
                    serialized_data, self.signature):
                raise InvalidSignatureException("Tried to create payload with wrong signature")
        else:
            raise InvalidSignatureException("Tried to create payload without signature")

    def to_pack_list(self):
        data = [('H', self.metadata_type),
                ('H', self.reserved_flags),
                ('64s', self.public_key)]
        return data

    @classmethod
    def from_unpack_list(cls, metadata_type, reserved_flags, public_key, **kwargs):
        return SignedPayload(metadata_type, reserved_flags, public_key, **kwargs)

    @classmethod
    def from_signed_blob(cls, data, check_signature=True):
        return cls.from_signed_blob_with_offset(data, check_signature)[0]

    @classmethod
    def from_signed_blob_with_offset(cls, data, check_signature=True, offset=0):
        # TODO: stop serializing/deserializing stuff twice
        unpack_list, end_offset = default_serializer.unpack_multiple(cls.format_list, data, offset=offset)
        if check_signature:
            signature = data[end_offset:end_offset + SIGNATURE_SIZE]
            payload = cls.from_unpack_list(*unpack_list, signature=signature)
        else:
            payload = cls.from_unpack_list(*unpack_list, skip_key_check=True)
        return payload, end_offset + SIGNATURE_SIZE

    def to_dict(self):
        return {
            "metadata_type": self.metadata_type,
            "reserved_flags": self.reserved_flags,
            "public_key": self.public_key,
            "signature": self.signature
        }

    def _serialized(self):
        serialized_data = default_serializer.pack_multiple(self.to_pack_list())[0]
        return str(serialized_data), str(self.signature)

    def serialized(self):
        return ''.join(self._serialized())

    @classmethod
    def from_file(cls, filepath):
        with open(filepath, 'rb') as f:
            return cls.from_signed_blob(f.read())


class ChannelNodePayload(SignedPayload):
    format_list = SignedPayload.format_list + ['Q', 'Q', 'Q']

    def __init__(self, metadata_type, reserved_flags, public_key,
                 id_, origin_id, timestamp,
                 **kwargs):
        self.id_ = id_
        self.origin_id = origin_id
        self.timestamp = timestamp
        super(ChannelNodePayload, self).__init__(metadata_type, reserved_flags, public_key,
                                                 **kwargs)

    def to_pack_list(self):
        data = super(ChannelNodePayload, self).to_pack_list()
        data.append(('Q', self.id_))
        data.append(('Q', self.origin_id))
        data.append(('Q', self.timestamp))
        return data

    @classmethod
    def from_unpack_list(cls, metadata_type, reserved_flags, public_key,
                         id_, origin_id, timestamp,
                         **kwargs):
        return ChannelNodePayload(metadata_type, reserved_flags, public_key,
                                  id_, origin_id, timestamp,
                                  **kwargs)

    def to_dict(self):
        dct = super(ChannelNodePayload, self).to_dict()
        dct.update({
            "id_": self.id_,
            "origin_id": self.origin_id,
            "timestamp": self.timestamp
        })
        return dct


class TorrentMetadataPayload(ChannelNodePayload):
    """
    Payload for metadata that stores a torrent.
    """
    format_list = ChannelNodePayload.format_list + ['20s', 'Q', 'I', 'varlenI', 'varlenI', 'varlenI']

    def __init__(self, metadata_type, reserved_flags, public_key,
                 id_, origin_id, timestamp,
                 infohash, size, torrent_date, title, tags, tracker_info,
                 **kwargs):
        self.infohash = str(infohash)
        self.size = size
        self.torrent_date = time2int(torrent_date) if isinstance(torrent_date, datetime) else torrent_date
        self.title = title.decode('utf-8') if isinstance(title, str) else title
        self.tags = tags.decode('utf-8') if isinstance(tags, str) else tags
        self.tracker_info = tracker_info.decode('utf-8') if isinstance(tracker_info, str) else tracker_info
        super(TorrentMetadataPayload, self).__init__(metadata_type, reserved_flags, public_key,
                                                     id_, origin_id, timestamp,
                                                     **kwargs)

    def to_pack_list(self):
        data = super(TorrentMetadataPayload, self).to_pack_list()
        data.append(('20s', self.infohash))
        data.append(('Q', self.size))
        data.append(('I', self.torrent_date))
        data.append(('varlenI', self.title.encode('utf-8')))
        data.append(('varlenI', self.tags.encode('utf-8')))
        data.append(('varlenI', self.tracker_info.encode('utf-8')))
        return data

    @classmethod
    def from_unpack_list(cls, metadata_type, reserved_flags, public_key,
                         id_, origin_id, timestamp,
                         infohash, size, torrent_date, title, tags, tracker_info, **kwargs):
        return TorrentMetadataPayload(metadata_type, reserved_flags, public_key,
                                      id_, origin_id, timestamp,
                                      infohash, size, torrent_date, title, tags, tracker_info, **kwargs)

    def to_dict(self):
        dct = super(TorrentMetadataPayload, self).to_dict()
        dct.update({
            "infohash": self.infohash,
            "size": self.size,
            "torrent_date": int2time(self.torrent_date),
            "title": self.title,
            "tags": self.tags,
            "tracker_info": self.tracker_info
        })
        return dct

    # TODO:  DRY!(copypasted from TorrentMetadata)
    def get_magnet(self):
        return ("magnet:?xt=urn:btih:%s&dn=%s" %
                (hexlify(str(self.infohash)), str(self.title).encode('utf8'))) + \
               ("&tr=%s" % (str(self.tracker_info).encode('utf8')) if self.tracker_info else "")


class ChannelMetadataPayload(TorrentMetadataPayload):
    """
    Payload for metadata that stores a channel.
    """
    format_list = TorrentMetadataPayload.format_list + ['Q'] + ['Q']

    def __init__(self, metadata_type, reserved_flags, public_key,
                 id_, origin_id, timestamp,
                 infohash, size, torrent_date, title, tags, tracker_info,
                 num_entries, start_timestamp,
                 **kwargs):
        self.num_entries = num_entries
        self.start_timestamp = start_timestamp
        super(ChannelMetadataPayload, self).__init__(metadata_type, reserved_flags, public_key,
                                                     id_, origin_id, timestamp,
                                                     infohash, size, torrent_date, title, tags, tracker_info,
                                                     **kwargs)

    def to_pack_list(self):
        data = super(ChannelMetadataPayload, self).to_pack_list()
        data.append(('Q', self.num_entries))
        data.append(('Q', self.start_timestamp))
        return data

    @classmethod
    def from_unpack_list(cls, metadata_type, reserved_flags, public_key,
                         id_, origin_id, timestamp,
                         infohash, size, torrent_date, title, tags, tracker_info,
                         num_entries, start_timestamp,
                         **kwargs):
        return ChannelMetadataPayload(metadata_type, reserved_flags, public_key,
                                      id_, origin_id, timestamp,
                                      infohash, size, torrent_date, title, tags, tracker_info,
                                      num_entries, start_timestamp,
                                      **kwargs)

    def to_dict(self):
        dct = super(ChannelMetadataPayload, self).to_dict()
        dct.update({"num_entries": self.num_entries,
                    "start_timestamp": self.start_timestamp})
        return dct


class DeletedMetadataPayload(SignedPayload):
    """
    Payload for metadata that stores deleted metadata.
    """
    format_list = SignedPayload.format_list + ['64s']

    def __init__(self, metadata_type, reserved_flags, public_key,
                 delete_signature,
                 **kwargs):
        self.delete_signature = str(delete_signature)
        super(DeletedMetadataPayload, self).__init__(metadata_type, reserved_flags, public_key,
                                                     **kwargs)

    def to_pack_list(self):
        data = super(DeletedMetadataPayload, self).to_pack_list()
        data.append(('64s', self.delete_signature))
        return data

    @classmethod
    def from_unpack_list(cls, metadata_type, reserved_flags, public_key,
                         delete_signature,
                         **kwargs):
        return DeletedMetadataPayload(metadata_type, reserved_flags, public_key,
                                      delete_signature,
                                      **kwargs)

    def to_dict(self):
        dct = super(DeletedMetadataPayload, self).to_dict()
        dct.update({"delete_signature": self.delete_signature})
        return dct

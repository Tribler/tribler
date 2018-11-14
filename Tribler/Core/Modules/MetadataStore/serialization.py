from __future__ import absolute_import, division

import struct
from binascii import hexlify
from datetime import datetime, timedelta

from Tribler.Core.exceptions import InvalidSignatureException
from Tribler.pyipv8.ipv8.database import database_blob
from Tribler.pyipv8.ipv8.keyvault.crypto import default_eccrypto
from Tribler.pyipv8.ipv8.messaging.payload import Payload
from Tribler.pyipv8.ipv8.messaging.serialization import default_serializer

EPOCH = datetime(1970, 1, 1)
INFOHASH_SIZE = 20  # bytes

SIGNATURE_SIZE = 64
EMPTY_SIG = '0' * 64

# Metadata types. Should have been an enum, but in Python its unwieldy.
TYPELESS = 1
REGULAR_TORRENT = 2
CHANNEL_TORRENT = 3
DELETED = 4


# We have to write our own serialization procedure for timestamps, since
# there is no standard for this, except Unix time, and that is
# deprecated by 2038, that is very soon.


def time2float(date_time, epoch=EPOCH):
    """
    Convert a datetime object to a float.
    :param date_time: The datetime object to convert.
    :param epoch: The epoch time, defaults to Jan 1, 1970.
    :return: The floating point representation of date_time.

    WARNING: TZ-aware timestamps are madhouse...
    For Python3 we could use a simpler method:
    timestamp = (dt - datetime(1970, 1, 1, tzinfo=timezone.utc)) / timedelta(seconds=1)
    """
    time_diff = date_time - epoch
    return float((time_diff.microseconds + (time_diff.seconds + time_diff.days * 86400) * 10 ** 6) / 10 ** 6)


def float2time(timestamp, epoch=EPOCH):
    """
    Convert a float into a datetime object.
    :param timestamp: The timestamp to be converted.
    :param epoch: The epoch time, defaults to Jan 1, 1970.
    :return: The datetime representation of timestamp.
    """
    microseconds_total = int(timestamp * 10 ** 6)
    microseconds = microseconds_total % 10 ** 6
    seconds_total = (microseconds_total - microseconds) / 10 ** 6
    seconds = seconds_total % 86400
    days = (seconds_total - seconds) / 86400
    dt = epoch + timedelta(days=days, seconds=seconds, microseconds=microseconds)
    return dt


class KeysMismatchException(Exception):
    pass


class UnknownBlobTypeException(Exception):
    pass


def read_payload_with_offset(data, offset=0):
    # First we have to determine the actual payload type
    metadata_type = struct.unpack_from('>I', database_blob(data), offset=offset)[0]
    if metadata_type == DELETED:
        return DeletedMetadataPayload.from_signed_blob_with_offset(data, check_signature=True, offset=offset)
    elif metadata_type == REGULAR_TORRENT:
        return TorrentMetadataPayload.from_signed_blob_with_offset(data, check_signature=True, offset=offset)
    elif metadata_type == CHANNEL_TORRENT:
        return ChannelMetadataPayload.from_signed_blob_with_offset(data, check_signature=True, offset=offset)

    # Unknown metadata type, raise exception
    raise UnknownBlobTypeException


def read_payload(data):
    return read_payload_with_offset(data)[0]


class MetadataPayload(Payload):
    """
    Payload for metadata.
    """

    format_list = ['I', '74s', 'f', 'Q']

    def __init__(self, metadata_type, public_key, timestamp, tc_pointer, **kwargs):
        super(MetadataPayload, self).__init__()
        self.metadata_type = metadata_type
        self.public_key = str(public_key)
        self.timestamp = time2float(timestamp) if isinstance(timestamp, datetime) else timestamp
        self.tc_pointer = tc_pointer
        self.signature = str(kwargs["signature"]) if "signature" in kwargs else EMPTY_SIG

    def has_valid_signature(self):
        sig_data = default_serializer.pack_multiple(self.to_pack_list())[0]
        return default_eccrypto.is_valid_signature(default_eccrypto.key_from_public_bin(self.public_key), sig_data,
                                                   self.signature)

    def to_pack_list(self):
        data = [('I', self.metadata_type),
                ('74s', self.public_key),
                ('f', self.timestamp),
                ('Q', self.tc_pointer)]
        return data

    @classmethod
    def from_unpack_list(cls, metadata_type, public_key, timestamp, tc_pointer):
        return MetadataPayload(metadata_type, public_key, timestamp, tc_pointer)

    @classmethod
    def from_signed_blob(cls, data, check_signature=True):
        return cls.from_signed_blob_with_offset(data, check_signature)[0]

    @classmethod
    def from_signed_blob_with_offset(cls, data, check_signature=True, offset=0):
        unpack_list, end_offset = default_serializer.unpack_multiple(cls.format_list, data, offset=offset)
        payload = cls.from_unpack_list(*unpack_list)
        if check_signature:
            payload.signature = data[end_offset:end_offset + SIGNATURE_SIZE]
            data_unsigned = data[offset:end_offset]
            key = default_eccrypto.key_from_public_bin(payload.public_key)
            if not default_eccrypto.is_valid_signature(key, data_unsigned, payload.signature):
                raise InvalidSignatureException
        return payload, end_offset + SIGNATURE_SIZE

    def to_dict(self):
        return {
            "metadata_type": self.metadata_type,
            "public_key": self.public_key,
            "timestamp": float2time(self.timestamp),
            "tc_pointer": self.tc_pointer,
            "signature": self.signature
        }

    def _serialized(self, key=None):
        # If we are going to sign it, we must provide a matching key
        if key and self.public_key != str(key.pub().key_to_bin()):
            raise KeysMismatchException(self.public_key, str(key.pub().key_to_bin()))

        serialized_data = default_serializer.pack_multiple(self.to_pack_list())[0]
        if key:
            signature = default_eccrypto.create_signature(key, serialized_data)

        # This check ensures that an entry with a wrong signature will not proliferate further
        elif default_eccrypto.is_valid_signature(default_eccrypto.key_from_public_bin(self.public_key), serialized_data,
                                                 self.signature):
            signature = self.signature
        else:
            raise InvalidSignatureException(hexlify(self.signature))
        return str(serialized_data), str(signature)

    def serialized(self, key=None):
        return ''.join(self._serialized(key))

    @classmethod
    def from_file(cls, filepath):
        with open(filepath, 'rb') as f:
            return cls.from_signed_blob(f.read())


class TorrentMetadataPayload(MetadataPayload):
    """
    Payload for metadata that stores a torrent.
    """
    format_list = MetadataPayload.format_list + ['20s', 'Q', 'varlenI', 'varlenI', 'varlenI']

    def __init__(self, metadata_type, public_key, timestamp, tc_pointer, infohash, size, title, tags, tracker_info,
                 **kwargs):
        super(TorrentMetadataPayload, self).__init__(metadata_type, public_key, timestamp, tc_pointer, **kwargs)
        self.infohash = str(infohash)
        self.size = size
        self.title = title.decode('utf-8') if type(title) == str else title
        self.tags = tags.decode('utf-8') if type(tags) == str else tags
        self.tracker_info = tracker_info.decode('utf-8') if type(tracker_info) == str else tracker_info

    def to_pack_list(self):
        data = super(TorrentMetadataPayload, self).to_pack_list()
        data.append(('20s', self.infohash))
        data.append(('Q', self.size))
        data.append(('varlenI', self.title.encode('utf-8')))
        data.append(('varlenI', self.tags.encode('utf-8')))
        data.append(('varlenI', self.tracker_info.encode('utf-8')))
        return data

    @classmethod
    def from_unpack_list(cls, metadata_type, public_key, timestamp, tc_pointer, infohash, size, title, tags,
                         tracker_info):
        return TorrentMetadataPayload(metadata_type, public_key, timestamp, tc_pointer, infohash, size, title, tags,
                                      tracker_info)

    def to_dict(self):
        dct = super(TorrentMetadataPayload, self).to_dict()
        dct.update({
            "infohash": self.infohash,
            "size": self.size,
            "title": self.title,
            "tags": self.tags,
            "tracker_info": self.tracker_info
        })
        return dct

    # TODO:  DRY!(copypasted from TorrentMetadata)
    def get_magnet(self):
        return ("magnet:?xt=urn:btih:%s&dn=%s" %
                (str(self.infohash).encode('hex'), str(self.title).encode('utf8'))) + \
               ("&tr=%s" % (str(self.tracker_info).encode('utf8')) if self.tracker_info else "")


class ChannelMetadataPayload(TorrentMetadataPayload):
    """
    Payload for metadata that stores a channel.
    """
    format_list = TorrentMetadataPayload.format_list + ['Q']

    def __init__(self, metadata_type, public_key, timestamp, tc_pointer, infohash, size, title, tags, tracker_info,
                 version, **kwargs):
        super(ChannelMetadataPayload, self).__init__(metadata_type, public_key, timestamp, tc_pointer,
                                                     infohash, size, title, tags, tracker_info, **kwargs)
        self.version = version

    def to_pack_list(self):
        data = super(ChannelMetadataPayload, self).to_pack_list()
        data.append(('Q', self.version))
        return data

    @classmethod
    def from_unpack_list(cls, metadata_type, public_key, timestamp, tc_pointer, infohash, size, title, tags,
                         tracker_info, version):
        return ChannelMetadataPayload(metadata_type, public_key, timestamp, tc_pointer, infohash, size,
                                      title, tags, tracker_info, version)

    def to_dict(self):
        dct = super(ChannelMetadataPayload, self).to_dict()
        dct.update({"version": self.version})
        return dct


class DeletedMetadataPayload(MetadataPayload):
    """
    Payload for metadata that stores deleted metadata.
    """
    format_list = MetadataPayload.format_list + ['64s']

    def __init__(self, metadata_type, public_key, timestamp, tc_pointer, delete_signature, **kwargs):
        super(DeletedMetadataPayload, self).__init__(metadata_type, public_key, timestamp, tc_pointer, **kwargs)
        self.delete_signature = str(delete_signature)

    def to_pack_list(self):
        data = super(DeletedMetadataPayload, self).to_pack_list()
        data.append(('64s', self.delete_signature))
        return data

    @classmethod
    def from_unpack_list(cls, metadata_type, public_key, timestamp, tc_pointer, delete_signature):
        return DeletedMetadataPayload(metadata_type, public_key, timestamp, tc_pointer, delete_signature)

    def to_dict(self):
        dct = super(DeletedMetadataPayload, self).to_dict()
        dct.update({"delete_signature": self.delete_signature})
        return dct

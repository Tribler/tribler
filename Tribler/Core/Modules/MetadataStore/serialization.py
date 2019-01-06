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
    metadata_type = struct.unpack_from('>I', database_blob(data), offset=offset)[0]
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


class MetadataPayload(Payload):
    """
    Payload for metadata.
    """

    format_list = ['I', '64s', 'Q']

    def __init__(self, metadata_type, public_key, id_, **kwargs):
        super(MetadataPayload, self).__init__()
        self.metadata_type = metadata_type
        self.public_key = str(public_key)
        self.id_ = id_
        self.signature = str(kwargs["signature"]) if "signature" in kwargs else EMPTY_SIG

    def has_valid_signature(self):
        sig_data = default_serializer.pack_multiple(self.to_pack_list())[0]
        return default_eccrypto.is_valid_signature(
            default_eccrypto.key_from_public_bin(b"LibNaCLPK:" + self.public_key), sig_data,
            self.signature)

    def to_pack_list(self):
        data = [('I', self.metadata_type),
                ('64s', self.public_key),
                ('Q', self.id_)]
        return data

    @classmethod
    def from_unpack_list(cls, metadata_type, public_key, id_):
        return MetadataPayload(metadata_type, public_key, id_)

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
            key = default_eccrypto.key_from_public_bin(b"LibNaCLPK:" + payload.public_key)
            if not default_eccrypto.is_valid_signature(key, data_unsigned, payload.signature):
                raise InvalidSignatureException
        return payload, end_offset + SIGNATURE_SIZE

    def to_dict(self):
        return {
            "metadata_type": self.metadata_type,
            "public_key": self.public_key,
            "id_": self.id_,
            "signature": self.signature
        }

    def _serialized(self, key=None):
        # If we are going to sign it, we must provide a matching key
        if key and self.public_key != str(key.pub().key_to_bin()[10:]):
            raise KeysMismatchException(self.public_key, str(key.pub().key_to_bin()[10:]))

        serialized_data = default_serializer.pack_multiple(self.to_pack_list())[0]
        if key:
            signature = default_eccrypto.create_signature(key, serialized_data)

        # This check ensures that an entry with a wrong signature will not proliferate further
        elif default_eccrypto.is_valid_signature(default_eccrypto.key_from_public_bin(b"LibNaCLPK:" + self.public_key),
                                                 serialized_data,
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
    format_list = MetadataPayload.format_list + ['Q', '20s', 'Q', 'I', 'varlenI', 'varlenI', 'varlenI']

    def __init__(self, metadata_type, public_key, id_,
                 timestamp, infohash, size, torrent_date, title, tags, tracker_info,
                 **kwargs):
        super(TorrentMetadataPayload, self).__init__(metadata_type, public_key, id_,
                                                     **kwargs)
        self.timestamp = timestamp
        self.infohash = str(infohash)
        self.size = size
        self.torrent_date = time2int(torrent_date) if isinstance(torrent_date, datetime) else torrent_date
        self.title = title.decode('utf-8') if type(title) == str else title
        self.tags = tags.decode('utf-8') if type(tags) == str else tags
        self.tracker_info = tracker_info.decode('utf-8') if type(tracker_info) == str else tracker_info

    def to_pack_list(self):
        data = super(TorrentMetadataPayload, self).to_pack_list()
        data.append(('Q', self.timestamp))
        data.append(('20s', self.infohash))
        data.append(('Q', self.size))
        data.append(('I', self.torrent_date))
        data.append(('varlenI', self.title.encode('utf-8')))
        data.append(('varlenI', self.tags.encode('utf-8')))
        data.append(('varlenI', self.tracker_info.encode('utf-8')))
        return data

    @classmethod
    def from_unpack_list(cls, metadata_type, public_key, id_,
                         timestamp, infohash, size, torrent_date, title, tags, tracker_info):
        return TorrentMetadataPayload(metadata_type, public_key, id_,
                                      timestamp, infohash, size, torrent_date, title, tags, tracker_info)

    def to_dict(self):
        dct = super(TorrentMetadataPayload, self).to_dict()
        dct.update({
            "timestamp": self.timestamp,
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
                (str(self.infohash).encode('hex'), str(self.title).encode('utf8'))) + \
               ("&tr=%s" % (str(self.tracker_info).encode('utf8')) if self.tracker_info else "")


class ChannelMetadataPayload(TorrentMetadataPayload):
    """
    Payload for metadata that stores a channel.
    """
    format_list = TorrentMetadataPayload.format_list + ['Q']

    def __init__(self, metadata_type, public_key, id_,
                 timestamp, infohash, size, torrent_date, title, tags, tracker_info,
                 num_entries,
                 **kwargs):
        super(ChannelMetadataPayload, self).__init__(metadata_type, public_key, id_,
                                                     timestamp, infohash, size, torrent_date, title, tags,
                                                     tracker_info,
                                                     **kwargs)
        self.num_entries = num_entries

    def to_pack_list(self):
        data = super(ChannelMetadataPayload, self).to_pack_list()
        data.append(('Q', self.num_entries))
        return data

    @classmethod
    def from_unpack_list(cls, metadata_type, public_key, id_,
                         timestamp, infohash, size, torrent_date, title, tags, tracker_info,
                         num_entries):
        return ChannelMetadataPayload(metadata_type, public_key, id_,
                                      timestamp, infohash, size, torrent_date, title, tags, tracker_info,
                                      num_entries)

    def to_dict(self):
        dct = super(ChannelMetadataPayload, self).to_dict()
        dct.update({"num_entries": self.num_entries})
        return dct


class DeletedMetadataPayload(MetadataPayload):
    """
    Payload for metadata that stores deleted metadata.
    """
    format_list = MetadataPayload.format_list + ['64s']

    def __init__(self, metadata_type, public_key, id_,
                 delete_signature,
                 **kwargs):
        super(DeletedMetadataPayload, self).__init__(metadata_type, public_key, id_,
                                                     **kwargs)
        self.delete_signature = str(delete_signature)

    def to_pack_list(self):
        data = super(DeletedMetadataPayload, self).to_pack_list()
        data.append(('64s', self.delete_signature))
        return data

    @classmethod
    def from_unpack_list(cls, metadata_type, public_key, id_,
                         delete_signature):
        return DeletedMetadataPayload(metadata_type, public_key, id_,
                                      delete_signature)

    def to_dict(self):
        dct = super(DeletedMetadataPayload, self).to_dict()
        dct.update({"delete_signature": self.delete_signature})
        return dct

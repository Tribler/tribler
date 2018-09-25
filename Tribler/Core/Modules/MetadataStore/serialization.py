from __future__ import division

from datetime import datetime, timedelta

from enum import Enum, unique

from Tribler.pyipv8.ipv8.attestation.trustchain.block import EMPTY_SIG
from Tribler.pyipv8.ipv8.deprecated.payload import Payload
from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto
from Tribler.pyipv8.ipv8.messaging.serialization import Serializer

EPOCH = datetime(1970, 1, 1)
INFOHASH_SIZE = 20  # bytes


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
# deprecated by 2038, that is very soon.


def time2float(date_time, epoch=EPOCH):
    """
    Convert a datetime object to a float.
    :param date_time: The datetime object to convert.
    :param epoch: The epoch time, defaults to Jan 1, 1970.
    :return: The floating point representation of date_time.

    WARNING: TZ-aware timestamps are madhouse...
    For Python3 we could use a simpler method:
    >>> timestamp = (dt - datetime(1970, 1, 1, tzinfo=timezone.utc)) / timedelta(seconds=1)
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


class MetadataPayload(Payload):
    """
    Payload for metadata.
    """

    format_list = ['I', '74s', 'f', 'I', '64s']

    def __init__(self, metadata_type, public_key, timestamp, tc_pointer, signature):
        super(MetadataPayload, self).__init__()
        self.metadata_type = metadata_type
        self.public_key = public_key
        self.timestamp = timestamp
        self.tc_pointer = tc_pointer
        self.signature = signature

    def has_valid_signature(self):
        crypto = ECCrypto()
        serializer = Serializer()
        original_signature = self.signature

        # Make a payload where the signature is zero
        self.signature = EMPTY_SIG
        sig_data = serializer.pack_multiple(self.to_pack_list())[0]
        valid = crypto.is_valid_signature(crypto.key_from_public_bin(self.public_key), sig_data, original_signature)
        self.signature = original_signature
        return valid

    def to_pack_list(self):
        data = [('I', self.metadata_type),
                ('74s', self.public_key),
                ('f', self.timestamp),
                ('I', self.tc_pointer),
                ('64s', self.signature)]

        return data

    @classmethod
    def from_unpack_list(cls, metadata_type, public_key, timestamp, tc_pointer, signature):
        return MetadataPayload(metadata_type, public_key, timestamp, tc_pointer, signature)


class TorrentMetadataPayload(MetadataPayload):
    """
    Payload for metadata that stores a torrent.
    """
    format_list = MetadataPayload.format_list + ['20s', 'I', 'varlenI', 'varlenI']

    def __init__(self, metadata_type, public_key, timestamp, tc_pointer, signature, infohash, size, title, tags):
        super(TorrentMetadataPayload, self).__init__(metadata_type, public_key, timestamp, tc_pointer, signature)
        self.infohash = infohash
        self.size = size
        self.title = title
        self.tags = tags

    def to_pack_list(self):
        data = super(TorrentMetadataPayload, self).to_pack_list()
        data.append(('20s', self.infohash))
        data.append(('I', self.size))
        data.append(('varlenI', self.title))
        data.append(('varlenI', self.tags))
        return data

    @classmethod
    def from_unpack_list(cls, metadata_type, public_key, timestamp, tc_pointer, signature, infohash, size, title, tags):
        return TorrentMetadataPayload(metadata_type, public_key, timestamp, tc_pointer, signature, infohash, size,
                                      title, tags)


class ChannelMetadataPayload(TorrentMetadataPayload):
    """
    Payload for metadata that stores a channel.
    """
    format_list = TorrentMetadataPayload.format_list + ['I']

    def __init__(self, metadata_type, public_key, timestamp, tc_pointer, signature, infohash, size, title, tags,
                 version):
        super(ChannelMetadataPayload, self).__init__(metadata_type, public_key, timestamp, tc_pointer, signature,
                                                     infohash, size, title, tags)
        self.version = version

    def to_pack_list(self):
        data = super(ChannelMetadataPayload, self).to_pack_list()
        data.append(('I', self.version))
        return data

    @classmethod
    def from_file(cls, filepath):
        with open(filepath, 'rb') as f:
            serializer = Serializer()
            serialized_data = f.read()
            return serializer.unpack_to_serializables([cls, ], serialized_data)[0]

    @classmethod
    def from_unpack_list(cls, metadata_type, public_key, timestamp, tc_pointer, signature, infohash, size, title, tags,
                         version):
        return ChannelMetadataPayload(metadata_type, public_key, timestamp, tc_pointer, signature, infohash, size,
                                      title, tags, version)


class DeletedMetadataPayload(MetadataPayload):
    """
    Payload for metadata that stores deleted metadata.
    """
    format_list = MetadataPayload.format_list + ['64s']

    def __init__(self, metadata_type, public_key, timestamp, tc_pointer, signature, delete_signature):
        super(DeletedMetadataPayload, self).__init__(metadata_type, public_key, timestamp, tc_pointer, signature)
        self.delete_signature = delete_signature

    def to_pack_list(self):
        data = super(DeletedMetadataPayload, self).to_pack_list()
        data.append(('64s', self.delete_signature))
        return data

    @classmethod
    def from_unpack_list(cls, metadata_type, public_key, timestamp, tc_pointer, signature, delete_signature):
        return DeletedMetadataPayload(metadata_type, public_key, timestamp, tc_pointer, signature, delete_signature)

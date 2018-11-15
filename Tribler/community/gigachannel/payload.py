from Tribler.pyipv8.ipv8.deprecated.payload import Payload


class TruncatedChannelPayload(Payload):
    """
    Small representation of a channel containing a:

     - 20 character infohash
     - 64 character channel title (possibly truncated)
     - 64 character public key (LibNaCLPK without "LibNaCLPK:" prefix)
     - 8 byte channel version

     In total this message is 156 bytes.
    """

    format_list = ['20s', '64s', '64s', 'Q']

    def __init__(self, infohash, title, public_key, version):
        self.infohash = infohash
        self.title = title
        self.public_key = public_key
        self.version = version

    def to_pack_list(self):
        return [('20s', self.infohash),
                ('64s', self.title),
                ('64s', self.public_key),
                ('Q', self.version)]

    @classmethod
    def from_unpack_list(cls, infohash, title, public_key, version):
        return cls(infohash, title, public_key, version)


class TruncatedChannelPlayloadBlob(Payload):
    """
    Collection of TruncatedChannelPayloads.

    This message can fit from 1 up to 7 TruncatedChannelPayloads.
    The size of this message is therefore from 156 up to 1092 bytes.
    """

    format_list = [TruncatedChannelPayload]
    optional_format_list = [TruncatedChannelPayload] * 6

    def __init__(self, payload_list):
        self.payload_list = payload_list

    def to_pack_list(self):
        return [('payload', payload) for payload in self.payload_list[:7]]

    @classmethod
    def from_unpack_list(cls, *args):
        return cls(args)

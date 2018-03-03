from Tribler.pyipv8.ipv8.deprecated.payload import Payload


class ChannelPayload(Payload):

    format_list = ['20s']

    def __init__(self, info_hash):
        self.info_hash = info_hash

    def to_pack_list(self):
        return [('20s', self.info_hash)]

    @classmethod
    def from_unpack_list(cls, *args):
        return cls(args[0])

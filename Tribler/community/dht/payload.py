from struct import pack, unpack, unpack_from, calcsize
from socket import inet_aton, inet_ntoa

from Tribler.pyipv8.ipv8.deprecated.payload import Payload
from Tribler.community.dht.routing import Node


def encode_values(values):
    return ''.join([pack('!H', len(value)) + value for value in values])


def decode_values(values_str):
    values = []
    index = 0
    while index < len(values_str):
        length = unpack_from('!H', values_str, offset=index)[0]
        index += calcsize('!H')
        values.append(values_str[index:index + length])
        index += length
    return values


def encode_nodes(nodes):
    nodes_str = ''
    for node in nodes:
        key = node.public_key.key_to_bin()
        nodes_str += inet_aton(node.address[0]) + pack("!H", node.address[1])
        nodes_str += pack('!H', len(key)) + key
    return nodes_str


def decode_nodes(nodes_str):
    nodes = []
    index = 0
    while index < len(nodes_str):
        ip, port, key_length = unpack('!4sHH', nodes_str[index:index + 8])
        index += 8
        address = (inet_ntoa(ip), port)
        key = nodes_str[index:index + key_length]
        index += key_length
        nodes.append(Node(key, address=address))
    return nodes


class BasePayload(Payload):

    format_list = ['I']

    def __init__(self, identifier):
        super(BasePayload, self).__init__()
        self.identifier = identifier

    def to_pack_list(self):
        return [('I', self.identifier)]

    @classmethod
    def from_unpack_list(cls, identifier):
        return BasePayload(identifier)


class PingRequestPayload(BasePayload):
    pass


class PingResponsePayload(BasePayload):
    pass


class StoreRequestPayload(BasePayload):

    format_list = BasePayload.format_list + ['20s', '20s', 'varlenH']

    def __init__(self, identifier, token, target, values):
        super(StoreRequestPayload, self).__init__(identifier)
        self.token = token
        self.target = target
        self.values = values

    def to_pack_list(self):
        data = super(StoreRequestPayload, self).to_pack_list()
        data.append(('20s', self.token))
        data.append(('20s', self.target))
        data.append(('varlenH', encode_values(self.values)))
        return data

    @classmethod
    def from_unpack_list(cls, identifier, token, target, values_str):
        values = decode_values(values_str)
        return StoreRequestPayload(identifier, token, target, values)


class StoreResponsePayload(BasePayload):
    pass


class FindRequestPayload(BasePayload):

    format_list = BasePayload.format_list + ['varlenI', '20s', '?']

    def __init__(self, identifier, lan_address, target, force_nodes):
        super(FindRequestPayload, self).__init__(identifier)
        self.lan_address = lan_address
        self.target = target
        self.force_nodes = force_nodes

    def to_pack_list(self):
        data = super(FindRequestPayload, self).to_pack_list()
        data.append(('varlenI', inet_aton(self.lan_address[0]) + pack("!H", self.lan_address[1])))
        data.append(('20s', self.target))
        data.append(('?', self.force_nodes))
        return data

    @classmethod
    def from_unpack_list(cls, identifier, lan_address, target, force_nodes):
        return FindRequestPayload(identifier,
                                  (inet_ntoa(lan_address[:4]), unpack('!H', lan_address[4:6])[0]),
                                  target,
                                  force_nodes)


class FindResponsePayload(BasePayload):

    format_list = BasePayload.format_list + ['20s', 'varlenH', 'varlenH']

    def __init__(self, identifier, token, values, nodes):
        super(FindResponsePayload, self).__init__(identifier)
        self.token = token
        self.values = values
        self.nodes = nodes

    def to_pack_list(self):
        data = super(FindResponsePayload, self).to_pack_list()
        data.append(('20s', self.token))
        data.append(('varlenH', encode_values(self.values)))
        data.append(('varlenH', encode_nodes(self.nodes)))
        return data

    @classmethod
    def from_unpack_list(cls, identifier, token, values_str, nodes_str):
        return FindResponsePayload(identifier, token, decode_values(values_str), decode_nodes(nodes_str))


class StrPayload(Payload):

    format_list = ['raw']

    def __init__(self, data):
        super(StrPayload, self).__init__()
        self.data = data

    def to_pack_list(self):
        return [('raw', self.data)]

    @classmethod
    def from_unpack_list(cls, data):
        return StrPayload(data)


class SignedStrPayload(Payload):

    format_list = ['varlenH', 'I', 'varlenH']

    def __init__(self, data, version, public_key):
        super(SignedStrPayload, self).__init__()
        self.data = data
        self.version = version
        self.public_key = public_key

    def to_pack_list(self):
        return [('varlenH', self.data),
                ('I', self.version),
                ('varlenH', self.public_key)]

    @classmethod
    def from_unpack_list(cls, data, version, public_key):
        return SignedStrPayload(data, version, public_key)


class StorePeerRequestPayload(BasePayload):

    format_list = BasePayload.format_list + ['20s', '20s']

    def __init__(self, identifier, token, target):
        super(StorePeerRequestPayload, self).__init__(identifier)
        self.token = token
        self.target = target

    def to_pack_list(self):
        data = super(StorePeerRequestPayload, self).to_pack_list()
        data.append(('20s', self.token))
        data.append(('20s', self.target))
        return data

    @classmethod
    def from_unpack_list(cls, identifier, token, target):
        return StorePeerRequestPayload(identifier, token, target)


class StorePeerResponsePayload(BasePayload):
    pass


class ConnectPeerRequestPayload(BasePayload):

    format_list = BasePayload.format_list + ['varlenI', '20s']

    def __init__(self, identifier, lan_address, target):
        super(ConnectPeerRequestPayload, self).__init__(identifier)
        self.lan_address = lan_address
        self.target = target

    def to_pack_list(self):
        data = super(ConnectPeerRequestPayload, self).to_pack_list()
        data.append(('varlenI', inet_aton(self.lan_address[0]) + pack("!H", self.lan_address[1])))
        data.append(('20s', self.target))
        return data

    @classmethod
    def from_unpack_list(cls, identifier, lan_address, target):
        return ConnectPeerRequestPayload(identifier,
                                         (inet_ntoa(lan_address[:4]), unpack('!H', lan_address[4:6])[0]),
                                         target)


class ConnectPeerResponsePayload(BasePayload):

    format_list = BasePayload.format_list + ['varlenH']

    def __init__(self, identifier, nodes):
        super(ConnectPeerResponsePayload, self).__init__(identifier)
        self.nodes = nodes

    def to_pack_list(self):
        data = super(ConnectPeerResponsePayload, self).to_pack_list()
        data.append(('varlenH', encode_nodes(self.nodes)))
        return data

    @classmethod
    def from_unpack_list(cls, identifier, nodes):
        return ConnectPeerResponsePayload(identifier, decode_nodes(nodes))

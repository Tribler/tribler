from socket import inet_ntoa, inet_aton
from struct import pack, unpack_from

from Tribler.community.tunnel.conversion import TunnelConversion


class HiddenTunnelConversion(TunnelConversion):

    def __init__(self, community):
        super(HiddenTunnelConversion, self).__init__(community)

        self.define_meta_message(chr(30),
                                 community.get_meta_message(u"establish-intro"),
                                 self._encode_establish_intro,
                                 self._decode_establish_intro)
        self.define_meta_message(chr(31),
                                 community.get_meta_message(u"intro-established"),
                                 self._encode_intro_established,
                                 self._decode_intro_established)
        self.define_meta_message(chr(32),
                                 community.get_meta_message(u"key-request"),
                                 self._encode_keys_request,
                                 self._decode_keys_request)
        self.define_meta_message(chr(33),
                                 community.get_meta_message(u"key-response"),
                                 self._encode_keys_response,
                                 self._decode_keys_response)
        self.define_meta_message(chr(34),
                                 community.get_meta_message(u"establish-rendezvous"),
                                 self._encode_establish_rendezvous,
                                 self._decode_establish_rendezvous)
        self.define_meta_message(chr(35),
                                 community.get_meta_message(u"rendezvous-established"),
                                 self._encode_rendezvous_established,
                                 self._decode_rendezvous_established)
        self.define_meta_message(chr(36),
                                 community.get_meta_message(u"create-e2e"),
                                 self._encode_create_e2e,
                                 self._decode_create_e2e)
        self.define_meta_message(chr(37),
                                 community.get_meta_message(u"created-e2e"),
                                 self._encode_created_e2e,
                                 self._decode_created_e2e)
        self.define_meta_message(chr(38),
                                 community.get_meta_message(u"link-e2e"),
                                 self._encode_link_e2e,
                                 self._decode_link_e2e)
        self.define_meta_message(chr(39),
                                 community.get_meta_message(u"linked-e2e"),
                                 self._encode_linked_e2e,
                                 self._decode_linked_e2e)
        self.define_meta_message(chr(40),
                                 community.get_meta_message(u"dht-request"),
                                 self._encode_dht_request,
                                 self._decode_dht_request)
        self.define_meta_message(chr(41),
                                 community.get_meta_message(u"dht-response"),
                                 self._encode_dht_response,
                                 self._decode_dht_response)

    def _encode_establish_intro(self, message):
        return pack('!IH20s', message.payload.circuit_id, message.payload.identifier, message.payload.info_hash),

    def _decode_establish_intro(self, placeholder, offset, data):
        circuit_id, identifier, info_hash = unpack_from('!IH20s', data, offset)
        offset += 26

        return offset, placeholder.meta.payload.implement(circuit_id, identifier, info_hash)

    def _encode_intro_established(self, message):
        return pack('!IH', message.payload.circuit_id, message.payload.identifier),

    def _decode_intro_established(self, placeholder, offset, data):
        circuit_id, identifier = unpack_from('!IH', data, offset)
        offset += 6

        return offset, placeholder.meta.payload.implement(circuit_id, identifier)

    def _encode_establish_rendezvous(self, message):
        return pack('!IH20s', message.payload.circuit_id, message.payload.identifier, message.payload.cookie),

    def _decode_establish_rendezvous(self, placeholder, offset, data):
        circuit_id, identifier, cookie = unpack_from('!IH20s', data, offset)
        offset += 26

        return offset, placeholder.meta.payload.implement(circuit_id, identifier, cookie)

    def _encode_rendezvous_established(self, message):
        host, port = message.payload.rendezvous_point_addr
        return pack('!IH4sH', message.payload.circuit_id, message.payload.identifier, inet_aton(host), port),

    def _decode_rendezvous_established(self, placeholder, offset, data):
        circuit_id, identifier = unpack_from('!IH', data, offset)
        offset += 6

        host, port = unpack_from('!4sH', data, offset)
        rendezvous_point_addr = (inet_ntoa(host), port)
        offset += 6

        return offset, placeholder.meta.payload.implement(circuit_id, identifier, rendezvous_point_addr)

    def _encode_keys_request(self, message):
        return pack('!H20s', message.payload.identifier, message.payload.info_hash),

    def _decode_keys_request(self, placeholder, offset, data):
        identifier, info_hash = unpack_from('!H20s', data, offset)
        offset += 22
        return offset, placeholder.meta.payload.implement(identifier, info_hash)

    def _encode_keys_response(self, message):
        return pack('!HH', message.payload.identifier, len(message.payload.public_key)) \
            + message.payload.public_key + message.payload.pex_peers,

    def _decode_keys_response(self, placeholder, offset, data):
        identifier, len_public_key = unpack_from('!HH', data, offset)
        offset += 4

        public_key = data[offset: offset + len_public_key]
        offset += len_public_key

        pex_peers = data[offset:]
        offset += len(pex_peers)

        return offset, placeholder.meta.payload.implement(identifier, public_key, pex_peers)

    def _encode_create_e2e(self, message):
        payload = message.payload
        packet = pack("!H20sHH20s", payload.identifier, payload.info_hash, len(payload.node_public_key),
                      len(payload.key), payload.node_id) + payload.node_public_key + payload.key
        return packet,

    def _decode_create_e2e(self, placeholder, offset, data):
        identifier, info_hash, len_pubic_key, len_key, nodeid = unpack_from('!H20sHH20s', data, offset)
        offset += 46

        node_public_key = data[offset: offset + len_pubic_key]
        offset += len_pubic_key

        key = data[offset:offset + len_key]
        offset += len_key

        return offset, placeholder.meta.payload.implement(identifier, info_hash, nodeid, node_public_key, key)

    def _encode_created_e2e(self, message):
        payload = message.payload
        return pack("!HH32s", payload.identifier, len(payload.key), payload.auth) + payload.key + payload.rp_sock_addr,

    def _decode_created_e2e(self, placeholder, offset, data):
        identifier, len_key, auth = unpack_from('!HH32s', data, offset)
        offset += 36

        key = data[offset:offset + len_key]
        offset += len_key

        rp_sock_addr = data[offset:]
        offset += len(rp_sock_addr)

        return offset, placeholder.meta.payload.implement(identifier, key, auth, rp_sock_addr)

    def _encode_link_e2e(self, message):
        payload = message.payload
        return pack("!IH20s", payload.circuit_id, payload.identifier, payload.cookie),

    def _decode_link_e2e(self, placeholder, offset, data):
        circuit_id, identifier, cookie = unpack_from('!IH20s', data, offset)
        offset += 26

        return offset, placeholder.meta.payload.implement(circuit_id, identifier, cookie)

    def _encode_linked_e2e(self, message):
        payload = message.payload
        return pack("!IH", payload.circuit_id, payload.identifier),

    def _decode_linked_e2e(self, placeholder, offset, data):
        circuit_id, identifier = unpack_from('!IH', data, offset)
        offset += 6
        return offset, placeholder.meta.payload.implement(circuit_id, identifier)

    def _encode_dht_request(self, message):
        return pack('!IH20s',
                    message.payload.circuit_id,
                    message.payload.identifier,
                    message.payload.info_hash),

    def _decode_dht_request(self, placeholder, offset, data):
        circuit_id, identifier, info_hash = unpack_from('!IH20s', data, offset)
        offset += 26
        return offset, placeholder.meta.payload.implement(circuit_id, identifier, info_hash)

    def _encode_dht_response(self, message):
        return pack('!IH20s',
                    message.payload.circuit_id,
                    message.payload.identifier,
                    message.payload.info_hash) + message.payload.peers,

    def _decode_dht_response(self, placeholder, offset, data):
        circuit_id, identifier, info_hash = unpack_from('!IH20s', data, offset)
        offset += 26

        peers = data[offset:]
        offset += len(peers)

        return offset, placeholder.meta.payload.implement(circuit_id, identifier, info_hash, peers)

from M2Crypto.EC import EC_pub
import logging
import M2Crypto

from Tribler.community.anontunnel.globals import MESSAGE_CREATED, ORIGINATOR, ENDPOINT, MESSAGE_CREATE
from Tribler.dispersy.member import Member


logger = logging.getLogger(__name__)


class NoCrypto(object):
    def enable(self, proxy):
        pass

    def disable(self):
        pass


class DefaultCrypto(object):
    def __init__(self):
        self.proxy = None
        """ :type proxy: Tribler.community.anontunnel.community.ProxyCommunity """

    @property
    def session_keys(self):
        return self.proxy.session_keys if self.proxy else {}

    def enable(self, proxy):

        """
        :type proxy: Tribler.community.anontunnel.community.ProxyCommunity
        :param proxy:
        """
        self.proxy = proxy

        proxy.add_relay_transformer(self._crypto_relay)
        proxy.add_receive_transformer(self._crypto_incoming)
        proxy.add_send_transformer(self._crypto_outgoing)
        proxy.add_message_filter(MESSAGE_CREATE, self._on_create)

    def disable(self):
        self.proxy.remove_relay_transformer(self._crypto_relay)
        self.proxy.remove_receive_transformer(self._crypto_incoming)
        self.proxy.remove_send_transformer(self._crypto_outgoing)
        self.proxy.remove_message_filter(MESSAGE_CREATE, self._on_create)

    def _on_create(self, candidate, circuit_id, payload):
        return payload

    def _crypto_outgoing(self, candidate, circuit_id, message_type, content):
        relay_key = (candidate, circuit_id)
        if circuit_id in self.proxy.circuits and not self.proxy.circuits[circuit_id].unverified_hop:
            # I am the originator so I have to create the full onion
            circuit = self.proxy.circuits[circuit_id]
            hops = circuit.hops

            for hop in reversed(hops):
                logger.debug("Adding AES layer for hop %s:%s with key %s" % (hop.host, hop.port, hop.session_key))
                content = AESencode(hop.session_key, content)
        elif relay_key in self.session_keys:
            content = AESencode(self.session_keys[relay_key], content)
            logger.debug(
                "Adding AES layer for circuit %s with key %s" % (circuit_id, self.session_keys[relay_key]))

        elif message_type == MESSAGE_CREATED or message_type == MESSAGE_CREATE:
                logger.debug("Adding public key encryption for circuit %s" % (circuit_id))
                candidate_key = iter(candidate.get_members()).next()._ec
                content = self.proxy.dispersy.crypto.encrypt(candidate_key, content)
                logger.error("Length of encrypted outgoing content: {}".format(len(content)))

        return content

    def _crypto_relay(self, direction, candidate, circuit_id, data):
        relay_key = (candidate, circuit_id)
        next_relay = self.proxy.relay_from_to[relay_key]
        next_relay_key = (candidate, next_relay)

        if direction == ORIGINATOR:
            # Message is going downstream so I have to add my onion layer
            # logger.debug("Adding AES layer with key %s to circuit %d" % (self.session_keys[next_relay.circuit_id], next_relay.circuit_id))
            data = AESencode(self.session_keys[next_relay_key], data)

        elif direction == ENDPOINT:
            # Message is going upstream so I have to remove my onion layer
            # logger.debug("Removing AES layer with key %s" % self.session_keys[circuit_id])
            data = AESdecode(self.session_keys[relay_key], data)

        return data

    def _crypto_incoming(self, candidate, circuit_id, data):
        relay_key = (candidate, circuit_id)
        if circuit_id in self.proxy.circuits:
            # I am the originator so I'll peel the onion skins
            for hop in self.proxy.circuits[circuit_id].hops:
                logger.debug("Removing AES layer for %s:%s with key %s" % (hop.host, hop.port, hop.session_key))
                data = AESdecode(hop.session_key, data)

        elif relay_key in self.session_keys:
            # last node in circuit, circuit already exists
            logger.debug("Removing AES layer with key %s" % (self.session_keys[relay_key]))
            data = AESdecode(self.session_keys[relay_key], data)
        else:
            # last node in circuit, circuit does not exist yet, decrypt with elgamal key
            my_key = self.proxy.my_member._ec
            logger.error("Length of encrypted incoming content: {}".format(len(data)))
            data = self.proxy.dispersy.crypto.decrypt(my_key, data)

        return data


def get_cryptor( op, key, alg='aes_128_ecb', iv=None ):
    if iv == None:
        iv = '\0' * 256
    cryptor = M2Crypto.EVP.Cipher( alg=alg, key=key, iv=iv, op=op)
    return cryptor


def AESencode( key, plaintext ):
    cryptor = get_cryptor( 1, key )
    ret = cryptor.update( plaintext )
    ret = ret + cryptor.final()
    return ret


def AESdecode( key, ciphertext ):
    cryptor = get_cryptor( 0, key )
    ret = cryptor.update( ciphertext )
    ret = ret + cryptor.final()
    return ret
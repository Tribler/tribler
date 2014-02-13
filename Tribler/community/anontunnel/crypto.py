import logging
import M2Crypto

from Tribler.community.anontunnel.globals import MESSAGE_CREATED, ORIGINATOR, \
    ENDPOINT, MESSAGE_CREATE

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

        proxy.relay_transformers.append(self._crypto_relay)
        proxy.receive_transformers.append(self._crypto_incoming)
        proxy.send_transformers.append(self._crypto_outgoing)

    def disable(self):
        self.proxy.relay_transformers.remove(self._crypto_relay)
        self.proxy.receive_transformers.remove(self._crypto_incoming)
        self.proxy.send_transformers.remove(self._crypto_outgoing)

    def _crypto_outgoing(self, candidate, circuit_id, message_type, content):
        relay_key = (candidate.sock_addr, circuit_id)
        logger.debug(
            "Crypto_outgoing for circuit {0} and message type {1}".format(
                circuit_id, ord(message_type)))

        # CREATE and CREATED have to be Elgamal encrypted
        if message_type == MESSAGE_CREATED or message_type == MESSAGE_CREATE:
            logger.debug(
                "Adding public key encryption for circuit %s" % circuit_id)
            candidate_pub_key = iter(candidate.get_members()).next()._ec
            content = self.proxy.dispersy.crypto.encrypt(candidate_pub_key,
                                                         content)

        # If own circuit, AES layers have to be added
        elif circuit_id in self.proxy.circuits:
            # I am the originator so I have to create the full onion
            circuit = self.proxy.circuits[circuit_id]
            hops = circuit.hops
            for hop in reversed(hops):
                logger.debug("Adding AES layer for hop %s:%s with key %s" % (
                hop.host, hop.port, hop.session_key))
                content = aes_encode(hop.session_key, content)

        # Else add AES layer
        elif relay_key in self.session_keys:
            content = aes_encode(self.session_keys[relay_key], content)
            logger.debug(
                "Adding AES layer for circuit %s with key %s" % (
                circuit_id, self.session_keys[relay_key]))

        logger.debug("Length of outgoing message: {0}".format(len(content)))
        return content

    def _crypto_relay(self, direction, sock_addr, circuit_id, data):
        relay_key = (sock_addr, circuit_id)
        next_relay = self.proxy.relay_from_to[relay_key]
        next_relay_key = (next_relay.sock_addr, next_relay.circuit_id)

        # Message is going downstream so I have to add my onion layer
        if direction == ORIGINATOR:
            logger.debug(
                "AES encoding circuit {0} towards ORIGINATOR, key {1}".format(
                    next_relay.circuit_id,
                    self.session_keys[
                        next_relay_key]))
            data = aes_encode(self.session_keys[next_relay_key], data)

        # Message is going upstream so I have to remove my onion layer
        elif direction == ENDPOINT:
            logger.debug(
                "AES decoding circuit {0} towards ENDPOINT, key {1}".format(
                    next_relay.circuit_id,
                    self.session_keys[relay_key]))
            data = aes_decode(self.session_keys[relay_key], data)

        return data

    def _crypto_incoming(self, candidate, circuit_id, data):
        relay_key = (candidate.sock_addr, circuit_id)
        logger.debug("Crypto_incoming for circuit {0}".format(circuit_id))
        logger.debug("Length of incoming message: {0}".format(len(data)))

        # If I am the circuits originator I want to peel layers
        if circuit_id in self.proxy.circuits and len(
                self.proxy.circuits[circuit_id].hops) > 0:
            # I am the originator so I'll peel the onion skins
            logger.debug(
                "I am the circuit originator, I am going to peel layers")
            for hop in self.proxy.circuits[circuit_id].hops:
                logger.debug(
                    "Peeling layer with key {0}".format(hop.session_key))
                data = aes_decode(hop.session_key, data)

        # I'm the last node in the circuit, probably an EXTEND message, decrypt with AES
        elif relay_key in self.session_keys:
            # last node in circuit, circuit already exists
            logger.debug(
                "I am the last node in the already existing circuit, decrypt with AES")
            data = aes_decode(self.session_keys[relay_key], data)

        # I don't know the sender! Let's decrypt with my private Elgamal key
        else:
            # last node in circuit, circuit does not exist yet, decrypt with Elgamal key
            logger.error(
                "Circuit does not yet exist, decrypting with my Elgamal key")
            my_key = self.proxy.my_member._ec
            data = self.proxy.dispersy.crypto.decrypt(my_key, data)

        return data


# M2 CRYPTO AES code, should be substituted with Niels's lib which implements these

def get_cryptor(op, key, alg='aes_128_ecb', iv=None):
    if iv is None:
        iv = '\0' * 256
    cryptor = M2Crypto.EVP.Cipher(alg=alg, key=key, iv=iv, op=op)
    return cryptor


def aes_encode(key, plaintext):
    cryptor = get_cryptor(1, key)
    ret = cryptor.update(plaintext)
    ret = ret + cryptor.final()
    return ret


def aes_decode(key, ciphertext):
    cryptor = get_cryptor(0, key)
    ret = cryptor.update(ciphertext)
    ret = ret + cryptor.final()
    return ret
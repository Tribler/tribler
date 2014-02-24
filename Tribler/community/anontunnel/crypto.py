import logging
import M2Crypto

from Tribler.community.anontunnel.globals import MESSAGE_CREATED, ORIGINATOR, \
    ENDPOINT, MESSAGE_CREATE

logger = logging.getLogger()


class CryptoError(Exception):
    pass


class NoCrypto(object):
    def enable(self, proxy):
        pass

    def disable(self):
        pass


class DefaultCrypto(object):
    def __init__(self):
        self.proxy = None
        """ :type proxy: ProxyCommunity """

    @property
    def session_keys(self):
        return self.proxy.session_keys if self.proxy else {}

    def enable(self, proxy):

        """
        :type proxy: ProxyCommunity
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
        """
        Apply crypto to outgoing messages. The current protocol handles 3
        distinct cases: CREATE/CREATED, ORIGINATOR, ENDPOINT / RELAY.

        Messages of type CREATE or CREATED are encrypted using Elgamal, when
        these messages are received they need to be encrypted using the
        recipients PUBLIC KEY.

        If you have a SESSION KEY for the outgoing message use it to encrypt
        the packet, in this case you are a hop of the circuit. This adds a
        layer to the onion.

        If you do not have a SESSION KEY for the outgoing message but created
        the circuit encrypt it with the SESSION KEY linked to the circuit
        itself

        @param Candidate candidate: the recipient of the message
        @param int circuit_id: the circuit to sent the message over
        @param str message_type: the message's type
        @param str content: the raw (serialized) content of the message
        @rtype: str
        @return: the encrypted payload
        """

        relay_key = (candidate.sock_addr, circuit_id)
        logger.debug(
            "Crypto_outgoing for circuit {0} and message type {1}".format(
                circuit_id, ord(message_type)))

        # CREATE and CREATED have to be Elgamal encrypted
        if message_type == MESSAGE_CREATED or message_type == MESSAGE_CREATE:
            logger.debug("public key encryption for circuit %s" % circuit_id)
            candidate_pub_key = iter(candidate.get_members()).next()._ec
            content = self.proxy.crypto.encrypt(candidate_pub_key, content)
        # Else add AES layer
        elif relay_key in self.session_keys:
            content = aes_encode(self.session_keys[relay_key], content)
            logger.debug("Adding AES layer for circuit %s with key %s" % (
                circuit_id, self.session_keys[relay_key]))
        # If own circuit, AES layers have to be added
        elif circuit_id in self.proxy.circuits:
            # I am the originator so I have to create the full onion
            circuit = self.proxy.circuits[circuit_id]
            hops = circuit.hops
            for hop in reversed(hops):
                logger.debug(
                    "Adding AES layer for hop %s:%s with key %s" %
                    (hop.host, hop.port, hop.session_key)
                )
                content = aes_encode(hop.session_key, content)
        else:
            raise CryptoError("Don't know how to encrypt outgoing message")

        logger.debug("Length of outgoing message: {0}".format(len(content)))
        return content

    def _crypto_relay(self, direction, sock_addr, circuit_id, data):
        """
        Crypto RELAY messages. Two distinct cases are considered: relaying to
        the ENDPOINT and relaying back to the ORIGINATOR.

        When relaying to the ENDPOINT we need to strip one layer of the onion,
        before forwarding the packet to the next hop. This is done by
        decrypting with our SESSION_KEY.

        In the case that we relay towards the ORIGINATOR an additional onion
        layer must be added. This is done by encrypting with our SESSION KEY

        @param str direction: the direction of the relay
        @param sock_addr: the destination of the relay message
        @param circuit_id: the destination circuit
        @param data: the data to relay
        @return: the onion encrypted payload
        @rtype: str
        """
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
        else:
            raise ValueError("The parameter 'direction' must be either"
                             "ORIGINATOR or ENDPOINT")

        return data

    def _crypto_incoming(self, candidate, circuit_id, data):
        """
        Decrypt incoming packets. Three cases are considered. The case that
        we are the ENDPOINT of the circuit, the case that we are the ORIGINATOR
        and finally the case that we are neither. This means that this is our
        first packet on this circuit and that it MUST be a CREATE or CREATED
        message

        @todo: Check whether it really is a CREATE or CREATED message ?

        @param Candidate candidate: the candidate we got the message from
        @param int circuit_id: the circuit we got the message on
        @param str data: the raw payload we received
        @return: the decrypted payload
        @rtype: str
        """

        relay_key = (candidate.sock_addr, circuit_id)
        logger.debug("Crypto_incoming for circuit {0}".format(circuit_id))
        logger.debug("Length of incoming message: {0}".format(len(data)))

        # I'm the last node in the circuit, probably an EXTEND message,
        # decrypt with AES
        if relay_key in self.session_keys:
            # last node in circuit, circuit already exists
            logger.debug("I am the last node in the already existing circuit, "
                         "decrypt with AES")
            data = aes_decode(self.session_keys[relay_key], data)

        # If I am the circuits originator I want to peel layers
        elif circuit_id in self.proxy.circuits and len(
                self.proxy.circuits[circuit_id].hops) > 0:
            # I am the originator so I'll peel the onion skins
            logger.debug(
                "I am the circuit originator, I am going to peel layers")
            for hop in self.proxy.circuits[circuit_id].hops:
                logger.debug(
                    "Peeling layer with key {0}".format(hop.session_key))
                data = aes_decode(hop.session_key, data)
        # I don't know the sender! Let's decrypt with my private Elgamal key
        else:
            # last node in circuit, circuit does not exist yet,
            # decrypt with Elgamal key
            logger.debug(
                "Circuit does not yet exist, decrypting with my Elgamal key")
            my_key = self.proxy.my_member._ec
            data = self.proxy.crypto.decrypt(my_key, data)

        return data


# M2 CRYPTO AES code, should be substituted with Niels's lib
# which implements these

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
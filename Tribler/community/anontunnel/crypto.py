from Crypto.Util.number import bytes_to_long, long_to_bytes
import M2Crypto
import hashlib
import logging
import random
from Tribler.Core.Utilities import encoding

from Tribler.community.anontunnel.globals import MESSAGE_CREATED, ORIGINATOR, \
    ENDPOINT, MESSAGE_CREATE, MESSAGE_EXTEND, MESSAGE_EXTENDED, \
    DIFFIE_HELLMAN_MODULUS, DIFFIE_HELLMAN_MODULUS_SIZE, \
    DIFFIE_HELLMAN_GENERATOR

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
        self._logger = logging.getLogger(__name__)
        self._received_secrets = {}

    @property
    def session_keys(self):
        return self.proxy.session_keys

    def enable(self, proxy):
        """
        :type proxy: ProxyCommunity
        :param proxy:
        """
        self.proxy = proxy

        proxy.relay_transformers.append(self._crypto_relay_packet)
        proxy.receive_transformers.append(self._crypto_incoming_packet)
        proxy.send_transformers.append(self._crypto_outgoing_packet)
        proxy.before_send_transformers[MESSAGE_CREATE]\
            .append(self._encrypt_create_content)
        proxy.before_send_transformers[MESSAGE_CREATED]\
            .append(self._encrypt_created_content)
        proxy.before_send_transformers[MESSAGE_EXTEND]\
            .append(self._encrypt_extend_content)
        proxy.before_send_transformers[MESSAGE_EXTENDED]\
            .append(self._encrypt_extended_content)
        proxy.after_receive_transformers[MESSAGE_CREATE]\
            .append(self._decrypt_create_content)
        proxy.after_receive_transformers[MESSAGE_CREATED]\
            .append(self._decrypt_created_content)
        proxy.after_receive_transformers[MESSAGE_EXTEND]\
            .append(self._decrypt_extend_content)
        proxy.after_receive_transformers[MESSAGE_EXTENDED]\
            .append(self._decrypt_extended_content)

    def disable(self):
        self.proxy.relay_transformers.remove(self._crypto_relay_packet)
        self.proxy.receive_transformers.remove(self._crypto_incoming_packet)
        self.proxy.send_transformers.remove(self._crypto_outgoing_packet)
        self.proxy.before_send_transformers[MESSAGE_CREATE]\
            .remove(self._encrypt_create_content)
        self.proxy.before_send_transformers[MESSAGE_CREATED]\
            .remove(self._encrypt_created_content)
        self.proxy.before_send_transformers[MESSAGE_EXTEND]\
            .remove(self._encrypt_extend_content)
        self.proxy.before_send_transformers[MESSAGE_EXTENDED]\
            .remove(self._encrypt_extended_content)
        self.proxy.after_receive_transformers[MESSAGE_CREATE]\
            .remove(self._decrypt_create_content)
        self.proxy.after_receive_transformers[MESSAGE_CREATED]\
            .remove(self._decrypt_created_content)
        self.proxy.after_receive_transformers[MESSAGE_EXTEND]\
            .remove(self._decrypt_extend_content)
        self.proxy.after_receive_transformers[MESSAGE_EXTENDED]\
            .remove(self._decrypt_extended_content)

    def _encrypt_create_content(self, candidate, circuit_id, message):
        """
        Method which encrypts the contents of a CREATE message before it
        is being sent. The only thing in a CREATE message that needs to be
        encrypted is the first part of the DIFFIE HELLMAN handshake, which is
        created in this method.

        @param Candidate candidate: Destination of the message
        @param int circuit_id: Circuit identifier
        @param CreateMessage message: Message as passed from the community
        @return CreateMessage: Version of the message with encrypted contents
        """
        dh_secret = random.getrandbits(DIFFIE_HELLMAN_MODULUS_SIZE)

        while dh_secret >= DIFFIE_HELLMAN_MODULUS:
            dh_secret = random.getrandbits(DIFFIE_HELLMAN_MODULUS_SIZE)
        dh_secret = 0
        dh_first_part = pow(DIFFIE_HELLMAN_GENERATOR, dh_secret,
                            DIFFIE_HELLMAN_MODULUS)
        pub_key = iter(candidate.get_members()).next()._ec

        encrypted_dh_first_part = self.proxy.crypto.encrypt(
            pub_key, long_to_bytes(dh_first_part,
                                   DIFFIE_HELLMAN_MODULUS_SIZE / 8))
        message.key = encrypted_dh_first_part

        if circuit_id in self.proxy.circuits:
            hop = self.proxy.circuits[circuit_id].unverified_hop
            hop.dh_secret = dh_secret
            hop.dh_first_part = dh_first_part
            hop.pub_key = pub_key

        return message

    def _decrypt_create_content(self, candidate, circuit_id, message):
        """
        The first part of the DIFFIE HELLMAN handshake is encrypted with
        Elgamal and is decrypted here

        @param Candidate candidate: Destination of the message
        @param int circuit_id: Circuit identifier
        @param CreateMessage message: Message as passed from the community
        @return CreateMessage: Message with decrypted contents
        """
        relay_key = (candidate.sock_addr, circuit_id)
        my_key = self.proxy.my_member._ec
        decrypted_dh_first_part = bytes_to_long(
            self.proxy.crypto.decrypt(my_key, message.key))
        message.key = decrypted_dh_first_part
        self._received_secrets[relay_key] = message.key
        return message

    def _encrypt_extend_content(self, candidate, circuit_id, message):
        """
        Method which encrypts the contents of an EXTEND message before it
        is being sent. The only thing in an EXTEND message that needs to be
        encrypted is the first part of the DIFFIE HELLMAN handshake, which is
        created in this method.

        @param Candidate candidate: Destination of the message
        @param int circuit_id: Circuit identifier
        @param ExtendMessage message: Message as passed from the community
        @return ExtendMessage: Version of the message with encrypted contents
        """
        dh_secret = random.getrandbits(DIFFIE_HELLMAN_MODULUS_SIZE)

        while dh_secret >= DIFFIE_HELLMAN_MODULUS:
            dh_secret = random.getrandbits(DIFFIE_HELLMAN_MODULUS_SIZE)
        dh_secret = 0
        dh_first_part = pow(DIFFIE_HELLMAN_GENERATOR, dh_secret,
                            DIFFIE_HELLMAN_MODULUS)

        pub_key = self.proxy.circuits[circuit_id].unverified_hop.pub_key

        encrypted_dh_first_part = self.proxy.crypto.encrypt(
            pub_key, long_to_bytes(dh_first_part,
                                   DIFFIE_HELLMAN_MODULUS_SIZE / 8))
        message.key = encrypted_dh_first_part

        hop = self.proxy.circuits[circuit_id].unverified_hop
        hop.dh_first_part = dh_first_part
        hop.dh_secret = dh_secret

        return message

    def _decrypt_extend_content(self, candidate, circuit_id, message):
        """
        Nothing is encrypted in an Extend message

        @param Candidate candidate: Destination of the message
        @param int circuit_id: Circuit identifier
        @param ExtendMessage message: Message as passed from the community
        @return ExtendMessage: Message with decrypted contents
        """
        return message

    def _encrypt_created_content(self, candidate, circuit_id, message):
        """
        Method which encrypts the contents of a CREATED message before it
        is being sent. There are two things that need to be encrypted in a
        CREATED message. The second part of the DIFFIE HELLMAN handshake, which
        is being generated and encrypted in this method, and the candidate
        list, which is passed from the community.

        @param Candidate candidate: Destination of the message
        @param int circuit_id: Circuit identifier
        @param CreatedMessage message: Message as passed from the community
        @return CreatedMessage: Version of the message with encrypted contents
        """
        relay_key = (candidate.sock_addr, circuit_id)
        dh_secret = random.getrandbits(DIFFIE_HELLMAN_MODULUS_SIZE)
        while dh_secret >= DIFFIE_HELLMAN_MODULUS:
            dh_secret = random.getrandbits(DIFFIE_HELLMAN_MODULUS_SIZE)

        dh_secret = 0
        key = pow(self._received_secrets[relay_key],
                  dh_secret, DIFFIE_HELLMAN_MODULUS)

        m = hashlib.sha1()
        m.update(str(key))
        key = m.digest()[0:16]

        self.proxy.session_keys[relay_key] = key
        return_key = pow(DIFFIE_HELLMAN_GENERATOR, dh_secret,
                         DIFFIE_HELLMAN_MODULUS)
        message.key = return_key
        message.candidate_list = self._encrypt_candidate_list(
            self.proxy.session_keys[relay_key], message.candidate_list)

        return message

    def _decrypt_created_content(self, candidate, circuit_id, message):
        """
        Nothing to decrypt if you're not the originator of the circuit. Else,
        The candidate list should be decrypted as if it was an Extended
        message.

        @param Candidate candidate: Destination of the message
        @param int circuit_id: Circuit identifier
        @param CreatedMessage message: Message as passed from the community
        @return CreatedMessage: Message with decrypted contents
        """
        if circuit_id in self.proxy.circuits:
            return self._decrypt_extended_content(
                candidate, circuit_id, message)
        return message

    def _encrypt_extended_content(self, candidate, circuit_id, message):
        """
        Everything is already encrypted in an Extended message

        @param Candidate candidate: Destination of the message
        @param int circuit_id: Circuit identifier
        @param ExtendedMessage | CreatedMessage message: Message as passed
        from the community
        @return ExtendedMessage: Same
        """
        return message

    def _decrypt_extended_content(self, candidate, circuit_id, message):
        """
        This method decrypts the contents of an encrypted Extended message.
        If the candidate list is undecryptable, the message is malformed and
        the circuit should be broken.

        @param Candidate candidate:
        @param int circuit_id:
        @param ExtendedMessage message:
        @return ExtendedMessage: Extended message with unencrypted contents
        """
        unverified_hop = self.proxy.circuits[circuit_id].unverified_hop
        session_key = pow(message.key,
                          unverified_hop.dh_secret,
                          DIFFIE_HELLMAN_MODULUS)
        m = hashlib.sha1()
        m.update(str(session_key))
        key = m.digest()[0:16]
        unverified_hop.session_key = key
        try:
            message.candidate_list = self._decrypt_candidate_list(
                unverified_hop.session_key, message.candidate_list)
        except:
            reason = "Can't decrypt candidate list!"
            self._logger.exception(reason)
            self.proxy.remove_circuit(circuit_id, reason)
            return None


        self.proxy.circuits[circuit_id].add_hop(unverified_hop)
        self.proxy.circuits[circuit_id].unverified_hop = None
        return message



    def _crypto_outgoing_packet(self, candidate, circuit_id, message_type, content):
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

    def _crypto_relay_packet(self, direction, sock_addr, circuit_id, data):
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
            data = aes_encode(
                self.session_keys[next_relay_key], data)

        # Message is going upstream so I have to remove my onion layer
        elif direction == ENDPOINT:
            logger.debug(
                "AES decoding circuit {0} towards ENDPOINT, key {1}".format(
                    next_relay.circuit_id,
                    self.session_keys[relay_key]))
            data = aes_decode(
                self.session_keys[relay_key], data)
        else:
            raise ValueError("The parameter 'direction' must be either"
                             "ORIGINATOR or ENDPOINT")

        return data

    def _crypto_incoming_packet(self, candidate, circuit_id, data):
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
            data = aes_decode(
                self.session_keys[relay_key], data)

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

    def _encrypt_candidate_list(self, key, cand_dict):
        """
        This method encrypts a candidate list with the given public elgamal key

        @param EC_Pub key: Elliptic Curve Elgamal key
        @param dict cand_dict: Dict with candidates
        @return string: encoded version of the candidate dict
        """
        encoded_dict = encoding.encode(cand_dict)
        return aes_encode(key, encoded_dict)

    def _decrypt_candidate_list(self, key, encrypted_cand_dict):
        """
        This method decrypts a candidate list with the given private elgamal
        key

        @param key: Private Elliptic Curve Elgamal key
        @param string cand_dict: Encoded dict
        @return dict: Dict filled with candidates
        """
        encoded_dict = aes_decode(key, encrypted_cand_dict)
        offset, cand_dict = encoding.decode(encoded_dict)
        return cand_dict

# SHOULD BE IMPORTED FROM NIELS

def get_cryptor(op, key, alg='aes_128_ecb', iv=None):
    if iv is None:
        iv = chr(0) * 256
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
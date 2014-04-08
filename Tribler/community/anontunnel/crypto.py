from Crypto.Util.number import bytes_to_long, long_to_bytes
from Tribler.community.privatesemantic.crypto.optional_crypto import mpz, rand
from collections import defaultdict
import hashlib
import logging
from Tribler.Core.Utilities import encoding
from Tribler.Core.Utilities.encoding import encode, decode
from Tribler.community.anontunnel.events import TunnelObserver
from Tribler.community.privatesemantic.crypto.optional_crypto import \
    aes_encrypt_str, aes_decrypt_str

from Tribler.community.anontunnel.globals import MESSAGE_CREATED, ORIGINATOR, \
    ENDPOINT, MESSAGE_CREATE, MESSAGE_EXTEND, MESSAGE_EXTENDED, \
    DIFFIE_HELLMAN_MODULUS, DIFFIE_HELLMAN_MODULUS_SIZE, \
    DIFFIE_HELLMAN_GENERATOR


class CryptoError(Exception):
    pass


class Crypto(TunnelObserver):

    def __init__(self):
        TunnelObserver.__init__(self)
        self.outgoing_packet_crypto = lambda candidate, circuit, message, payload: payload
        self.incoming_packet_crypto = lambda candidate, circuit, payload: payload
        self.relay_packet_crypto = lambda destination, circuit, message_type, content: content
        self.encrypt_outgoing_packet_content = defaultdict()
        self.decrypt_incoming_packet_content = defaultdict()
        self._logger = logging.getLogger(__name__)

    def handle_incoming_packet(self, candidate, circuit_id, data):
        """
        As soon as a packet comes in it has to be decrypted depending on candidate / circuit id
        @param candidate: The originator of the packet
        @param circuit_id: The circuit ID in the packet
        @param data: The packet data
        @return: The unencrypted data
        """

        data = self.incoming_packet_crypto(candidate, circuit_id, data)
        if not data:
            return None
        return data

    def handle_incoming_packet_content(self, candidate, circuit_id, payload, packet_type):
        """
        As soon as an incoming packet is decrypted, the content has to be decrypted
        depending on the packet type
        @param candidate: The originator of the packet
        @param circuit_id: The circuit ID in the packet
        @param payload: The packet data
        @param packet_type: The type of the packet
        @return: The payload with unencrypted content
        """

        if packet_type in self.decrypt_incoming_packet_content:
            payload = self.decrypt_incoming_packet_content[packet_type](candidate, circuit_id, payload)
        if not payload:
            return None
        return payload

    def handle_outgoing_packet(self, destination, circuit_id, message_type, content):
        """
        Outgoing packets have to be encrypted according to the destination, packet type and
        circuit identifier
        @param destination: The originator of the packet
        @param circuit_id: The circuit ID in the packet
        @param message_type: The type of the packet
        @param content: The packet data
        @return: The encrypted content
        """
        try:
            content = self.outgoing_packet_crypto(destination, circuit_id, message_type, content)
            return content
        except:
            self._logger.error("Cannot encrypt outgoing packet content")
            return None

    def handle_outgoing_packet_content(self, destination, circuit_id, message, message_type):
        """
        Content of outgoing packets have to be encrypted according to the destination, 4
        message type and circuit identifier
        @param destination: The originator of the packet
        @param circuit_id: The circuit ID in the packet
        @param message_type: The type of the packet
        @param message: The message
        @return: The message with encrypted content
        """

        try:
            if message_type in self.encrypt_outgoing_packet_content:
                message = self.encrypt_outgoing_packet_content[message_type](destination, circuit_id, message)
            return message
        except:
            self._logger.error("Cannot encrypt outgoing packet content")
            return None

    def handle_relay_packet(self, direction, sock_addr, circuit_id, data):
        """
        Relayed messages have to be encrypted / decrypted depending on direction, sock address and
        circuit identifier
        @param direction: direction of the packet
        @param circuit_id: The circuit ID in the packet
        @param sock_addr: socket address of the originator of the message
        @param data: The message data
        @return: The message data, en- / decrypted according to the circuitdirection
        """
        try:
            data = self.relay_packet_crypto(direction, sock_addr, circuit_id, data)
            return data
        except:
            self._logger.error("Cannot crypt relay packet")
            return None


class NoCrypto(Crypto):
    def __init__(self):
        Crypto.__init__(self)
        self.proxy = None
        self.key_to_forward = None
        self.encrypt_outgoing_packet_content[MESSAGE_CREATED] = self._encrypt_created_content
        self.decrypt_incoming_packet_content[MESSAGE_CREATED] = self._decrypt_created_content
        self.decrypt_incoming_packet_content[MESSAGE_EXTENDED] = self._decrypt_extended_content


    def set_proxy(self, proxy):
        """
        Method which enables the "nocrypto" cryptography settings for the given
        community. NoCrypto encodes and decodes candidate lists, everything is
        passed as a string in the messages

        @param ProxyCommunity proxy: Proxy community to which this crypto
         object is coupled
        """
        self.proxy = proxy

    def disable(self):
        """
        Disables the crypto settings
        """
        self.outgoing_packet_crypto = lambda candidate, circuit, message, payload: payload
        self.incoming_packet_crypto = lambda candidate, circuit, payload: payload
        self.relay_packet_crypto = lambda destination, circuit, message_type, content: content
        self.encrypt_outgoing_packet_content = defaultdict()
        self.decrypt_incoming_packet_content = defaultdict()

    def _encrypt_created_content(self, candidate, circuit_id, message):
        """
        Candidate list must be converted to a string in nocrypto

        @param Candidate candidate: Destination of the message
        @param int circuit_id: Circuit identifier
        @param CreatedMessage message: Message as passed from the community
        @return CreatedMessage: Version of the message with candidate string
        """
        message.candidate_list = encode(message.candidate_list)
        return message

    def _decrypt_created_content(self, candidate, circuit_id, message):
        """
        If created is for us, decode candidate list from string to dict

        @param Candidate candidate: Sender of the message
        @param int circuit_id: Circuit identifier
        @param CreatedMessage message: Message as passed from the community
        @return CreatedMessage: Message with candidates as dict
        """
        if circuit_id in self.proxy.circuits:
            _, message.candidate_list = decode(message.candidate_list)
        return message

    def _decrypt_extended_content(self, candidate, circuit_id, message):
        """
        Convert candidate list from string to dict

        @param Candidate candidate: Sender of the message
        @param int circuit_id: Circuit identifier
        @param ExtendedMessage message: Message as passed from the community
        @return ExtendedMessage: Extended message with candidate list as dict
        """
        _, message.candidate_list = decode(message.candidate_list)
        return message


class DefaultCrypto(Crypto):

    @staticmethod
    def __generate_diffie_secret():
        """
        Generates a new Diffie Hellman g^x. Note the mpz lib used for Windows
        @return: tuple of x and g^x
        """
        dh_secret = 0
        while dh_secret >= DIFFIE_HELLMAN_MODULUS or dh_secret < 2:
              dh_secret = rand("next", DIFFIE_HELLMAN_MODULUS)
        dh_secret = mpz(dh_secret)

        dh_first_part = mpz(pow(DIFFIE_HELLMAN_GENERATOR, dh_secret, DIFFIE_HELLMAN_MODULUS))
        return dh_secret, dh_first_part

    def __init__(self):
        Crypto.__init__(self)
        self.proxy = None
        """ :type proxy: ProxyCommunity """
        self._logger = logging.getLogger(__name__)
        self._received_secrets = {}
        self.session_keys = {}
        self.encrypt_outgoing_packet_content[MESSAGE_CREATE] = self._encrypt_create_content
        self.encrypt_outgoing_packet_content[MESSAGE_CREATED] = self._encrypt_created_content
        self.encrypt_outgoing_packet_content[MESSAGE_EXTEND] = self._encrypt_extend_content
        self.encrypt_outgoing_packet_content[MESSAGE_EXTENDED] = self._encrypt_extended_content
        self.decrypt_incoming_packet_content[MESSAGE_CREATE] = self._decrypt_create_content
        self.decrypt_incoming_packet_content[MESSAGE_CREATED] = self._decrypt_created_content
        self.decrypt_incoming_packet_content[MESSAGE_EXTEND] = self._decrypt_extend_content
        self.decrypt_incoming_packet_content[MESSAGE_EXTENDED] = self._decrypt_extended_content

    def on_break_relay(self, relay_key):
        """
        Method called whenever a relay is broken after for example a timeout
        or an invalid packet. Callback from the community to remove the session
        key
        @param relay_key:
        """
        if relay_key in self.session_keys:
            del self.session_keys[relay_key]

    def set_proxy(self, proxy):
        """
        Method which enables the "defaultcrypto" cryptography settings for
        the given community. Default crypto uses cryptography for all message
        types, based on exchanged secrets established with DIFFIE HELLMAN and
        Elliptic Curve Elgamal. See documentation for extra info.

        @param ProxyCommunity proxy: Proxy community to which this crypto
         object is coupled
        """
        self.proxy = proxy
        proxy.observers.append(self)

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

        if circuit_id in self.proxy.circuits:
            dh_secret, dh_first_part = self.__generate_diffie_secret()

            pub_key = iter(candidate.get_members()).next()._ec

            encrypted_dh_first_part = self.proxy.crypto.encrypt(
                pub_key, long_to_bytes(dh_first_part))
            message.key = encrypted_dh_first_part
            hop = self.proxy.circuits[circuit_id].unverified_hop
            hop.dh_secret = dh_secret
            hop.dh_first_part = dh_first_part
            hop.set_public_key(pub_key)
        else:
            message.key = self.key_to_forward
            self.key_to_forward = None

        return message

    def _decrypt_create_content(self, candidate, circuit_id, message):
        """
        The first part of the DIFFIE HELLMAN handshake is encrypted with
        Elgamal and is decrypted here

        @param Candidate candidate: Sender of the message
        @param int circuit_id: Circuit identifier
        @param CreateMessage message: Message as passed from the community
        @return CreateMessage: Message with decrypted contents
        """
        relay_key = (candidate.sock_addr, circuit_id)
        my_key = self.proxy.my_member._ec
        dh_second_part = mpz(bytes_to_long(self.proxy.crypto.decrypt(my_key, message.key)))

        if dh_second_part < 2 or dh_second_part > DIFFIE_HELLMAN_MODULUS - 1:
            self._logger.warning("Invalid DH data received over circuit {}.".format(circuit_id))
            return None

        self._received_secrets[relay_key] = dh_second_part
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
        dh_secret, dh_first_part = self.__generate_diffie_secret()

        pub_key = self.proxy.circuits[circuit_id].unverified_hop.pub_key

        encrypted_dh_first_part = self.proxy.crypto.encrypt(
            pub_key, long_to_bytes(dh_first_part))
        message.key = encrypted_dh_first_part

        hop = self.proxy.circuits[circuit_id].unverified_hop
        hop.dh_first_part = dh_first_part
        hop.dh_secret = dh_secret

        return message

    def _decrypt_extend_content(self, candidate, circuit_id, message):
        """
        Nothing is encrypted in an Extend message

        @param Candidate candidate: Sender of the message
        @param int circuit_id: Circuit identifier
        @param ExtendMessage message: Message as passed from the community
        @return ExtendMessage: Message with decrypted contents
        """
        self.key_to_forward = message.key
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
        dh_secret, _ = self.__generate_diffie_secret()

        key = pow(self._received_secrets[relay_key],
                  dh_secret, DIFFIE_HELLMAN_MODULUS)

        m = hashlib.sha256()
        m.update(str(key))
        key = m.digest()[0:16]

        self.session_keys[relay_key] = key
        return_key = pow(DIFFIE_HELLMAN_GENERATOR, dh_secret,
                         DIFFIE_HELLMAN_MODULUS)
        message.key = long_to_bytes(return_key)

        encoded_dict = encoding.encode(message.candidate_list)
        message.candidate_list = aes_encrypt_str(self.session_keys[relay_key], encoded_dict)

        return message

    def _decrypt_created_content(self, candidate, circuit_id, message):
        """
        Nothing to decrypt if you're not the originator of the circuit. Else,
        The candidate list should be decrypted as if it was an Extended
        message.

        @param Candidate candidate: Sender of the message
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

        @param Candidate candidate: Sender of the message
        @param int circuit_id: Circuit identifier
        @param ExtendedMessage|CreatedMessage message: Message as passed from
        the community
        @return ExtendedMessage|CreatedMessage: Extended message with
        unencrypted contents
        """
        unverified_hop = self.proxy.circuits[circuit_id].unverified_hop

        dh_second_part = mpz(bytes_to_long(message.key))

        if dh_second_part < 2 or dh_second_part > DIFFIE_HELLMAN_MODULUS - 1:
            self._logger.warning("Invalid DH data received over circuit {}.".format(circuit_id))
            return None

        session_key = pow(dh_second_part,
                          unverified_hop.dh_secret,
                          DIFFIE_HELLMAN_MODULUS)
        m = hashlib.sha256()
        m.update(str(session_key))
        key = m.digest()[0:16]
        unverified_hop.session_key = key
        try:
            encoded_dict = aes_decrypt_str(unverified_hop.session_key, message.candidate_list)
            _, cand_dict = encoding.decode(encoded_dict)
            message.candidate_list = cand_dict
        except:
            reason = "Can't decrypt candidate list!"
            self._logger.error(reason)
            self.proxy.remove_circuit(circuit_id, reason)
            return None

        return message

    def outgoing_packet_crypto(self, candidate, circuit_id,
                                message_type, content):
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

        # CREATE and CREATED have to be Elgamal encrypted
        if message_type == MESSAGE_CREATED or message_type == MESSAGE_CREATE:
            candidate_pub_key = iter(candidate.get_members()).next()._ec
            content = self.proxy.crypto.encrypt(candidate_pub_key, content)
        # Else add AES layer
        elif relay_key in self.session_keys:
            content = aes_encrypt_str(self.session_keys[relay_key], content)
        # If own circuit, AES layers have to be added
        elif circuit_id in self.proxy.circuits:
            # I am the originator so I have to create the full onion
            circuit = self.proxy.circuits[circuit_id]
            hops = circuit.hops
            for hop in reversed(hops):
                content = aes_encrypt_str(hop.session_key, content)
        else:
            raise CryptoError("Don't know how to encrypt outgoing message")

        return content

    def relay_packet_crypto(self, direction, sock_addr, circuit_id, data):
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
            data = aes_encrypt_str(
                self.session_keys[next_relay_key], data)

        # Message is going upstream so I have to remove my onion layer
        elif direction == ENDPOINT:
            data = aes_decrypt_str(
                self.session_keys[relay_key], data)
        else:
            raise ValueError("The parameter 'direction' must be either"
                             "ORIGINATOR or ENDPOINT")

        return data

    def incoming_packet_crypto(self, candidate, circuit_id, data):
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
        # I'm the last node in the circuit, probably an EXTEND message,
        # decrypt with AES
        if relay_key in self.session_keys:

            try:
                # last node in circuit, circuit already exists
                return aes_decrypt_str(self.session_keys[relay_key], data)
            except:
                self._logger.warning("Cannot decrypt a message destined for us, the end of a circuit.")
                return None

        # If I am the circuits originator I want to peel layers
        elif circuit_id in self.proxy.circuits and len(
                self.proxy.circuits[circuit_id].hops) > 0:

            try:
                # I am the originator so I'll peel the onion skins
                for hop in self.proxy.circuits[circuit_id].hops:
                    data = aes_decrypt_str(hop.session_key, data)

                return data
            except:
                self._logger.warning("Cannot decrypt packet. It should be a packet coming of our own circuit, but we cannot peel the onion.")
                return None

        # I don't know the sender! Let's decrypt with my private Elgamal key
        else:
            try:
                # last node in circuit, circuit does not exist yet,
                # decrypt with Elgamal key
                self._logger.debug(
                    "Circuit does not yet exist, decrypting with my Elgamal key")
                my_key = self.proxy.my_member._ec
                data = self.proxy.crypto.decrypt(my_key, data)

                return data
            except:
                self._logger.warning("Cannot decrypt packet, should be an initial packet encrypted with our public Elgamal key");
                return None



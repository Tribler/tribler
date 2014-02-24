import logging
from random import getrandbits


from Crypto.Util.number import long_to_bytes
from Tribler.community.anontunnel.globals import CIRCUIT_STATE_EXTENDING, \
    MESSAGE_EXTEND, DIFFIE_HELLMAN_MODULUS_SIZE, DIFFIE_HELLMAN_MODULUS, \
    DIFFIE_HELLMAN_GENERATOR
from Tribler.community.anontunnel.payload import ExtendMessage
from Tribler.community.anontunnel.routing import Hop

__author__ = 'chris'


class ExtendStrategy:
    def __init__(self):
        self._logger = logging.getLogger(__name__)

    def extend(self, candidate_list=None):
        if not candidate_list:
            candidate_list = {}

        raise NotImplementedError()


class TrustThyNeighbour(ExtendStrategy):
    def __init__(self, proxy, circuit):
        """
        :type proxy: Tribler.community.anontunnel.community.ProxyCommunity
        :param circuit:
        """
        ExtendStrategy.__init__(self)
        self.proxy = proxy
        self.circuit = circuit

    def extend(self, candidate_list=None):
        if not candidate_list:
            candidate_list = {}

        assert self.circuit.state == CIRCUIT_STATE_EXTENDING, \
            "Only circuits with state CIRCUIT_STATE_EXTENDING can be extended"
        assert self.circuit.goal_hops > len(self.circuit.hops), \
            "Circuits with correct length cannot be extended"

        self._logger.info("Trusting our tunnel to extend circuit %d",
                    self.circuit.circuit_id)
        self.proxy.send_message(self.circuit.candidate,
                                self.circuit.circuit_id, MESSAGE_EXTEND,
                                ExtendMessage(None))


class NeighbourSubset(ExtendStrategy):
    def __init__(self, proxy, circuit):
        """
        :type proxy: Tribler.community.anontunnel.community.ProxyCommunity
        :param circuit:
        """
        ExtendStrategy.__init__(self)
        self.proxy = proxy
        self.circuit = circuit

    def extend(self, candidate_list=None):
        if not candidate_list:
            candidate_list = {}

        assert self.circuit.state == CIRCUIT_STATE_EXTENDING, \
            "Only circuits with state CIRCUIT_STATE_EXTENDING can be extended"
        assert self.circuit.goal_hops > len(self.circuit.hops), \
            "Circuits with correct length cannot be extended"

        sock_addr, extend_hop_public_key = next(candidate_list.iteritems(),
                                                (None, None))

        if not sock_addr:
            raise ValueError("No candidates to extend, bailing out ")

        extend_hop_public_key = self.proxy.dispersy.crypto.key_from_public_bin(
            extend_hop_public_key)

        dh_secret = getrandbits(DIFFIE_HELLMAN_MODULUS_SIZE)
        while dh_secret >= DIFFIE_HELLMAN_MODULUS:
            dh_secret = getrandbits(DIFFIE_HELLMAN_MODULUS_SIZE)

        self.circuit.unverified_hop = Hop(
            sock_addr, extend_hop_public_key, dh_secret)

        dh_first_part = pow(DIFFIE_HELLMAN_GENERATOR, dh_secret,
                            DIFFIE_HELLMAN_MODULUS)
        try:
            encrypted_dh_first_part = self.proxy.crypto.encrypt(
                extend_hop_public_key,
                long_to_bytes(dh_first_part, 2048 / 8))
            self._logger.info(
                "We chose %s from the list to extend circuit %d with "
                "encrypted DH first part %s",
                sock_addr, self.circuit.circuit_id, dh_first_part)

            self.proxy.send_message(
                self.circuit.candidate, self.circuit.circuit_id,
                MESSAGE_EXTEND,
                ExtendMessage(sock_addr, encrypted_dh_first_part))
        except BaseException as e:
            self._logger.exception("Encryption error")
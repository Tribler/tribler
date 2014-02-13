import logging
from random import getrandbits
from Tribler.community.anontunnel.conversion import int_to_packed

logger = logging.getLogger(__name__)

from Tribler.community.anontunnel.globals import *
from Tribler.community.anontunnel.payload import *

__author__ = 'chris'

class ExtendStrategy:
    def extend(self, candidate_list=None):
        raise NotImplementedError()

class TrustThyNeighbour(ExtendStrategy):
    def __init__(self, proxy, circuit):
        """
        :type proxy: Tribler.community.anontunnel.community.ProxyCommunity
        :param circuit:
        """
        self.proxy = proxy
        self.circuit = circuit

    def extend(self, candidate_list=None):
        assert self.circuit.state == CIRCUIT_STATE_EXTENDING, "Only circuits with state CIRCUIT_STATE_EXTENDING can be extended"
        assert self.circuit.goal_hops > len(
            self.circuit.hops), "Circuits with correct length cannot be extended"

        logger.info(
            "We are trusting our hop to extend circuit %d" % self.circuit.circuit_id)
        self.proxy.send_message(self.circuit.candidate,
                                self.circuit.circuit_id, MESSAGE_EXTEND,
                                ExtendMessage(None))


class NeighbourSubset(ExtendStrategy):
    def __init__(self, proxy, circuit):
        """
        :type proxy: Tribler.community.anontunnel.community.ProxyCommunity
        :param circuit:
        """
        self.proxy = proxy
        self.circuit = circuit

    def extend(self, candidate_list):
        assert self.circuit.state == CIRCUIT_STATE_EXTENDING, "Only circuits with state CIRCUIT_STATE_EXTENDING can be extended"
        assert self.circuit.goal_hops > len(
            self.circuit.hops), "Circuits with correct length cannot be extended"

        from Tribler.community.anontunnel.community import Hop

        sock_addr, extend_hop_public_key = next(candidate_list.iteritems(),
                                                (None, None))

        if not sock_addr:
            raise ValueError("No candidates to extend, bailing out ")

        extend_hop_public_key = self.proxy.dispersy.crypto.key_from_public_bin(
            extend_hop_public_key)

        dh_secret = getrandbits(DIFFIE_HELLMAN_MODULUS_SIZE)
        while dh_secret >= DIFFIE_HELLMAN_MODULUS:
            dh_secret = getrandbits(DIFFIE_HELLMAN_MODULUS_SIZE)

        self.circuit.unverified_hop = Hop(sock_addr, extend_hop_public_key,
                                          dh_secret)

        dh_first_part = pow(DIFFIE_HELLMAN_GENERATOR, dh_secret,
                            DIFFIE_HELLMAN_MODULUS)
        try:
            encrypted_dh_first_part = self.proxy.dispersy.crypto.encrypt(
                extend_hop_public_key,
                int_to_packed(dh_first_part, 2048))
            logger.info(
                "We chose %s from the list to extend circuit %d with encrypted DH first part %s" % (
                    sock_addr, self.circuit.circuit_id, dh_first_part))
            self.proxy.send_message(self.circuit.candidate,
                                    self.circuit.circuit_id, MESSAGE_EXTEND,
                                    ExtendMessage(sock_addr,
                                                  encrypted_dh_first_part))
        except BaseException as e:
            logger.exception("Encryption error")
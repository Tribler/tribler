import logging
from Tribler.community.anontunnel.globals import CIRCUIT_STATE_EXTENDING, \
    MESSAGE_EXTEND
from Tribler.community.anontunnel.payload import ExtendMessage
from Tribler.community.anontunnel.routing import Hop

__author__ = 'chris'


class NoCandidatesException(ValueError):
    pass


class ExtendStrategy:
    def __init__(self):
        self._logger = logging.getLogger(__name__)

    def extend(self, candidate_list=None):
        if not candidate_list:
            candidate_list = []

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
            candidate_list = []

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
            candidate_list = []

        assert self.circuit.state == CIRCUIT_STATE_EXTENDING, \
            "Only circuits with state CIRCUIT_STATE_EXTENDING can be extended"
        assert self.circuit.goal_hops > len(self.circuit.hops), \
            "Circuits with correct length cannot be extended"

        extend_hop_public_bin = next(iter(candidate_list), None)

        if not extend_hop_public_bin:
            raise NoCandidatesException("No candidates (with key) to extend, bailing out.")

        extend_hop_public_key = self.proxy.dispersy.crypto.key_from_public_bin(extend_hop_public_bin)
        hashed_public_key = self.proxy.dispersy.crypto.key_to_hash(extend_hop_public_key)

        self.circuit.candidate.pub_key = extend_hop_public_key
        self.circuit.unverified_hop = Hop(extend_hop_public_key)

        try:
            self._logger.info(
                "We chose %s from the list to extend circuit %d",
                hashed_public_key, self.circuit.circuit_id)

            self.proxy.send_message(
                self.circuit.candidate, self.circuit.circuit_id,
                MESSAGE_EXTEND,
                ExtendMessage(extend_hop_public_bin))
        except BaseException:
            self._logger.exception("Encryption error")
            return False

        return True
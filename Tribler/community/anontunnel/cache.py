"""
Cache module for the ProxyCommunity.

Keeps track of outstanding PING and EXTEND requests and of candidates used in
CREATE and CREATED requests.

"""

import logging
from Tribler.dispersy.requestcache import NumberCache

__author__ = 'chris'


class CircuitRequestCache(NumberCache):
    PREFIX = u"anon-circuit"

    """
    Circuit request cache is used to keep track of circuit building. It
    succeeds when the circuit reaches full length.

    On timeout the circuit is removed

    @param ProxyCommunity community: the instance of the ProxyCommunity
    @param int force_number:
    """

    def __init__(self, community, circuit):
        number = self.create_identifier(circuit)

        NumberCache.__init__(self, community.request_cache, self.PREFIX, number)
        self._logger = logging.getLogger(__name__)
        self.community = community
        self.circuit = circuit
        ''' :type : Tribler.community.anontunnel.community.Circuit '''

    @property
    def timeout_delay(self):
        return 10.0

    def on_success(self):
        """
        Mark the Request as successful, cancelling the timeout
        """

        from Tribler.community.anontunnel.globals \
            import CIRCUIT_STATE_READY

        if self.circuit.state == CIRCUIT_STATE_READY:
            self._logger.info("Circuit %d is ready", self.number)
            self.community.dispersy.callback.register(
                self.community.request_cache.pop, args=(self.prefix, self.number,))

    def on_timeout(self):
        from Tribler.community.anontunnel.globals \
            import CIRCUIT_STATE_READY

        if not self.circuit.state == CIRCUIT_STATE_READY:
            reason = 'timeout on CircuitRequestCache, state = %s' % \
                     self.circuit.state
            self.community.remove_circuit(self.number, reason)

    @classmethod
    def create_identifier(cls, circuit):
        return circuit.circuit_id


class PingRequestCache(NumberCache):
    PREFIX = u"anon-ping"

    """
    Request cache that is used to time-out PING messages

    @param ProxyCommunity community: instance of the ProxyCommunity
    @param force_number:
    """
    def __init__(self, community, circuit):
        NumberCache.__init__(self, community.request_cache, self.PREFIX, circuit.circuit_id)

        self.circuit = circuit
        self.community = community

    @property
    def timeout_delay(self):
        return 10.0

    def on_pong(self, message):
        self.community.circuits[self.number].beat_heart()
        self.community.dispersy.callback.register(
            self.community.request_cache.pop, args=(self.PREFIX, self.number,))

    def on_timeout(self):
        self.community.remove_circuit(self.number, 'RequestCache')


class CreatedRequestCache(NumberCache):
    PREFIX = u"anon-created"

    def __init__(self, community, circuit_id, candidate, candidates):
        """

        @param int circuit_id: the circuit's id
        @param WalkCandidate candidate: the candidate from which we got the CREATE
        @param dict[str, WalkCandidate] candidates: we sent to the candidate to pick from
        """

        number = self.create_identifier(circuit_id, candidate)
        super(CreatedRequestCache, self).__init__(community.request_cache, self.PREFIX, number)

        self.circuit_id = circuit_id
        self.candidate = candidate
        self.candidates = dict(candidates)

    @property
    def timeout_delay(self):
        return 10.0

    def on_timeout(self):
        pass

    @classmethod
    def create_identifier(cls, circuit_id, candidate):
        return circuit_id
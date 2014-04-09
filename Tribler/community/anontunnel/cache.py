"""
Cache module for the ProxyCommunity.

Keeps track of outstanding PING and EXTEND requests and of candidates used in
CREATE and CREATED requests.

"""

import logging
from operator import itemgetter
import threading
import time
from Tribler.dispersy.requestcache import NumberCache

__author__ = 'chris'


class CircuitRequestCache(NumberCache):
    """
    Circuit request cache is used to keep track of circuit building. It
    succeeds when the circuit reaches full length.

    On timeout the circuit is removed

    @param ProxyCommunity community: the instance of the ProxyCommunity
    @param int force_number:
    """

    def __init__(self, community, force_number):
        NumberCache.__init__(self, community.request_cache, force_number)
        self._logger = logging.getLogger(__name__)
        self.community = community

        self.circuit = None
        ''' :type : Tribler.community.anontunnel.community.Circuit '''

    @staticmethod
    def create_number(force_number=-1):
        return force_number if force_number >= 0 \
            else NumberCache.create_number()

    @staticmethod
    def create_identifier(number, force_number=-1):
        assert isinstance(number, (int, long)), type(number)
        return u"request-cache:circuit-request:%d" % (number,)

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
                self.community.request_cache.pop, args=(self.identifier,))

    def on_timeout(self):
        from Tribler.community.anontunnel.globals \
            import CIRCUIT_STATE_READY

        if not self.circuit.state == CIRCUIT_STATE_READY:
            reason = 'timeout on CircuitRequestCache, state = %s' % \
                     self.circuit.state
            self.community.remove_circuit(self.number, reason)


class PingRequestCache(NumberCache):
    """
    Request cache that is used to time-out PING messages

    @param ProxyCommunity community: instance of the ProxyCommunity
    @param force_number:
    """
    def __init__(self, community, force_number):
        NumberCache.__init__(self, community.request_cache, force_number)
        self.community = community

    @staticmethod
    def create_number(force_number=-1):
        return force_number \
            if force_number >= 0 \
            else NumberCache.create_number()

    @staticmethod
    def create_identifier(number, force_number=-1):
        assert isinstance(number, (int, long)), type(number)
        return u"request-cache:ping-request:%d" % (number,)

    @property
    def timeout_delay(self):
        return 10.0

    @property
    def cleanup_delay(self):
        return 0.0

    def on_pong(self, message):
        self.community.circuits[self.number].beat_heart()
        self.community.dispersy.callback.register(
            self.community.request_cache.pop, args=(self.identifier,))

    def on_timeout(self):
        self.community.remove_circuit(self.number, 'RequestCache')


class CandidateCache(object):
    """
    The candidate cache caches public keys, IPs of known candidates in the
    community

    @param ProxyCommunity community: the proxy community instance
    """
    def __init__(self, community, timeout=60):
        self._lock = threading.RLock()
        self._timeout = timeout
        self._capacity = 1000
        self._community = community

        # Public attributes
        self.hashed_key_to_candidate = {}
        ''' :type : dict[object, WalkCandidate]'''

        self.ip_to_candidate = {}
        ''' :type : dict[(str, int), WalkCandidate] '''

        self.candidate_to_time = {}
        ''' :type : dict[WalkCandidate, float] '''

        def __clean_up_task():
            while True:
                try:
                    self.clean()
                finally:
                    yield 300.0

        community.dispersy.callback.register(__clean_up_task)

    def cache(self, candidate, times_out=True):
        """
        Caches a supplied candidate

        @param bool times_out: whether the cache entry should timeout
        @param WalkCandidate candidate: the candidate we should cache
        """

        with self._lock:
            self.invalidate_by_candidate(candidate)

            self.ip_to_candidate[candidate.sock_addr] = candidate
            self.hashed_key_to_candidate[iter(candidate.get_members()).next().mid] = candidate

            # set the insert time infinitely far in the future to make sure
            # it remains in the cache for candidates that should not timeout
            insert_time = time.time() if times_out else float("inf")
            self.candidate_to_time[candidate] = insert_time

    def invalidate_by_candidate(self, candidate):
        """
        Invalidate a single candidate in the cache
        @param WalkCandidate candidate: the candidate to invalidate
        """
        with self._lock:
            # check if already exists
            if candidate in self.candidate_to_time:
                if candidate.sock_addr in self.ip_to_candidate:
                    del self.ip_to_candidate[candidate.sock_addr]
                del self.candidate_to_time[candidate]
                del self.hashed_key_to_candidate[iter(candidate.get_members()).next().mid]

    @property
    def items(self):
        """
        Returns (candidate, insert_time) from the cache
        @return:
        """
        return self.candidate_to_time.items()

    @property
    def candidates(self):
        """
        Returns (candidate, insert_time) from the cache
        @return:
        """
        return self.candidate_to_time.keys()

    def clean(self):
        """
        Clean up the cache by invalidating old entries
        """
        sample_time = time.time()

        with self._lock:
            timed_out = [candidate
                         for candidate, insert_time
                         in self.candidate_to_time.iteritems()
                         if insert_time + self._timeout < sample_time]

            for candidate in timed_out:
                self.invalidate_by_candidate(candidate)

            invalid = [(ip, candidate)
                       for ip, candidate
                       in self.ip_to_candidate.iteritems() if candidate.sock_addr != ip]

            for ip, candidate in invalid:
                del self.ip_to_candidate[ip]
                self.ip_to_candidate[candidate.sock_addr] = candidate

            invalid = [(mid, candidate)
                       for mid, candidate
                       in self.hashed_key_to_candidate.iteritems()
                       if mid != next(iter(candidate.get_members())).mid]

            for mid, candidate in invalid:
                del self.hashed_key_to_candidate[mid]
                self.hashed_key_to_candidate[iter(candidate.get_members()).next().mid] = candidate

            # Shrink back to capacity if needed
            amount_to_remove = max(0, len(self.candidate_to_time) - self._capacity)
            if amount_to_remove:
                sorted_list = sorted(self.candidate_to_time, key=itemgetter(1))
                to_remove = sorted_list[0:amount_to_remove]

                for candidate in to_remove:
                    self.invalidate_by_candidate(candidate)

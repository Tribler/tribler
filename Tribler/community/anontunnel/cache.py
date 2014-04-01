import hashlib
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
        self.community.dispersy.callback.register(
            self.community.request_cache.pop, args=(self.identifier,))

    def on_timeout(self):
        self.community.remove_circuit(self.number, 'RequestCache')


class CandidateCache:
    """
    The candidate cache caches public keys, IPs of known candidates in the
    community

    @param ProxyCommunity community: the proxy community instance
    """
    def __init__(self, community, timeout=60):
        self.lock = threading.RLock()

        self.timeout = timeout

        self.capacity = 1000

        self.keys_to_candidate = {}
        ''' :type : dict[object, WalkCandidate] '''

        self.candidate_to_key = {}
        ''' :type : dict[WalkCandidate, object]'''

        self.candidate_to_key_string = {}
        ''' :type : dict[WalkCandidate, object]'''

        self.hashed_key_to_candidate = {}
        ''' :type : dict[object, WalkCandidate]'''

        self.candidate_to_hashed_key = {}
        ''' :type : dict[WalkCandidate, object]'''

        self.ip_to_candidate = {}
        ''' :type : dict[(str, int), WalkCandidate] '''

        self.candidate_to_time = {}
        ''' :type : dict[WalkCandidate, float] '''

        self.community = community

        def __clean_up_task():
            while True:
                try:
                    self.invalidate()
                finally:
                    yield 30.0

        community.dispersy.callback.register(__clean_up_task)

    def cache(self, candidate, times_out=True):
        """
        Caches a supplied candidate

        @param bool times_out: whether the cache entry should timeout
        @param WalkCandidate candidate: the candidate we should cache
        """
        key = next(iter(candidate.get_members()))._ec

        with self.lock:
            self.invalidate_by_candidate(candidate)

            self.keys_to_candidate[key] = candidate
            self.candidate_to_key[candidate] = key
            self.ip_to_candidate[candidate.sock_addr] = candidate
            key_string = self.community.crypto.key_to_bin(key)
            self.candidate_to_key_string[candidate] = key_string
            m = hashlib.sha256()
            m.update(str(key_string))
            hashed_key = m.digest()[0:6]
            self.hashed_key_to_candidate[hashed_key] = candidate
            self.candidate_to_hashed_key[candidate] = hashed_key

            # set the insert time infinitely far in the future to make sure
            # it remains in the cache for candidates that should not timeout
            insert_time = time.time() if times_out else float("inf")
            self.candidate_to_time[candidate] = insert_time

    def invalidate_by_candidate(self, candidate):
        """
        Invalidate a single candidate in the cache
        @param WalkCandidate candidate: the candidate to invalidate
        """
        with self.lock:
            if candidate.sock_addr in self.ip_to_candidate:
                # This line is not useless!
                candidate = self.ip_to_candidate[candidate.sock_addr]
                del self.ip_to_candidate[candidate.sock_addr]

            if candidate in self.candidate_to_key:
                key = self.candidate_to_key[candidate]
                del self.candidate_to_key[candidate]
                del self.keys_to_candidate[key]
                del self.candidate_to_time[candidate]
                del self.candidate_to_key_string[candidate]
                hashed_key = self.candidate_to_hashed_key[candidate]
                del self.candidate_to_hashed_key[candidate]
                del self.hashed_key_to_candidate[hashed_key]

    def invalidate_ip(self, ip):
        """
        Invalidate a single candidate in the cache by its IP address
        @param (str, int) ip: the ip of the candidate to invalidate
        """
        with self.lock:
            if ip in self.ip_to_candidate:
                candidate = self.ip_to_candidate[ip]
                return self.invalidate_by_candidate(candidate)

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

    def invalidate(self):
        """
        Clean up the cache by invalidating old entries
        """
        sample_time = time.time()

        with self.lock:
            timed_out = [candidate
                         for candidate, insert_time
                         in self.candidate_to_time.iteritems()
                         if insert_time + self.timeout < sample_time]

            for candidate in timed_out:
                self.invalidate_by_candidate(candidate)

            # Shrink back to capacity if needed
            amount_to_remove = max(0, len(self.candidate_to_time) - self.capacity)
            if amount_to_remove:
                sorted_list = sorted(self.candidate_to_time, key=itemgetter(1))
                to_remove = sorted_list[0:amount_to_remove]

                for candidate in to_remove:
                    self.invalidate_by_candidate(candidate)
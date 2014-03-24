from operator import itemgetter
import time
import threading

__author__ = 'chris'


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
            timed_out = (candidate
                         for candidate, insert_time
                         in self.candidate_to_time.iteritems()
                         if insert_time + self.timeout < sample_time)

            for candidate in timed_out:
                self.invalidate_by_candidate(candidate)

            # Shrink back to capacity if needed
            amount_to_remove = max(0, len(self.candidate_to_time) - self.capacity)
            if amount_to_remove:
                sorted_list = sorted(self.candidate_to_time, key=itemgetter(1))
                to_remove = sorted_list[0:amount_to_remove]

                for candidate in to_remove:
                    self.invalidate_by_candidate(candidate)
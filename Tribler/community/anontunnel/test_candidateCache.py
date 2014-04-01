from unittest import TestCase
from Tribler.community.anontunnel.cache import CandidateCache
from Tribler.community.anontunnel.community import ProxyCommunity
from Tribler.community.privatesemantic.crypto.elgamalcrypto import ElgamalCrypto
from Tribler.dispersy.callback import Callback
from Tribler.dispersy.candidate import WalkCandidate
from mock import MagicMock, Mock
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import StandaloneEndpoint
from Tribler.dispersy.member import Member

__author__ = 'Chris'


class TestCandidateCache(TestCase):
    def setUp(self):
        self.dispersy = Dispersy(Callback(), StandaloneEndpoint(0), u".", u":memory:", ElgamalCrypto())
        self.dispersy.start()

        obj = Mock()
        obj.crypto = ElgamalCrypto()
        obj.callback = Callback()

        self.cache = CandidateCache(obj)
        self.__candidate_counter = 0

    def __create_walk_candidate(self):
        candidate = WalkCandidate(("127.0.0.1", self.__candidate_counter), False, ("127.0.0.1", self.__candidate_counter), ("127.0.0.1", self.__candidate_counter), u'unknown')
        key = self.dispersy.crypto.generate_key(u"high")
        ''' :type : EC '''

        member = []
        def create_member():
            member.append(Member(self.dispersy, self.dispersy.crypto.key_to_bin(key.pub())))

        self.dispersy.callback.call(create_member)

        candidate.associate(member[0])
        self.__candidate_counter += 1
        return candidate

    def test_cache(self):
        candidate = self.__create_walk_candidate()
        cache = self.cache
        cache.cache(candidate)

        self.assertIn(candidate, cache.candidate_to_hashed_key, "Hashed key must be retrievable from candidate cache")
        hashed_key = cache.candidate_to_hashed_key[candidate]

        self.assertIn(hashed_key, cache.hashed_key_to_candidate, "Candidate must be found using hashed key")
        self.assertEqual(cache.hashed_key_to_candidate[hashed_key], candidate, "Candidate must be the same one we stored")
        self.assertIn(candidate, cache.candidate_to_time, "There must be a cache-time entry for the candidate")
        self.assertIn(candidate, cache.candidate_to_key, "Key must be found using candidate")

        self.assertIn(next(iter(candidate.get_members()))._ec, cache.keys_to_candidate, "Candidate must be found using its key")

    def test_invalidate_by_candidate(self):
        candidate = self.__create_walk_candidate()
        cache = self.cache
        cache.cache(candidate)
        cache.invalidate_by_candidate(candidate)

        self.assertNotIn(candidate, cache.candidates)

    def test_invalidate_ip(self):
        candidate = self.__create_walk_candidate()
        cache = self.cache
        cache.cache(candidate)
        cache.invalidate_ip(candidate.sock_addr)

        self.assertNotIn(candidate, cache.candidates)

    def test_items(self):
        candidate = self.__create_walk_candidate()
        cache = self.cache
        cache.cache(candidate)

        self.assertIn((candidate, cache.candidate_to_time[candidate]), cache.items)

    def test_candidates(self):
        candidate = self.__create_walk_candidate()
        cache = self.cache
        cache.cache(candidate)

        self.assertIn(candidate, cache.candidates)

    def test_invalidate(self):
        candidate = self.__create_walk_candidate()
        self.cache.cache(candidate)

        candidate2 = self.__create_walk_candidate()
        self.cache.cache(candidate2)

        self.assertEqual(2, len(self.cache.candidates))

        # valsspelen
        self.cache.candidate_to_time[candidate] = 0

        self.cache.invalidate()

        self.assertIn(candidate2, self.cache.candidates)
        self.assertNotIn(candidate, self.cache.candidates)
from random import choice, random
from time import time

from candidate import Candidate
from conversion import Conversion
from payload import IntroductionRequestPayload, IntroductionResponsePayload, PunctureRequestPayload, PuncturePayload

from Tribler.Core.dispersy.authentication import NoAuthentication
from Tribler.Core.dispersy.community import Community
from Tribler.Core.dispersy.conversion import DefaultConversion
from Tribler.Core.dispersy.destination import AddressDestination
from Tribler.Core.dispersy.distribution import DirectDistribution
from Tribler.Core.dispersy.message import Message, DelayMessageByProof
from Tribler.Core.dispersy.resolution import PublicResolution

if __debug__:
    from Tribler.Core.dispersy.dprint import dprint

class WalktestCommunity(Community):
    def __init__(self, *args, **kargs):
        super(WalktestCommunity, self).__init__(*args, **kargs)

        self._bootstrap_addresses = self._dispersy._bootstrap_addresses
        assert self._bootstrap_addresses, "fails, maybe a DNS issue"
        self._candidates = {}

    def start_walk(self):
        self.create_introduction_requests(self.yield_candidates(1))

    @property
    def dispersy_candidate_request_initial_delay(self):
        # disable
        return 0.0

    @property
    def dispersy_sync_initial_delay(self):
        # disable
        return 0.0

    def initiate_meta_messages(self):
        return [Message(self, u"introduction-request", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), IntroductionRequestPayload(), self.generic_check, self.on_introduction_request, delay=1.0),
                Message(self, u"introduction-response", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), IntroductionResponsePayload(), self.generic_check, self.on_introduction_response, delay=1.0),
                Message(self, u"puncture-request", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), PunctureRequestPayload(), self.generic_check, self.on_puncture_request, delay=1.0),
                Message(self, u"puncture", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), PuncturePayload(), self.generic_check, self.on_puncture, delay=1.0)]

    def initiate_conversions(self):
        return [DefaultConversion(self), Conversion(self)]

    def generic_check(self, messages):
        # allow all
        return messages

    def yield_candidates(self, count, blacklist=[]):
        assert self._bootstrap_addresses, "must have bootstrap peers"

        # remove own address (should do this when our own external address changes)
        if self._dispersy.external_address in self._candidates:
            del self._candidates[self._dispersy.external_address]

        # remove old candidates
        deadline = time() - 60.0
        for candidate in [candidate for candidate in self._candidates.itervalues() if candidate.stamp < deadline]:
            del self._candidates[candidate.address]

        # get all candidates that either participated in a our walk or that stumbled upon us
        walks = [candidate for candidate in self._candidates.itervalues() if candidate.is_walk and candidate.address not in blacklist]
        stumbles = [candidate for candidate in self._candidates.itervalues() if candidate.is_stumble and candidate.address not in blacklist]

        # yield candidates
        for _ in xrange(count):
            r = random()
            assert 0 <= r <= 1

            if r <= 0.49 and walks:
                yield choice(walks).address
                continue

            if r <= 0.98 and stumbles:
                yield choice(stumbles).address
                continue

            yield choice(self._bootstrap_addresses)

    def introduction_response_timeout(self, message):
        if message is None:
            self.start_walk()

    def create_introduction_requests(self, destinations):
        meta = self._meta_messages[u"introduction-request"]
        messages = [meta.impl(distribution=(self.global_time,), destination=(destination,), payload=(destination,)) for destination in destinations]
        self._dispersy.store_update_forward(messages, False, False, True)

        # wait for instroduction-response
        meta = self._meta_messages[u"introduction-response"]
        footprint = meta.generate_footprint()
        timeout = meta.delay + 1.0 # TODO why 1.0 margin
        for _ in xrange(len(messages)):
            self._dispersy.await_message(meta.generate_footprint(), self.introduction_response_timeout, timeout=timeout)

        return messages

    def on_introduction_request(self, messages):
        # get candidates BEFORE updating our local view
        candidates = list(self.yield_candidates(len(messages), [message.address for message in messages]))

        # update local view
        for message in messages:
            if message.address in self._candidates:
                self._candidates[message.address].inc_introduction_requests()
            else:
                self._candidates[message.address] = Candidate(message.address, introduction_requests=1)

            self._dispersy.external_address_vote(message.payload.public_address, message.address)

        # create introduction responses
        meta = self._meta_messages[u"introduction-response"]
        responses = [meta.impl(distribution=(self.global_time,), destination=(message.address,), payload=(message.address, candidate)) for message, candidate in zip(messages, candidates)]
        self._dispersy.store_update_forward(responses, False, False, True)

        # create puncture requests
        meta = self._meta_messages[u"puncture-request"]
        requests = [meta.impl(distribution=(self.global_time,), destination=(candidate,), payload=(message.address,)) for message, candidate in zip(messages, candidates)]
        self._dispersy.store_update_forward(requests, False, False, True)

    def on_introduction_response(self, messages):
        # get candidates BEFORE updating our local view
        candidate_it = self.yield_candidates(len(messages), [message.address for message in messages])

        # update local view
        for message in messages:
            if message.address in self._candidates:
                self._candidates[message.address].inc_introduction_responses()
            else:
                self._candidates[message.address] = Candidate(message.address, introduction_responses=1)

            self._dispersy.external_address_vote(message.payload.public_address, message.address)

        # probabilistically continue with the walk or choose a different path
        self.create_introduction_requests((message.payload.introduction_address if random() < 0.8 else candidate_it.next()) for message in messages)

    def on_puncture_request(self, messages):
        # update local view
        for message in messages:
            if message.address in self._candidates:
                self._candidates[message.address].inc_puncture_requests()
            else:
                self._candidates[message.address] = Candidate(message.address, puncture_requests=1)

        meta = self._meta_messages[u"puncture"]
        messages = [meta.impl(distribution=(self.global_time,), destination=(message.payload.walker_address,)) for message in messages]
        self._dispersy.store_update_forward(messages, False, False, True)

    def on_puncture(self, messages):
        # update local view
        for message in messages:
            if message.address in self._candidates:
                self._candidates[message.address].inc_punctures()
            else:
                self._candidates[message.address] = Candidate(message.address, punctures=1)

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
from Tribler.Core.dispersy.message import Message, DelayMessageByProof, DropMessage
from Tribler.Core.dispersy.resolution import PublicResolution

if __debug__:
    from lencoder import log
    from Tribler.Core.dispersy.dprint import dprint

class WalktestCommunity(Community):
    def __init__(self, *args, **kargs):
        super(WalktestCommunity, self).__init__(*args, **kargs)

        self._bootstrap_addresses = self._dispersy._bootstrap_addresses
        assert self._bootstrap_addresses, "fails, maybe a DNS issue"
        self._candidates = {}
        self._walk = set()

        if __debug__: log("walktest.log", "__init__", public_address=self._dispersy.external_address)

    def start_walk(self):
        if __debug__: log("walktest.log", "start_walk", public_address=self._dispersy.external_address)
        try:
            candidate = self.yield_candidates().next()

        except StopIteration:
            if __debug__: dprint("no candidate to start walk.  retry in N seconds")
            self._dispersy.callback(self.start_walk, delay=10.0)

        else:
            self.create_introduction_request(candidate)

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
                Message(self, u"introduction-response", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), IntroductionResponsePayload(), self.check_introduction_response, self.on_introduction_response, delay=1.0),
                Message(self, u"puncture-request", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), PunctureRequestPayload(), self.generic_check, self.on_puncture_request, delay=1.0),
                Message(self, u"puncture", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), PuncturePayload(), self.generic_check, self.on_puncture, delay=1.0)]

    def initiate_conversions(self):
        return [DefaultConversion(self), Conversion(self)]

    def generic_check(self, messages):
        # allow all
        return messages

    def yield_candidates(self, blacklist=[]):
        # remove own address (should do this when our own external address changes)
        if self._dispersy.external_address in self._candidates:
            del self._candidates[self._dispersy.external_address]
        if self._dispersy.external_address in self._bootstrap_addresses:
            self._bootstrap_addresses.remove(self._dispersy.external_address)

        # remove old candidates
        deadline = time() - 60.0
        for candidate in [candidate for candidate in self._candidates.itervalues() if candidate.stamp < deadline]:
            del self._candidates[candidate.address]

        # get all candidates that either participated in a our walk or that stumbled upon us
        walks = [candidate for candidate in self._candidates.itervalues() if candidate.is_walk and candidate.address not in blacklist]
        stumbles = [candidate for candidate in self._candidates.itervalues() if candidate.is_stumble and candidate.address not in blacklist]

        # yield candidates, if available
        if self._bootstrap_addresses or walks or stumbles:
            while True:
                r = random()
                assert 0 <= r <= 1

                if r <= 0.49 and walks:
                    yield choice(walks).address
                    continue

                if r <= 0.98 and stumbles:
                    yield choice(stumbles).address
                    continue

                if self._bootstrap_addresses:
                    yield choice(self._bootstrap_addresses)
                    continue

    def create_introduction_request(self, destination):
        if __debug__: log("walktest.log", "create_introduction_request", public_address=self._dispersy.external_address, introduction_request=destination)

        # claim unique walk identifier
        while True:
            identifier = int(random() * 2**16)
            if not identifier in self._walk:
                self._walk.add(identifier)
                break

        meta_request = self._meta_messages[u"introduction-request"]
        request = meta_request.impl(distribution=(self.global_time,), destination=(destination,), payload=(destination, identifier))

        # wait for instroduction-response
        meta_response = self._meta_messages[u"introduction-response"]
        footprint = meta_response.generate_footprint(payload=(identifier,))
        timeout = meta_response.delay + 5.0 # TODO why 5.0 margin
        self._dispersy.await_message(footprint, self.introduction_response_or_timeout, timeout=timeout)

        # release walk identifier some seconds after timeout expires
        self._dispersy.callback.register(self._walk.remove, (identifier,), delay=timeout+10.0)

        self._dispersy.store_update_forward([request], False, False, True)
        return request

    def on_introduction_request(self, messages):
        try:
            # get candidate BEFORE updating our local view
            candidate = self.yield_candidates([message.address for message in messages]).next()
        except StopIteration:
            candidate = None

        for message in messages:
            # update local view
            if message.address in self._candidates:
                self._candidates[message.address].inc_introduction_requests()
            else:
                self._candidates[message.address] = Candidate(message.address, introduction_requests=1)

            # obtain own public address
            self._dispersy.external_address_vote(message.payload.public_address, message.address)

            if candidate:
                if __debug__: log("walktest.log", "introduction_response_or_timeout", public_address=self._dispersy.external_address, sources=message.address, introduction_response=message.address, puncture_request=candidate)

                # create introduction responses
                meta = self._meta_messages[u"introduction-response"]
                response = meta.impl(distribution=(self.global_time,), destination=(message.address,), payload=(message.address, candidate, message.payload.identifier))
                self._dispersy.store_update_forward([response], False, False, True)

                # create puncture requests
                meta = self._meta_messages[u"puncture-request"]
                request = meta.impl(distribution=(self.global_time,), destination=(candidate,), payload=(message.address,))
                self._dispersy.store_update_forward([request], False, False, True)

    def check_introduction_response(self, messages):
        for message in messages:
            if message.payload.identifier in self._walk:
                yield message
            else:
                yield DropMessage(message, "unknown response identifier")

    def on_introduction_response(self, messages):
        # handled in introduction_response_or_timeout
        pass

    def introduction_response_or_timeout(self, message):
        if message is None:
            # timeout, start new walk
            self.start_walk()

        else:
            # update local view
            if message.address in self._candidates:
                self._candidates[message.address].inc_introduction_responses()
            else:
                self._candidates[message.address] = Candidate(message.address, introduction_responses=1)

            # obtain own public address
            self._dispersy.external_address_vote(message.payload.public_address, message.address)

            if __debug__: log("walktest.log", "on_introduction_response", public_address=self._dispersy.external_address, sources=[message.address for message in messages])

            # probabilistically continue with the walk or choose a different path
            if random() < 0.8:
                destination = messages.payload.introduction_address
            else:
                try:
                    destination = self.yield_candidates(message.address).next()
                except StopIteration:
                    destination = messages.payload.introduction_address
            self.create_introduction_request(destination)

    def on_puncture_request(self, messages):
        # update local view
        for message in messages:
            if message.address in self._candidates:
                self._candidates[message.address].inc_puncture_requests()
            else:
                self._candidates[message.address] = Candidate(message.address, puncture_requests=1)

        meta = self._meta_messages[u"puncture"]
        punctures = [meta.impl(distribution=(self.global_time,), destination=(message.payload.walker_address,)) for message in messages]
        self._dispersy.store_update_forward(punctures, False, False, True)

        if __debug__: log("walktest.log", "on_puncture_request", public_address=self._dispersy.external_address, sources=[message.address for message in messages], punctures=[message.destination.addresses[0] for message in punctures])

    def on_puncture(self, messages):
        # update local view
        for message in messages:
            if message.address in self._candidates:
                self._candidates[message.address].inc_punctures()
            else:
                self._candidates[message.address] = Candidate(message.address, punctures=1)

        if __debug__: log("walktest.log", "on_puncture_request", public_address=self._dispersy.external_address, sources=[message.address for message in messages])

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
from Tribler.Core.dispersy.message import Message, DropMessage
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

        if __debug__: log("walktest.log", "__init__", candidates=[(x.internal_address, x.external_address) for x in self._candidates.itervalues()])

    def start_walk(self):
        try:
            internal_candidate_address, external_candidate_address = self.yield_candidates().next()

        except StopIteration:
            if __debug__: dprint("no candidate to start walk.  retry in N seconds")
            self._dispersy.callback.register(self.start_walk, delay=10.0)

        else:
            destination = internal_candidate_address if external_candidate_address == self._dispersy.external_address else external_candidate_address
            self.create_introduction_request(destination)

    @property
    def dispersy_candidate_request_initial_delay(self):
        # disable
        return 0.0

    @property
    def dispersy_sync_initial_delay(self):
        # disable
        return 0.0

    def initiate_meta_messages(self):
        return [Message(self, u"introduction-request", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), IntroductionRequestPayload(), self.check_introduction_request, self.on_introduction_request, delay=1.0),
                Message(self, u"introduction-response", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), IntroductionResponsePayload(), self.check_introduction_response, self.on_introduction_response, delay=4.0),
                Message(self, u"puncture-request", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), PunctureRequestPayload(), self.generic_check, self.on_puncture_request, delay=1.0),
                Message(self, u"puncture", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), PuncturePayload(), self.generic_check, self.on_puncture, delay=1.0)]

    def initiate_conversions(self):
        return [DefaultConversion(self), Conversion(self)]

    def generic_check(self, messages):
        # allow all
        return messages

    def yield_candidates(self, blacklist=()):
        # remove own address (should do this when our own external address changes)
        if self._dispersy.external_address in self._candidates:
            del self._candidates[self._dispersy.external_address]
        if self._dispersy.external_address in self._bootstrap_addresses:
            self._bootstrap_addresses.remove(self._dispersy.external_address)

        # remove old candidates
        deadline = time() - 60.0
        for key in [key for key, candidate in self._candidates.iteritems() if candidate.stamp < deadline]:
            del self._candidates[key]

        # get all candidates that either participated in a our walk or that stumbled upon us
        walks = [candidate for candidate in self._candidates.itervalues() if candidate.is_walk and candidate.internal_address not in blacklist and candidate.external_address not in blacklist]
        stumbles = [candidate for candidate in self._candidates.itervalues() if candidate.is_stumble and candidate.internal_address not in blacklist and candidate.external_address not in blacklist]

        # apply blacklist to the bootstrap addresses
        bootstrap_addresses = [address for address in self._bootstrap_addresses if not address in blacklist]
        
        # yield candidates, if available
        if bootstrap_addresses or walks or stumbles:
            while True:
                r = random()
                assert 0 <= r <= 1

                if r <= 0.49 and walks:
                    candidate = choice(walks)
                    yield candidate.internal_address, candidate.external_address

                elif r <= 0.98 and stumbles:
                    candidate = choice(stumbles)
                    yield candidate.internal_address, candidate.external_address

                elif bootstrap_addresses:
                    external_address = choice(bootstrap_addresses)
                    yield external_address, external_address

    def create_introduction_request(self, destination):
        assert isinstance(destination, tuple)
        assert len(destination) == 2
        assert isinstance(destination[0], str)
        assert isinstance(destination[1], int)

        # claim unique walk identifier
        while True:
            identifier = int(random() * 2**16)
            if not identifier in self._walk:
                self._walk.add(identifier)
                break

        advice = random() < 0.8 or len(self._candidates) < 5

        if __debug__:
            log("walktest.log", "create_introduction_request", internal_address=self._dispersy.internal_address, external_address=self._dispersy.external_address, candidates=[(x.internal_address, x.external_address) for x in self._candidates.itervalues()])
            log("walktest.log", "out-introduction-request", destination_address=destination, source_internal_address=self._dispersy.internal_address, source_external_address=self._dispersy.external_address, advice=advice, identifier=identifier)

        meta_request = self._meta_messages[u"introduction-request"]
        request = meta_request.impl(distribution=(self.global_time,), destination=(destination,), payload=(destination, self._dispersy.internal_address, self._dispersy.external_address, advice, identifier))

        # wait for instroduction-response
        meta_response = self._meta_messages[u"introduction-response"]
        footprint = meta_response.generate_footprint(payload=(identifier,))
        timeout = meta_response.delay + 5.0 # TODO why 5.0 margin
        self._dispersy.await_message(footprint, self.introduction_response_or_timeout, response_args=(destination, advice), timeout=timeout)

        # release walk identifier some seconds after timeout expires
        self._dispersy.callback.register(self._walk.remove, (identifier,), delay=timeout+10.0)

        self._dispersy.store_update_forward([request], False, False, True)
        return request

    def check_introduction_request(self, messages):
        if __debug__:
            for message in messages:
                if not (message.address == message.payload.source_internal_address or message.address == message.payload.source_external_address):
                    dprint(message.address, message.payload.source_internal_address, message.payload.source_external_address, glue="  ", force=1)
        return messages
                
    def on_introduction_request(self, messages):
        for message in messages:
            # get introduction candidate (if requested)
            if message.payload.advice:
                try:
                    internal_candidate_address, external_candidate_address = self.yield_candidates([message.address]).next()
                except StopIteration:
                    internal_candidate_address, external_candidate_address = None, None
            else:
                internal_candidate_address, external_candidate_address = None, None

            # update local view
            if message.address in self._candidates:
                self._candidates[message.address].inc_introduction_requests(message.payload.source_internal_address, message.payload.source_external_address)
            else:
                self._candidates[message.address] = Candidate(message.payload.source_internal_address, message.payload.source_external_address, introduction_requests=1)

            # obtain own public address
            self._dispersy.external_address_vote(message.payload.destination_address, message.address)
            
            if __debug__:
                log("walktest.log", "on_introduction_request", internal_address=self._dispersy.internal_address, external_address=self._dispersy.external_address, candidates=[(x.internal_address, x.external_address) for x in self._candidates.itervalues()])
                log("walktest.log", "in-introduction-request", source=message.address, destination_address=message.payload.destination_address, source_internal_address=message.payload.source_internal_address, source_external_address=message.payload.source_external_address, advice=message.payload.advice, identifier=message.payload.identifier)
                        
            if external_candidate_address:
                # create introduction responses
                meta = self._meta_messages[u"introduction-response"]
                response = meta.impl(distribution=(self.global_time,), destination=(message.address,), payload=(message.address, internal_candidate_address, external_candidate_address, message.payload.identifier))
                self._dispersy.store_update_forward([response], False, False, True)

                # create puncture requests
                destination = internal_candidate_address if external_candidate_address == self._dispersy.external_address else external_candidate_address
                meta = self._meta_messages[u"puncture-request"]
                request = meta.impl(distribution=(self.global_time,), destination=(destination,), payload=(message.payload.source_internal_address, message.payload.source_external_address))
                self._dispersy.store_update_forward([request], False, False, True)

                if __debug__:
                    log("walktest.log", "out-introduction-response", destination_address=message.address, internal_introduction_address=internal_candidate_address, external_introduction_address=external_candidate_address, identifier=message.payload.identifier)
                    log("walktest.log", "out-puncture-request", destination=destination, internal_walker_address=message.payload.source_internal_address, external_walker_address=message.payload.source_external_address)
                
            else:
                none = ("0.0.0.0", 0)
                meta = self._meta_messages[u"introduction-response"]
                response = meta.impl(distribution=(self.global_time,), destination=(message.address,), payload=(message.address, none, none, message.payload.identifier))
                self._dispersy.store_update_forward([response], False, False, True)

                if __debug__:
                    log("walktest.log", "out-introduction-response", destination_address=message.address, internal_introduction_address=none, external_introduction_address=none, identifier=message.payload.identifier)

    def check_introduction_response(self, messages):
        for message in messages:
            if __debug__: log("walktest.log", "check_introduction_response", internal_address=self._dispersy.internal_address, external_address=self._dispersy.external_address, candidates=[(x.internal_address, x.external_address) for x in self._candidates.itervalues()])

            if message.payload.external_introduction_address == message.address:
                yield DropMessage(message, "invalid external introduction address [introducing herself]")

            elif message.payload.internal_introduction_address == message.address:
                yield DropMessage(message, "invalid internal introduction address [introducing herself]")

            elif message.payload.external_introduction_address in (self._dispersy.internal_address, self._dispersy.external_address):
                yield DropMessage(message, "invalid external introduction address [introducing myself]")

            elif message.payload.internal_introduction_address in (self._dispersy.internal_address, self._dispersy.external_address):
                yield DropMessage(message, "invalid external introduction address [introducing myself]")
                
            elif not message.payload.identifier in self._walk:
                yield DropMessage(message, "invalid response identifier")

            else:
                yield message

    def on_introduction_response(self, messages):
        # handled in introduction_response_or_timeout
        for _ in messages:
            if __debug__: log("walktest.log", "on_introduction_response", internal_address=self._dispersy.internal_address, external_address=self._dispersy.external_address, candidates=[(x.internal_address, x.external_address) for x in self._candidates.itervalues()])

    def introduction_response_or_timeout(self, message, intermediary_address, advice):
        if message is None:
            # intermediary_address is no longer online
            if intermediary_address in self._candidates:
                del self._candidates[intermediary_address]

            if __debug__: log("walktest.log", "introduction-response-timeout", intermediary=intermediary_address, advice=advice)

            # timeout, start new walk
            self.start_walk()

        else:
            # # update local view
            # if message.address in self._candidates:
            #     self._candidates[message.address].inc_introduction_responses()
            # else:
            #     self._candidates[message.address] = Candidate(message.address, message.address, introduction_responses=1)

            # obtain own public address
            self._dispersy.external_address_vote(message.payload.destination_address, message.address)

            if __debug__: log("walktest.log", "in-introduction-response", source=message.address, destination_address=message.payload.destination_address, internal_introduction_address=message.payload.internal_introduction_address, external_introduction_address=message.payload.external_introduction_address, identifier=message.payload.identifier)

            if advice and self._dispersy._is_valid_internal_address(message.payload.internal_introduction_address) and self._dispersy.is_valid_remote_address(message.payload.external_introduction_address):
                # we asked for, and received, an introduction

                # determine if we are in the same LAN as the introduced node
                destination = message.payload.internal_introduction_address if message.payload.external_introduction_address[0] == self._dispersy.external_address[0] else message.payload.external_introduction_address
                self.create_introduction_request(destination)
            else:
                self.start_walk()

    def on_puncture_request(self, messages):
        for message in messages:
            # # update local view
            # if message.address in self._candidates:
            #     self._candidates[message.address].inc_puncture_requests()
            # else:
            #     self._candidates[message.address] = Candidate(message.address, message.address, puncture_requests=1)

            # determine if we are in the same LAN as the walker node
            destination = message.payload.internal_walker_address if message.payload.external_walker_address[0] == self._dispersy.external_address[0] else message.payload.external_walker_address
                
            meta = self._meta_messages[u"puncture"]
            puncture = meta.impl(distribution=(self.global_time,), destination=(destination,))
            self._dispersy.store_update_forward([puncture], False, False, True)

            if __debug__:
                log("walktest.log", "on_puncture_request", internal_address=self._dispersy.internal_address, external_address=self._dispersy.external_address, candidates=[(x.internal_address, x.external_address) for x in self._candidates.itervalues()])
                log("walktest.log", "in-puncture-request", source=message.address, internal_walker_address=message.payload.internal_walker_address, external_walker_address=message.payload.external_walker_address)
                log("walktest.log", "out-puncture", destination=destination)

    def on_puncture(self, messages):
        # update local view
        for message in messages:
            # if message.address in self._candidates:
            #     self._candidates[message.address].inc_punctures()
            # else:
            #     self._candidates[message.address] = Candidate(message.address, message.address, punctures=1)

            if __debug__:
                log("walktest.log", "on_puncture", internal_address=self._dispersy.internal_address, external_address=self._dispersy.external_address, candidates=[(x.internal_address, x.external_address) for x in self._candidates.itervalues()])
                log("walktest.log", "in-puncture", source=message.address)

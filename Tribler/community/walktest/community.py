
DAS2SCENARIO = False
DAS4SCENARIO = True

from time import time

from lencoder import close, bz2log

from Tribler.dispersy.authentication import NoAuthentication
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CandidateDestination
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.message import Message
from Tribler.dispersy.resolution import PublicResolution

from Tribler.dispersy.candidate import CANDIDATE_WALK_LIFETIME, CANDIDATE_STUMBLE_LIFETIME, CANDIDATE_INTRO_LIFETIME

from payload import ContactPayload
from conversion import WalktestConversion

if __debug__:
    from Tribler.dispersy.dprint import dprint

class WalktestCommunity(Community):
    def __init__(self, *args, **kargs):
        super(WalktestCommunity, self).__init__(*args, **kargs)
        if __debug__:
            dprint("cid: ", self.cid.encode("HEX"), force=1)
            dprint("mid: ", self.my_member.mid.encode("HEX"), force=1)

        try:
            hostname = open("/etc/hostname", "r").readline().strip()
        except:
            hostname = "unknown"

        bz2log("walktest.log",
               "load",
               mid=self.my_member.mid,
               hostname=hostname,
               **self._default_log())

        # redirect introduction-response timeout
        self._origional__introduction_response_timeout = self._dispersy.introduction_response_timeout
        self._dispersy.introduction_response_timeout = self._replacement__introduction_response_timeout

    def unload_community(self):
        bz2log("walktest.log",
               "unload",
               **self._default_log())
        return super(WalktestCommunity, self).unload_community()

    def _default_log(self):
        return dict(lan_address=self._dispersy.lan_address,
                    wan_address=self._dispersy.wan_address,
                    connection_type=self._dispersy.connection_type)

    def _replacement__introduction_response_timeout(self, identifier):
        has_response, into_resp_candidate, punct_candidate, community, helper_candidate, req_timestamp = self._dispersy._walk_identifiers.get(identifier)
        if not has_response and self == community:
            bz2log("walktest.log",
                   "timeout",
                   identifier=identifier,
                   intermediary_sock_address=helper_candidate.sock_addr,
                   intermediary_lan_address=helper_candidate.lan_address,
                   intermediary_wan_address=helper_candidate.wan_address,
                   **self._default_log())
        return self._origional__introduction_response_timeout(identifier)

    def _initialize_meta_messages(self):
        super(WalktestCommunity, self)._initialize_meta_messages()

        def advice(name, new_impl, new_handle):
            meta = self._meta_messages[name]
            meta.__origional_impl = meta.impl
            meta.__origional_handle = meta._handle_callback
            meta.impl = lambda *args, **kargs: new_impl(meta, *args, **kargs)
            meta._handle_callback = lambda *args, **kargs: new_handle(meta, *args, **kargs)

        # ENABLED ON DAS2
        if DAS2SCENARIO:
            advice(u"dispersy-introduction-request", self.impl_introduction_request, self.on_introduction_request)
            advice(u"dispersy-introduction-response", self.impl_introduction_response, self.on_introduction_response)
            advice(u"dispersy-puncture-request", self.impl_puncture_request, self.on_puncture_request)
            advice(u"dispersy-puncture", self.impl_puncture, self.on_puncture)

    def dispersy_claim_sync_bloom_filter(self, identifier):
        # disable sync bloom filter
        return None

    def initiate_conversions(self):
        return [DefaultConversion(self), WalktestConversion(self)]

    @property
    def dispersy_auto_download_master_member(self):
        return False

    if DAS4SCENARIO:
        def initiate_meta_messages(self):
            return []

        @staticmethod
        def _get_merged_candidate_category(candidate, community, now):
            timestamps = candidate._timestamps[community.cid]

            if now < timestamps.last_walk + CANDIDATE_WALK_LIFETIME:
                yield u"walk"

            if now < timestamps.last_stumble + CANDIDATE_STUMBLE_LIFETIME and now >= timestamps.last_intro + CANDIDATE_INTRO_LIFETIME:
                yield u"stumble"

            if now < timestamps.last_intro + CANDIDATE_INTRO_LIFETIME and now >= timestamps.last_stumble + CANDIDATE_STUMBLE_LIFETIME:
                yield u"intro"

            if now < timestamps.last_stumble + CANDIDATE_STUMBLE_LIFETIME and now < timestamps.last_intro + CANDIDATE_INTRO_LIFETIME:
                yield u"sandi"

            yield u"none"

        def dispersy_take_step(self):
            now = time()
            addresses = [(candidate.lan_address, candidate.get_category(self, now), "-".join(self._get_merged_candidate_category(candidate, self, now))) for candidate in self._dispersy._candidates.itervalues() if candidate.in_community(self, now)]
            bz2log("walktest.log",
                   "candidates",
                   candidates=addresses,
                   **self._default_log())
            return super(WalktestCommunity, self).dispersy_take_step()

    if DAS2SCENARIO:
        def initiate_meta_messages(self):
            return [Message(self, u"contact", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), ContactPayload(), self.check_contact, self.on_contact)]

        def create_contact(self, destination, identifier):
            meta = self._meta_messages[u"contact"]
            message = meta.impl(distribution=(self.global_time,), destination=(destination,), payload=(identifier,))
            self._dispersy.store_update_forward([message], False, False, True)

            bz2log("walktest.log",
                   "out-contact",
                   destination_address=destination.sock_addr,
                   identifier=identifier,
                   **self._default_log())

        def check_contact(self, messages):
            return messages

        def on_contact(self, messages):
            for message in messages:
                bz2log("walktest.log",
                       "in-contact",
                       source_address=message.candidate.sock_addr,
                       identifier=message.payload.identifier,
                       **self._default_log())

        def impl_introduction_request(self, meta, *args, **kargs):
            message = meta.__origional_impl(*args, **kargs)
            bz2log("walktest.log",
                   "out-introduction-request",
                   destination_address=message.destination.candidates[0].sock_addr,
                   destination_lan_address=message.destination.candidates[0].lan_address,
                   destination_wan_address=message.destination.candidates[0].wan_address,
                   advice=message.payload.advice,
                   identifier=message.payload.identifier,
                   **self._default_log())
            return message

        def on_introduction_request(self, meta, messages):
            for message in messages:
                bz2log("walktest.log",
                       "in-introduction-request",
                       source_address=message.candidate.sock_addr,
                       mid=message.authentication.member.mid,
                       destination_address=message.payload.destination_address,
                       source_lan_address=message.payload.source_lan_address,
                       source_wan_address=message.payload.source_wan_address,
                       advice=message.payload.advice,
                       identifier=message.payload.identifier,
                       **self._default_log())
            return meta.__origional_handle(messages)

        def impl_introduction_response(self, meta, *args, **kargs):
            message = meta.__origional_impl(*args, **kargs)
            assert len(message.destination.candidates) == 1
            bz2log("walktest.log",
                   "out-introduction-response",
                   destination_address=message.destination.candidates[0].sock_addr,
                   lan_introduction_address=message.payload.lan_introduction_address,
                   wan_introduction_address=message.payload.wan_introduction_address,
                   identifier=message.payload.identifier,
                   **self._default_log())
            return message

        def on_introduction_response(self, meta, messages):
            for message in messages:
                bz2log("walktest.log",
                       "in-introduction-response",
                       member=message.authentication.member.public_key,
                       source_address=message.candidate.sock_addr,
                       destination_address=message.payload.destination_address,
                       source_lan_address=message.payload.source_lan_address,
                       source_wan_address=message.payload.source_wan_address,
                       lan_introduction_address=message.payload.lan_introduction_address,
                       wan_introduction_address=message.payload.wan_introduction_address,
                       identifier=message.payload.identifier,
                       **self._default_log())

                # schedule the 'contact' message after one second.  this should give time for the
                # puncture to complete
                # self._dispersy.callback.register(self.create_contact, (message.candidate, message.payload.identifier), delay=1.0)

            return meta.__origional_handle(messages)

        def impl_puncture_request(self, meta, *args, **kargs):
            message = meta.__origional_impl(*args, **kargs)
            assert len(message.destination.candidates) == 1
            bz2log("walktest.log",
                   "out-puncture-request",
                   destination=message.destination.candidates[0].sock_addr,
                   lan_walker_address=message.payload.lan_walker_address,
                   wan_walker_address=message.payload.wan_walker_address,
                   identifier=message.payload.identifier,
                   **self._default_log())
            return message

        def on_puncture_request(self, meta, messages):
            for message in messages:
                bz2log("walktest.log",
                       "in-puncture-request",
                       source_address=message.candidate.sock_addr,
                       lan_walker_address=message.payload.lan_walker_address,
                       wan_walker_address=message.payload.wan_walker_address,
                       identifier=message.payload.identifier,
                       **self._default_log())
            return meta.__origional_handle(messages)

        def impl_puncture(self, meta, *args, **kargs):
            message = meta.__origional_impl(*args, **kargs)
            assert len(message.destination.candidates) == 1
            bz2log("walktest.log",
                   "out-puncture",
                   destination_address=message.destination.candidates[0].sock_addr,
                   source_lan_address=message.payload.source_lan_address,
                   source_wan_address=message.payload.source_wan_address,
                   identifier=message.payload.identifier,
                   **self._default_log())
            return message

        def on_puncture(self, meta, messages):
            for message in messages:
                bz2log("walktest.log",
                       "in-puncture",
                       member=message.authentication.member.mid,
                       source_address=message.candidate.sock_addr,
                       source_lan_address=message.payload.source_lan_address,
                       source_wan_address=message.payload.source_wan_address,
                       identifier=message.payload.identifier,
                       **self._default_log())
            return meta.__origional_handle(messages)

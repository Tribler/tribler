from lencoder import log

from Tribler.Core.dispersy.authentication import NoAuthentication
from Tribler.Core.dispersy.community import Community
from Tribler.Core.dispersy.conversion import DefaultConversion
from Tribler.Core.dispersy.destination import CandidateDestination
from Tribler.Core.dispersy.distribution import DirectDistribution
from Tribler.Core.dispersy.message import Message
from Tribler.Core.dispersy.resolution import PublicResolution

from payload import ContactPayload

if __debug__:
    from Tribler.Core.dispersy.dprint import dprint

class WalktestCommunity(Community):
    def __init__(self, *args, **kargs):
        super(WalktestCommunity, self).__init__(*args, **kargs)

        try:
            hostname = open("/etc/hostname", "r").readline().strip()
        except:
            hostname = "unknown"

        log("walktest.log",
            "init",
            mid=self.my_member.mid,
            hostname=hostname,
            **self._default_log())

        # redirect introduction-response timeout
        self._origional__introduction_response_or_timeout = self._dispersy.introduction_response_or_timeout
        self._dispersy.introduction_response_or_timeout = self._replacement__introduction_response_or_timeout

    def _replacement__introduction_response_or_timeout(self, message, community, intermediary_candidate):
        if message is None and self == community:
            log("walktest.log",
                "timeout",
                intermediary_lan_address=intermediary_candidate.lan_address,
                intermediary_wan_address=intermediary_candidate.wan_address,
                **self._default_log())
        return self._origional__introduction_response_or_timeout(message, community, intermediary_candidate)

    def _initialize_meta_messages(self):
        super(WalktestCommunity, self)._initialize_meta_messages()

        def advice(name, new_impl, new_handle):
            meta = self._meta_messages[name]
            meta.__origional_impl = meta.impl
            meta.__origional_handle = meta._handle_callback
            meta.impl = lambda *args, **kargs: new_impl(meta, *args, **kargs)
            meta._handle_callback = lambda *args, **kargs: new_handle(meta, *args, **kargs)

        advice(u"dispersy-introduction-request", self.impl_introduction_request, self.on_introduction_request)
        advice(u"dispersy-introduction-response", self.impl_introduction_response, self.on_introduction_response)
        advice(u"dispersy-puncture-request", self.impl_puncture_request, self.on_puncture_request)
        advice(u"dispersy-puncture", self.impl_puncture, self.on_puncture)

    def dispersy_claim_sync_bloom_filter(self, identifier):
        # disable sync bloom filter
        return None

    def initiate_meta_messages(self):
        return [Message(self, u"contact", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), ContactPayload(), self.check_contact, self.on_contact)]

    def initiate_conversions(self):
        return [DefaultConversion(self)]

    def create_contact(self, destination, identifier):
        meta = self._meta_messages[u"contact"]
        message = meta.impl(destination=(destination,), payload=(identifier,))
        self._dispersy.store_update_forward([message], False, False, True)

        log("walktest.log",
            "out-contact",
            destination_address=destination.address,
            identifier=identifier,
            **self._default_log())

    def check_contact(self, messages):
        return messages

    def on_contact(self, messages):
        for message in messages:
            log("walktest.log",
                "in-contact",
                source_address=message.candidate.address,
                identifier=message.payload.identifier,
                **self._default_log())

    def _default_log(self):
        return dict(lan_address=self._dispersy.lan_address,
                    wan_address=self._dispersy.wan_address,
                    connection_type=self._dispersy.connection_type)

    def dispersy_start_walk(self):
        log("walktest.log",
            "start-walk",
            candidates=[(candidate.lan_address, candidate.wan_address, candidate.connection_type) for candidate in self._dispersy.yield_all_candidates(self)],
            **self._default_log())
        return self._dispersy.start_walk(self)

    def impl_introduction_request(self, meta, *args, **kargs):
        message = meta.__origional_impl(*args, **kargs)
        if __debug__: dprint("create ", message.destination.candidates[0].address[0], ":", message.destination.candidates[0].address[1])
        log("walktest.log",
            "out-introduction-request",
            destination_address=message.destination.candidates[0].address,
            advice=message.payload.advice,
            identifier=message.payload.identifier,
            **self._default_log())
        return message

    def on_introduction_request(self, meta, messages):
        for message in messages:
            if __debug__: dprint("from ", message.candidate.address[0], ":", message.candidate.address[1], "  LAN ", message.payload.source_lan_address[0], ":", message.payload.source_lan_address[1], "  WAN ", message.payload.source_wan_address[0], ":", message.payload.source_wan_address[1])
            log("walktest.log",
                "in-introduction-request",
                source_address=message.candidate.address,
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
        if __debug__: dprint("create ", message.destination.candidates[0].address[0], ":", message.destination.candidates[0].address[1])
        log("walktest.log",
            "out-introduction-response",
            destination_address=message.destination.candidates[0].address,
            lan_introduction_address=message.payload.lan_introduction_address,
            wan_introduction_address=message.payload.wan_introduction_address,
            identifier=message.payload.identifier,
            **self._default_log())
        return message

    def on_introduction_response(self, meta, messages):
        for message in messages:
            if __debug__: dprint("from ", message.candidate.address[0], ":", message.candidate.address[1], " -> ", message.payload.lan_introduction_address[0], ":", message.payload.lan_introduction_address[1], " or ", message.payload.wan_introduction_address[0], ":", message.payload.wan_introduction_address[1])
            log("walktest.log",
                "in-introduction-response",
                member=message.authentication.member.public_key,
                source_address=message.candidate.address,
                destination_address=message.payload.destination_address,
                source_lan_address=message.payload.source_lan_address,
                source_wan_address=message.payload.source_wan_address,
                lan_introduction_address=message.payload.lan_introduction_address,
                wan_introduction_address=message.payload.wan_introduction_address,
                identifier=message.payload.identifier,
                **self._default_log())

            # schedule the 'contact' message after one second.  this should give time for the
            # puncture to complete
            self._dispersy.callback.register(self.create_contact, (message.candidate, message.payload.identifier), delay=1.0)

        return meta.__origional_handle(messages)

    def impl_puncture_request(self, meta, *args, **kargs):
        message = meta.__origional_impl(*args, **kargs)
        assert len(message.destination.candidates) == 1
        if __debug__: dprint("create ", message.destination.candidates[0].address[0], ":", message.destination.candidates[0].address[1])
        log("walktest.log",
            "out-puncture-request",
            destination=message.destination.candidates[0].address,
            lan_walker_address=message.payload.lan_walker_address,
            wan_walker_address=message.payload.wan_walker_address,
            identifier=message.payload.identifier,
            **self._default_log())
        return message

    def on_puncture_request(self, meta, messages):
        for message in messages:
            if __debug__: dprint("from ", message.candidate.address[0], ":", message.candidate.address[1])
            log("walktest.log",
                "in-puncture-request",
                source_address=message.candidate.address,
                lan_walker_address=message.payload.lan_walker_address,
                wan_walker_address=message.payload.wan_walker_address,
                identifier=message.payload.identifier,
                **self._default_log())
        return meta.__origional_handle(messages)

    def impl_puncture(self, meta, *args, **kargs):
        message = meta.__origional_impl(*args, **kargs)
        assert len(message.destination.candidates) == 1
        if __debug__: dprint("create ", message.destination.candidates[0].address[0], ":", message.destination.candidates[0].address[1])
        log("walktest.log",
            "out-puncture",
            destination_address=message.destination.candidates[0].address,
            source_lan_address=message.payload.source_lan_address,
            source_wan_address=message.payload.source_wan_address,
            identifier=message.payload.identifier,
            **self._default_log())
        return message

    def on_puncture(self, meta, messages):
        for message in messages:
            if __debug__: dprint("from ", message.candidate.address[0], ":", message.candidate.address[1])
            log("walktest.log",
                "in-puncture",
                member=message.authentication.member.mid,
                source_address=message.candidate.address,
                source_lan_address=message.payload.source_lan_address,
                source_wan_address=message.payload.source_wan_address,
                identifier=message.payload.identifier,
                **self._default_log())
        return meta.__origional_handle(messages)


DAS2SCENARIO = True
DAS4SCENARIO = False

from time import time

if DAS2SCENARIO:
    from lencoder import log
else:
    from lencoder import close, bz2log as log

from Tribler.Core.dispersy.authentication import NoAuthentication
from Tribler.Core.dispersy.community import Community
from Tribler.Core.dispersy.conversion import DefaultConversion
from Tribler.Core.dispersy.destination import CandidateDestination
from Tribler.Core.dispersy.distribution import DirectDistribution
from Tribler.Core.dispersy.message import Message
from Tribler.Core.dispersy.resolution import PublicResolution

from payload import ContactPayload
from conversion import WalktestConversion

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
            log("walktest.log", "timeout", lan_address=self._dispersy.lan_address, intermediary_lan_address=intermediary_candidate.lan_address)
        return self._origional__introduction_response_or_timeout(message, community, intermediary_candidate)

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


        # ENABLED ON DAS4
        if DAS4SCENARIO:
            self._dispersy.callback.register(self._watchdog)

    def dispersy_claim_sync_bloom_filter(self, identifier):
        # disable sync bloom filter
        return None

    def initiate_conversions(self):
        return [DefaultConversion(self), WalktestConversion(self)]

    if DAS4SCENARIO:
        def initiate_meta_messages(self):
            return []

        def _watchdog(self):
            try:
                while True:
                    yield 3600.0
            except GeneratorExit:
                print "GeneratorExit"
                log("walktest.log", "stopiteration")
                close("walktest.log")

        def dispersy_take_step(self):
            now = time()
            addresses = [(candidate.lan_address, candidate.get_category(self, now)) for candidate in self._dispersy._candidates.itervalues() if candidate.in_community(self, now)]
            log("walktest.log", "candidates", lan_address=self._dispersy.lan_address, candidates=addresses)
            return super(WalktestCommunity, self).dispersy_take_step()

    if DAS2SCENARIO:
        def initiate_meta_messages(self):
            return [Message(self, u"contact", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), ContactPayload(), self.check_contact, self.on_contact)]

        def create_contact(self, destination, identifier):
            meta = self._meta_messages[u"contact"]
            message = meta.impl(distribution=(self.global_time,), destination=(destination,), payload=(identifier,))
            self._dispersy.store_update_forward([message], False, False, True)

            log("walktest.log",
                "out-contact",
                destination_address=destination.sock_addr,
                identifier=identifier,
                **self._default_log())

        def check_contact(self, messages):
            return messages

        def on_contact(self, messages):
            for message in messages:
                log("walktest.log",
                    "in-contact",
                    source_address=message.candidate.sock_addr,
                    identifier=message.payload.identifier,
                    **self._default_log())

        def _default_log(self):
            return dict(lan_address=self._dispersy.lan_address,
                        wan_address=self._dispersy.wan_address,
                        connection_type=self._dispersy.connection_type)

        def impl_introduction_request(self, meta, *args, **kargs):
            message = meta.__origional_impl(*args, **kargs)
            log("walktest.log",
                "out-introduction-request",
                destination_address=message.destination.candidates[0].sock_addr,
                advice=message.payload.advice,
                identifier=message.payload.identifier,
                **self._default_log())
            return message

        def on_introduction_request(self, meta, messages):
            for message in messages:
                log("walktest.log",
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
            log("walktest.log",
                "out-introduction-response",
                destination_address=message.destination.candidates[0].sock_addr,
                lan_introduction_address=message.payload.lan_introduction_address,
                wan_introduction_address=message.payload.wan_introduction_address,
                identifier=message.payload.identifier,
                **self._default_log())
            return message

        def on_introduction_response(self, meta, messages):
            for message in messages:
                log("walktest.log",
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
            log("walktest.log",
                "out-puncture-request",
                destination=message.destination.candidates[0].sock_addr,
                lan_walker_address=message.payload.lan_walker_address,
                wan_walker_address=message.payload.wan_walker_address,
                identifier=message.payload.identifier,
                **self._default_log())
            return message

        def on_puncture_request(self, meta, messages):
            for message in messages:
                log("walktest.log",
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
            log("walktest.log",
                "out-puncture",
                destination_address=message.destination.candidates[0].sock_addr,
                source_lan_address=message.payload.source_lan_address,
                source_wan_address=message.payload.source_wan_address,
                identifier=message.payload.identifier,
                **self._default_log())
            return message

        def on_puncture(self, meta, messages):
            for message in messages:
                log("walktest.log",
                    "in-puncture",
                    member=message.authentication.member.mid,
                    source_address=message.candidate.sock_addr,
                    source_lan_address=message.payload.source_lan_address,
                    source_wan_address=message.payload.source_wan_address,
                    identifier=message.payload.identifier,
                    **self._default_log())
            return meta.__origional_handle(messages)

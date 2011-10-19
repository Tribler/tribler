from lencoder import log

from Tribler.Core.dispersy.community import Community
from Tribler.Core.dispersy.conversion import DefaultConversion

if __debug__:
    from Tribler.Core.dispersy.dprint import dprint

class WalktestCommunity(Community):
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
    
    def initiate_meta_messages(self):
        return []

    def initiate_conversions(self):
        return [DefaultConversion(self)]

    def dispersy_start_walk(self):
        log("walktest.log", "candidates", lan_address=self._dispersy.lan_address, wan_address=self._dispersy.wan_address, candidates=[(candidate.lan_address, candidate.wan_address) for candidate in self._dispersy.yield_all_candidates(self)])
        return self._dispersy.start_walk(self)

    def impl_introduction_request(self, meta, *args, **kargs):
        message = meta.__origional_impl(*args, **kargs)
        assert len(message.destination.addresses) == 1
        if __debug__: dprint("create ", message.destination.addresses[0][0], ":", message.destination.addresses[0][1])
        log("walktest.log", "out-introduction-request", destination_address=message.payload.destination_address, source_lan_address=message.payload.source_lan_address, source_wan_address=message.payload.source_wan_address, advice=message.payload.advice, identifier=message.payload.identifier)
        return message

    def on_introduction_request(self, meta, messages):
        for message in messages:
            if __debug__: dprint("from ", message.address[0], ":", message.address[1], "  LAN ", message.payload.source_lan_address[0], ":", message.payload.source_lan_address[1], "  WAN ", message.payload.source_wan_address[0], ":", message.payload.source_wan_address[1])
            log("walktest.log", "in-introduction-request", source=message.address, destination_address=message.payload.destination_address, source_lan_address=message.payload.source_lan_address, source_wan_address=message.payload.source_wan_address, advice=message.payload.advice, identifier=message.payload.identifier)
        return meta.__origional_handle(messages)

    def impl_introduction_response(self, meta, *args, **kargs):
        message = meta.__origional_impl(*args, **kargs)
        assert len(message.destination.addresses) == 1
        if __debug__: dprint("create ", message.destination.addresses[0][0], ":", message.destination.addresses[0][1])
        log("walktest.log", "out-introduction-response", destination_address=message.payload.destination_address, source_lan_address=message.payload.source_lan_address, source_wan_address=message.payload.source_wan_address, lan_introduction_address=message.payload.lan_introduction_address, wan_introduction_address=message.payload.wan_introduction_address, identifier=message.payload.identifier)
        return message

    def on_introduction_response(self, meta, messages):
        for message in messages:
            if __debug__: dprint("from ", message.address[0], ":", message.address[1], " -> ", message.payload.lan_introduction_address[0], ":", message.payload.lan_introduction_address[1], " or ", message.payload.wan_introduction_address[0], ":", message.payload.wan_introduction_address[1])
            log("walktest.log", "in-introduction-response", source=message.address, destination_address=message.payload.destination_address, source_lan_address=message.payload.source_lan_address, source_wan_address=message.payload.source_wan_address, lan_introduction_address=message.payload.lan_introduction_address, wan_introduction_address=message.payload.wan_introduction_address, identifier=message.payload.identifier)
        return meta.__origional_handle(messages)

    def impl_puncture_request(self, meta, *args, **kargs):
        message = meta.__origional_impl(*args, **kargs)
        assert len(message.destination.addresses) == 1
        if __debug__: dprint("create ", message.destination.addresses[0][0], ":", message.destination.addresses[0][1])
        log("walktest.log", "out-puncture-request", destination=message.destination.addresses[0], lan_walker_address=message.payload.lan_walker_address, wan_walker_address=message.payload.wan_walker_address)
        return message
    
    def on_puncture_request(self, meta, messages):
        for message in messages:
            if __debug__: dprint("from ", message.address[0], ":", message.address[1])
            log("walktest.log", "in-puncture-request", source=message.address, lan_walker_address=message.payload.lan_walker_address, wan_walker_address=message.payload.wan_walker_address)
        return meta.__origional_handle(messages)
    
    def impl_puncture(self, meta, *args, **kargs):
        message = meta.__origional_impl(*args, **kargs)
        assert len(message.destination.addresses) == 1
        if __debug__: dprint("create ", message.destination.addresses[0][0], ":", message.destination.addresses[0][1])
        log("walktest.log", "out-puncture", destination=message.destination.addresses[0])
        return message

    def on_puncture(self, meta, messages):
        for message in messages:
            if __debug__: dprint("from ", message.address[0], ":", message.address[1])
            log("walktest.log", "in-puncture", source=message.address)
        return meta.__origional_handle(messages)

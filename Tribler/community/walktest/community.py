from lencoder import log

from Tribler.Core.dispersy.community import Community
from Tribler.Core.dispersy.conversion import DefaultConversion

if __debug__:
    from Tribler.Core.dispersy.dprint import dprint

class WalktestCommunity(Community):
    def initiate_meta_messages(self):
        return []

    def initiate_conversions(self):
        return [DefaultConversion(self)]

    def dispersy_start_walk(self):
        return self._dispersy.start_walk(self)

    def dispersy_on_introduction_request(self, messages):
        for message in messages:
            if __debug__: dprint("from ", message.address[0], ":", message.address[1], "  LAN ", message.payload.source_lan_address[0], ":", message.payload.source_lan_address[1], "  WAN ", message.payload.source_wan_address[0], ":", message.payload.source_wan_address[1], force=1)
            log("walktest.log", "in-introduction-request", source=message.address, destination_address=message.payload.destination_address, source_lan_address=message.payload.source_lan_address, source_wan_address=message.payload.source_wan_address, advice=message.payload.advice, identifier=message.payload.identifier)
        return self._dispersy.on_introduction_request(messages)

    def dispersy_on_introduction_response(self, messages):
        for message in messages:
            if __debug__: dprint("from ", message.address[0], ":", message.address[1], "  LAN ", message.payload.source_lan_address[0], ":", message.payload.source_lan_address[1], "  WAN ", message.payload.source_wan_address[0], ":", message.payload.source_wan_address[1], force=1)
            log("walktest.log", "in-introduction-response", source=message.address, destination_address=message.payload.destination_address, source_lan_address=message.payload.source_lan_address, source_wan_address=message.payload.source_wan_address, lan_introduction_address=message.payload.lan_introduction_address, wan_introduction_address=message.payload.wan_introduction_address, identifier=message.payload.identifier)
        return self._dispersy.on_introduction_response(messages)

    def dispersy_on_puncture_request(self, messages):
        for message in messages:
            if __debug__: dprint("from ", message.address[0], ":", message.address[1], force=1)
            log("walktest.log", "in-puncture-request", source=message.address, lan_walker_address=message.payload.lan_walker_address, wan_walker_address=message.payload.wan_walker_address)
        return self._dispersy.on_puncture_request(messages)

    def dispersy_on_puncture(self, messages):
        for message in messages:
            if __debug__: dprint("from ", message.address[0], ":", message.address[1], force=1)
            log("walktest.log", "in-puncture", source=message.address)
        return self._dispersy.on_puncture(messages)

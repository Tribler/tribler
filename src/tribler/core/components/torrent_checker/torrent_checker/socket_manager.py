import asyncio
import logging
import struct
from asyncio import DatagramProtocol

import libtorrent

from tribler.core.components.socks_servers.socks5.client import Socks5Client
from tribler.core.components.torrent_checker.torrent_checker.dataclasses import UdpRequest


class UdpSocketManager(DatagramProtocol):
    """
    The UdpSocketManager ensures that the network packets are forwarded to the right UdpTrackerSession.
    """

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.requests = {}
        self.transport = None
        self.proxy_transports = {}

    def connection_made(self, transport):
        self.transport = transport

    async def get_proxy_transport(self, socks_proxy):
        transport = self.transport

        if socks_proxy:
            transport = self.proxy_transports.get(socks_proxy, Socks5Client(socks_proxy, self.datagram_received))
            if not transport.associated:
                await transport.associate_udp()
            if socks_proxy not in self.proxy_transports:
                self.proxy_transports[socks_proxy] = transport

        return transport

    async def send(self, udp_request: UdpRequest, response_callback=None):
        transport = await self.get_proxy_transport(udp_request.socks_proxy)

        host, port = udp_request.receiver[0], udp_request.receiver[1]
        try:
            transport.sendto(udp_request.data, (host, port))
            self.requests[udp_request.transaction_id] = (udp_request, response_callback)

        except OSError as e:
            self._logger.warning("Unable to write data to %s:%d - %s", host, port, e)
            return RuntimeError("Unable to write to socket - " + str(e))

    def datagram_received(self, data, _):
        # If the incoming data is valid, find the tracker session and give it the data and origin request
        if data and len(data) >= 4:
            transaction_id = struct.unpack_from('!i', data, 4)[0]

            # if the transaction id is not in the requests, try decoding using bdecode
            if transaction_id not in self.requests:
                decoded = libtorrent.bdecode(data)
                if not decoded or b't' not in decoded:
                    return

                transaction_id = decoded[b't']
                if transaction_id not in self.requests:
                    return

            udp_request, response_callback = self.requests.pop(transaction_id, None)
            if response_callback:
                # pass
                asyncio.ensure_future(response_callback(udp_request, data))

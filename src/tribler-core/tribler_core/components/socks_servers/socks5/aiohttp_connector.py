import socket
from asyncio import wait_for

from aiohttp import TCPConnector
from aiohttp.abc import AbstractResolver

from tribler_core.components.socks_servers.socks5.client import Socks5Client


class FakeResolver(AbstractResolver):

    async def resolve(self, host, port=0, family=socket.AF_INET):
        return [{'hostname': host,
                 'host': host, 'port': port,
                 'family': family, 'proto': 0,
                 'flags': 0}]

    async def close(self):
        pass


class Socks5Connector(TCPConnector):
    def __init__(self, proxy_addr, **kwargs):
        kwargs['resolver'] = FakeResolver()

        super().__init__(**kwargs)
        self.proxy_addr = proxy_addr

    # pylint: disable=W0221
    async def _wrap_create_connection(self, protocol_factory, host, port, **kwargs):
        client = Socks5Client(self.proxy_addr, lambda *_: None)

        if 'timeout' in kwargs and hasattr(kwargs['timeout'], 'sock_connect'):
            await wait_for(client.connect_tcp((host, port)), timeout=kwargs['timeout'].sock_connect)
        else:
            await client.connect_tcp((host, port))

        proto = protocol_factory()
        transport = client.transport
        transport._protocol = proto  # pylint: disable=W0212
        proto.transport = transport
        return transport, proto

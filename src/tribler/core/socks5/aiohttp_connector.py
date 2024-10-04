from __future__ import annotations

import socket
from asyncio import BaseTransport, wait_for
from typing import TYPE_CHECKING, Callable

from aiohttp import TCPConnector
from aiohttp.abc import AbstractResolver

from tribler.core.socks5.client import Socks5Client, Socks5ClientUDPConnection

if TYPE_CHECKING:
    from aiohttp.abc import ResolveResult


class FakeResolver(AbstractResolver):
    """
    Pretend to resolve an address. Just echo it back.
    """

    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_INET) -> list[ResolveResult]:
        """
        Resolve a host to itself.
        """
        return [{"hostname": host,
                 "host": host, "port": port,
                 "family": family, "proto": 0,
                 "flags": 0}]

    async def close(self) -> None:
        """
        Close this resolver.
        """


class Socks5Connector(TCPConnector):
    """
    A connector for Socks5 to create clients.
    """

    def __init__(self, proxy_addr: tuple, **kwargs) -> None:
        """
        Create a new connector.
        """
        kwargs["resolver"] = FakeResolver()

        super().__init__(**kwargs)
        self.proxy_addr = proxy_addr

    async def _wrap_create_connection(self,  # type: ignore[override]
                                      protocol_factory: Callable[[], Socks5ClientUDPConnection],
                                      **kwargs) -> tuple[BaseTransport, Socks5ClientUDPConnection]:
        """
        Create a transport and its associated connection.
        """
        client = Socks5Client(self.proxy_addr, lambda *_: None)
        host, port = kwargs.pop("addr_infos")[0][-1]

        if "timeout" in kwargs and hasattr(kwargs["timeout"], "sock_connect"):
            await wait_for(client.connect_tcp((host, port)), timeout=kwargs["timeout"].sock_connect)
        else:
            await client.connect_tcp((host, port))

        proto = protocol_factory()
        transport = client.transport
        transport._protocol = proto  # noqa: SLF001
        proto.transport = transport
        return transport, proto

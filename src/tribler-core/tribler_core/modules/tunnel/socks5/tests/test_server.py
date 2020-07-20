import pytest

from tribler_core.modules.tunnel.socks5.server import Socks5Server


@pytest.fixture
async def socks5_server(free_port):
    socks5_server = Socks5Server(free_port, None)
    yield socks5_server
    await socks5_server.stop()


@pytest.mark.asyncio
async def test_start_server(socks5_server):
    """
    Test writing an invalid version to the socks5 server
    """
    await socks5_server.start()

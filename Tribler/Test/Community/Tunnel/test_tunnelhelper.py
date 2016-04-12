from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.tunnel.main import Tunnel
from Tribler.community.tunnel.tunnel_community import TunnelSettings


class TestTunnelHelpers(AbstractServer):

    def test_start_stop(self):
        tunnel = Tunnel(TunnelSettings())
        tunnel.start(None)
        tunnel.stop()

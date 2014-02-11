import socket
import logging
from Tribler.community.anontunnel import exitsocket
from Tribler.community.anontunnel.community import TunnelObserver

__author__ = 'chris'
logger = logging.getLogger()


class DefaultExitStrategy(TunnelObserver):
    def __init__(self, raw_server, proxy):
        """
        @type proxy: Tribler.community.anontunnel.community.ProxyCommunity.ProxyCommunity
        """

        self.raw_server = raw_server
        self.proxy = proxy
        self._exit_sockets = {}
        proxy.add_observer(self)

    def on_exiting_from_tunnel(self, circuit_id, return_candidate, destination, data):
        logger.debug("EXIT DATA packet to %s", destination)

        try:
            self.get_exit_handler(circuit_id, return_candidate).sendto(data, destination)
        except socket.error:
            logger.exception("Dropping packets while we are EXITing data")

    @staticmethod
    def create(proxy, raw_server, circuit_id, address):
        # There is a special case where the circuit_id is None, then we act as EXIT node ourselves. In this case we
        # create a ShortCircuitHandler that bypasses dispersy by patching ENTER packets directly into the Proxy's
        # on_data event.
        if circuit_id in proxy.circuits and proxy.circuits[circuit_id].goal_hops == 0:
            return_handler = exitsocket.ShortCircuitExitSocket(raw_server, proxy, circuit_id, address)
        else:
            # Otherwise incoming ENTER packets should propagate back over the Dispersy tunnel, we use the
            # CircuitReturnHandler. It will use the DispersyTunnelProxy.send_data method to forward the data packet
            return_handler = exitsocket.TunnelExitSocket(raw_server, proxy, circuit_id, address)

        return return_handler

    def get_exit_handler(self, circuit_id, address):
        # If we don't have an exit socket yet for this socket, create one
        if not (circuit_id in self._exit_sockets):
            return_handler = self.create(self.proxy, self.raw_server, circuit_id, address)
            self._exit_sockets[circuit_id] = return_handler
        return self._exit_sockets[circuit_id]
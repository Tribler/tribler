from Tribler.community.anontunnel.ConnectionHandlers.CircuitReturnHandler import ShortCircuitReturnHandler, CircuitReturnHandler

__author__ = 'Chris'

class CircuitReturnFactory(object):
    def create(self, proxy, raw_server, circuit_id, address):

        # There is a special case where the circuit_id is None, then we act as EXIT node ourselves. In this case we
        # create a ShortCircuitHandler that bypasses dispersy by patching ENTER packets directly into the Proxy's
        # on_data event.
        if circuit_id is 0:
            return_handler = ShortCircuitReturnHandler(raw_server, proxy, address)
        else:
            # Otherwise incoming ENTER packets should propagate back over the Dispersy tunnel, we use the
            # CircuitReturnHandler. It will use the DispersyTunnelProxy.send_data method to forward the data packet
            return_handler = CircuitReturnHandler(raw_server, proxy, circuit_id, address)

        return return_handler




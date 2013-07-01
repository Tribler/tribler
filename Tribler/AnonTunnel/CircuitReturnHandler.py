__author__ = 'Chris'

import logging
logger = logging.getLogger(__name__)


class CircuitReturnHandler(object):
    """
    Sends incoming UDP packets back over the DispersyTunnelProxy.
    """

    def __init__(self, socket,proxy, circuit_id, destination_address):
        """
        Instantiate a new return handler

        :param proxy: instance to use to push packets back into upon reception of an external UDP packet
        :param circuit_id: the circuit to use to pass messages over in the tunnel proxy
        :param destination_address: the first hop of the circuit
        :param socket: the socket that listens to UDP packets

        :type proxy: DispersyTunnelProxy

        """
        self.proxy = proxy
        self.destination_address = destination_address
        self.circuit_id = circuit_id
        self.socket = socket


    def data_came_in(self, packets):
        """
        Method called by the server when a new UDP packet has been received
        :param packets: list of tuples (source address, packet) of the UDP packets received
        """

        for source_address, packet in packets:
            logger.info("ENTER DATA packet FROM %s", source_address)
            self.proxy.send_data(
                circuit_id = self.circuit_id,
                address= self.destination_address,
                ultimate_destination=None,
                payload = packet,
                origin = source_address
            )


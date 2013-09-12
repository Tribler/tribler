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

        :type proxy: Tribler.AnonTunnel.DispersyTunnelProxy.DispersyTunnelProxy

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

class ShortCircuitReturnHandler(object):
    """
    Only used when there are no circuits, it will be a 0-hop tunnel. So there is no anonymity at all.
    """

    def __init__(self, socket,proxy, destination_address):
        """
        Instantiate a new return handler

        :param proxy: instance to use to push packets back into upon reception of an external UDP packet
        :param destination_address: the first hop of the circuit
        :param socket: the socket that listens to UDP packets

        :type proxy: Tribler.AnonTunnel.DispersyTunnelProxy.DispersyTunnelProxy

        """
        self.proxy = proxy
        self.destination_address = destination_address
        self.socket = socket


    def data_came_in(self, packets):
        """
        Method called by the server when a new UDP packet has been received
        :param packets: list of tuples (source address, packet) of the UDP packets received
        """

        for source_address, packet in packets:
            logger.info("ENTER DATA packet FROM %s", source_address)
            meta = self.proxy.community.get_meta_message("data")
            message = meta.impl(
                              distribution=(self.proxy.community.global_time,),
                              payload=(0, self.destination_address, packet, source_address))

            self.proxy.fire("on_data", data=message.payload)


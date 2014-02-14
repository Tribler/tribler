from Tribler.community.anontunnel.payload import DataMessage

__author__ = 'Chris'

import logging

logger = logging.getLogger()


class TunnelExitSocket(object):
    """
    Sends incoming UDP packets back over the DispersyTunnelProxy.
    """

    def __init__(self, raw_server, proxy, circuit_id, destination_address):
        """
        Instantiate a new return handler

        :param proxy: instance to use to push packets back into upon reception
            of an external UDP packet
        :param circuit_id: the circuit to use to pass messages over in the
            tunnel proxy
        :param destination_address: the first hop of the circuit

        :type proxy: Tribler.community.anontunnel.community.ProxyCommunity

        """

        socket = raw_server.create_udpsocket(0, "0.0.0.0")
        raw_server.start_listening_udp(socket, self)

        self.proxy = proxy
        self.destination_address = destination_address
        self.circuit_id = circuit_id
        self.socket = socket

    def sendto(self, data, destination):
        """
        Sends data to the destination over an UDP socket
        @param str data: the data to send
        @param (str, int) destination: the destination to send to
        """
        self.socket.sendto(data, destination)

    def data_came_in(self, packets):
        """
        Method called by the server when a new UDP packet has been received
        :param packets: list of tuples (source address, packet) of the UDP
            packets received
        """

        for source_address, packet in packets:
            logger.info("ENTER DATA in TunnelExitSocket, packet FROM %s",
                        source_address)
            self.proxy.tunnel_data_to_origin(
                circuit_id=self.circuit_id,
                candidate=self.destination_address,
                source_address=source_address,
                accepted_on=self.socket.getsockname(),
                payload=packet)


class ShortCircuitExitSocket(object):
    """
    Only used when there are no circuits, it will be a 0-hop tunnel. So there
    is no anonymity at all.
    """

    def __init__(self, raw_server, proxy, circuit_id, destination_address):
        """
        Instantiate a new return handler

        :param proxy: instance to use to push packets back into upon reception
            of an external UDP packet
        :param destination_address: the first hop of the circuit

        :type proxy: ProxyCommunity

        """

        socket = raw_server.create_udpsocket(0, "0.0.0.0")
        raw_server.start_listening_udp(socket, self)

        self.proxy = proxy
        self.destination_address = destination_address
        self.socket = socket
        self.circuit_id = circuit_id

    def data_came_in(self, packets):
        """
        Method called by the server when a new UDP packet has been received

        :param packets: list of tuples (source address, packet) of the UDP
            packets received
        """

        for source_address, packet in packets:
            logger.info("ENTER DATA in ShortCircuitSocket, packet FROM %s",
                        source_address)
            message = DataMessage(("0.0.0.0", 0), packet, source_address)
            self.proxy.on_data(self.circuit_id, None, message)

    def sendto(self, data, destination):
        """
        Sends data to the destination over an UDP socket
        @param str data: the data to send
        @param (str, int) destination: the destination to send to
        """

        self.socket.sendto(data, destination)
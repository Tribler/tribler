__author__ = 'Chris'

import logging
logger = logging.getLogger(__name__)

class CircuitReturnHandler(object):
    def __init__(self, socket,proxy, circuit_id, destination_address):
        """

        :type proxy: TunnelProxy
        """
        self.proxy = proxy
        self.destination_address = destination_address
        self.circuit_id = circuit_id
        self.socket = socket


    def data_came_in(self, packets):
        for source_address, packet in packets:
            logger.info("ENTER DATA packet FROM %s", source_address)
            self.proxy.send_data(
                circuit_id = self.circuit_id,
                address= self.destination_address,
                ultimate_destination=None,
                payload = packet,
                origin = source_address
            )


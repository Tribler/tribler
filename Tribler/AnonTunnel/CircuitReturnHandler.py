__author__ = 'Chris'

import logging
logger = logging.getLogger(__name__)

class CircuitReturnHandler(object):
    def __init__(self, socket,proxy, circ_id, destination_address):
        """

        :type proxy: TunnelProxy
        """
        self.proxy = proxy
        self.destination_address = destination_address
        self.circ_id = circ_id


    def data_came_in(self, packets):
        for source_address, packet in packets:
            logger.info("ENTER DATA packet FROM %s", source_address)
            self.proxy.send_data(
                circuit_id = self.circ_id,
                address= self.destination_address,
                ultimate_destination=None,
                payload = packet,
                origin = source_address
            )


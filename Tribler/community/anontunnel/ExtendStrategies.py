import logging
logger = logging.getLogger(__name__)

import itertools
from Tribler.community.anontunnel import ProxyMessage
from Tribler.community.anontunnel.DispersyTunnelProxy import CIRCUIT_STATE_BROKEN, CIRCUIT_STATE_EXTENDING

__author__ = 'chris'


class TrustThyNeighbour:
    def __init__(self, proxy, circuit):
        """
        :type proxy: Tribler.community.anontunnel.DispersyTunnelProxy.DispersyTunnelProxy
        :param circuit:
        """
        self.circuit = circuit
        self.proxy = proxy

        def _timer():
            while True:
                self.extend()
                yield 2.0

        #circuit.subscribe("created", self.extend)
        #circuit.subscribe("extended", self.extend)
        self.__timer = proxy.callback.register(_timer)

    def stop(self):
        self.proxy.callback.unregister(self.__timer)

    def extend(self):
        if not self.circuit.created or self.circuit.state == CIRCUIT_STATE_BROKEN or self.circuit.goal_hops <= len(self.circuit.hops):
            return

        with self.proxy.lock:
            self.circuit.state = CIRCUIT_STATE_EXTENDING

        logger.warning("We are trusting our hop to extend circuit %d" % (self.circuit.id))
        self.proxy.send_message(self.circuit.candidate, self.circuit.id, ProxyMessage.MESSAGE_EXTEND,
                                ProxyMessage.ExtendMessage(None))


class RandomAPriori:
    def __init__(self, proxy, circuit):
        """
        :type proxy: Tribler.community.anontunnel.DispersyTunnelProxy.DispersyTunnelProxy
        :param circuit:
        """
        self.circuit = circuit
        self.proxy = proxy

        self.desired_hops = None
        self.punctured_until = 0

        def __timer():
            while True:
                yield self.extend()

        self.__timer = proxy.callback.register(__timer)


    def stop(self):
        self.proxy.callback.unregister(self.__timer)


    def extend(self):
        if not self.circuit.created or self.circuit.state == CIRCUIT_STATE_BROKEN or self.circuit.goal_hops <= len(self.circuit.hops):
            return 2.0

        with self.proxy.lock:
            self.circuit.state = CIRCUIT_STATE_EXTENDING

        if not self.desired_hops:
            candidate_hops = [self.circuit.candidate]
            it = self.proxy.community.dispersy_yield_verified_candidates()

            while len(candidate_hops) < self.circuit.goal_hops:
                candidate = next(it, None)

                if not candidate:
                    break

                if candidate not in candidate_hops:
                    candidate_hops.append(candidate)

            if len(candidate_hops) == self.circuit.goal_hops:
                self.desired_hops = candidate_hops
                logger.warning("Determined we want hops %s  for circuit %d" % ([x.sock_addr for x in candidate_hops], self.circuit.id))
            else:
                logger.warning("Cannot find enough hops for circuit %d" % (self.circuit.id))
                return 10.0

        if self.punctured_until < len(self.circuit.hops):
        # We need to puncture the NAT of the new hop with the last hop at this time.
            to_puncture = self.desired_hops[self.punctured_until + 1]
            current_end_of_tunnel = self.circuit.hops[-1]

            self.proxy.send_message(to_puncture, 0, ProxyMessage.MESSAGE_PUNCTURE, ProxyMessage.PunctureMessage(current_end_of_tunnel))
            self.punctured_until += 1
            logger.warning("Sent PUNCTURE(%s) to %s" % (current_end_of_tunnel, to_puncture))

            # Wait 5 seconds before sending the EXTEND
            return 5.0


        # We have punctured the next hop, so send the EXTEND
        self.proxy.send_message(self.circuit.candidate, self.circuit.id, ProxyMessage.MESSAGE_EXTEND,
                                ProxyMessage.ExtendMessage(self.desired_hops[len(self.circuit.hops)].sock_addr))

        return 2.0

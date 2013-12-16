import logging
logger = logging.getLogger(__name__)

from Tribler.community.anontunnel.globals import *
from Tribler.community.anontunnel.payload import *

import itertools

__author__ = 'chris'

class TrustThyNeighbour:
    def __init__(self, proxy, circuit):
        """
        :type proxy: Tribler.community.anontunnel.community.ProxyCommunity
        :param circuit:
        """
        self.proxy = proxy
        self.circuit = circuit

    def stop(self):
        pass

    def extend(self):
        assert self.circuit.state == CIRCUIT_STATE_EXTENDING, "Only circuits with state CIRCUIT_STATE_EXTENDING can be extended"
        assert self.circuit.goal_hops > len(self.circuit.hops), "Circuits with correct length cannot be extended"

        logger.info("We are trusting our hop to extend circuit %d" % (self.circuit.circuit_id))
        self.proxy.send_message(self.circuit.candidate, self.circuit.circuit_id, MESSAGE_EXTEND, ExtendMessage(None))


class RandomAPriori:
    def __init__(self, proxy, circuit):
        """
        :type proxy: Tribler.community.anontunnel.community.ProxyCommunity
        :param circuit:
        """
        self.proxy = proxy
        self.circuit = circuit

        self.desired_hops = None
        self.punctured_until = 0

    def stop(self):
        pass

    def extend(self):
        #TODO: this one should be looked at, seems a bit dodgy
        
        assert self.circuit.state == CIRCUIT_STATE_EXTENDING, "Only circuits with state CIRCUIT_STATE_EXTENDING can be extended"
        assert self.circuit.goal_hops > len(self.circuit.hops), "Circuits with correct length cannot be extended"

        if not self.desired_hops:
            #TODO: shouldn't we make sure that the complete circuit consists of unique candidates?
            candidate_hops = [self.circuit.candidate]
            
            it = list(self.proxy.dispersy_yield_verified_candidates())
            for candidate in it:
                if len(candidate_hops) >= self.circuit.goal_hops:
                    break
                
                if candidate not in candidate_hops:
                    candidate_hops.append(candidate)

            if len(candidate_hops) == self.circuit.goal_hops:
                self.desired_hops = candidate_hops
                logger.info("Determined we want hops %s for circuit %d" % ([x.sock_addr for x in candidate_hops], self.circuit.id))
                
            else:
                raise ValueError("Dont have enough hops to create circuit")

        if self.punctured_until < len(self.circuit.hops):
            # We need to puncture the NAT of the new hop with the last hop at this time.
            to_puncture = self.desired_hops[self.punctured_until + 1]
            current_end_of_tunnel = self.circuit.hops[-1]

            self.proxy.send_message(to_puncture, 0, MESSAGE_PUNCTURE, PunctureMessage(current_end_of_tunnel))
            self.punctured_until += 1
            
            logger.info("Sent PUNCTURE(%s) to %s" % (current_end_of_tunnel, to_puncture))

            def send_extend():
                # We have punctured the next hop, so send the EXTEND
                self.proxy.send_message(self.circuit.candidate, self.circuit.id, MESSAGE_EXTEND,
                                        ExtendMessage(self.desired_hops[len(self.circuit.hops)].sock_addr))

            self.proxy.callback.register(send_extend, delay=5.0)

        return 2.0

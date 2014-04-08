"""
Event handling related module

Can be safely imported as it does not import any dependencies in the global
 namespace
"""

__author__ = 'chris'


class TunnelObserver(object):
    """
    The TunnelObserver class is being notified by the ProxyCommunity in case
    a circuit / relay breaks, the global state changes or when data is being
    sent and received
    """

    def __init__(self):
        pass

    def on_break_circuit(self, circuit):
        """
        Called when a circuit has been broken and removed from the
        ProxyCommunity
        @param Circuit circuit: the circuit that has been broken
        """
        pass

    # noinspection PyMethodMayBeStatic
    def on_break_relay(self, relay_key):
        """
        Called when a relay has been broken due to inactivity
        @param ((str, int), int) relay_key: the identifier in
            (sock_addr, circuit) format
        """
        pass

    def on_incoming_from_tunnel(self, community, circuit, origin, data):
        """
        Called when we are receiving data from our circuit

        @type community: Tribler.community.anontunnel.community.ProxyCommunity
        @param Circuit circuit: the circuit the data was received on
        @param (str, int) origin: the origin of the packet in sock_addr format
        @param str data: the data received
        """
        pass

    def on_exiting_from_tunnel(self, circuit_id, candidate, destination, data):
        """
        Called when a DATA message has been received destined for the outside
        world

        @param int circuit_id: the circuit id where the the DATA message was
            received on
        @param Candidate candidate: the relay candidate who relayed the message
        @param (str, int) destination: the packet's ultimate destination
        @param data: the payload
        """
        pass

    def on_tunnel_stats(self, community, candidate, stats):
        """
        Called when a STATS message has been received
        @type community: Tribler.community.anontunnel.community.ProxyCommunity
        @type candidate: Candidate
        @type stats: dict
        """
        pass

    def on_enter_tunnel(self, circuit_id, candidate, origin, payload):
        """
        Called when we received a packet from the outside world

        @param int circuit_id: the circuit for which we received data from the
            outside world
        @param Candidate candidate: the known relay for this circuit
        @param (str, int) origin: the outside origin of the packet
        @param str payload: the packet's payload
        """
        pass

    def on_send_data(self, circuit_id, candidate, destination, payload):
        """
        Called when uploading data over a circuit

        @param int circuit_id: the circuit where data being uploaded over
        @param Candidate candidate: the relay used to send data over
        @param (str, int) destination: the destination of the packet
        @param str payload: the packet's payload
        """
        pass

    def on_relay(self, from_key, to_key, direction, data):
        """
        Called when we are relaying data from_key to to_key

        @param ((str, int), int) from_key: the relay we are getting data from
        @param ((str, int), int) to_key: the relay we are sending data to
        @param direction: ENDPOINT if we are relaying towards the end of the
            tunnel, ORIGINATOR otherwise
        @type data: str
        @return:
        """
        pass

    def on_unload(self):
        """
        Called when the ProxyCommunity is being unloaded
        """
        pass


class CircuitPoolObserver(object):
    """
    An observer interface for circuit pools. Contains the event triggered when
    a new circuit has been added to the pool
    """
    def __init__(self):
        pass

    def on_circuit_added(self, pool, circuit):
        """
        A circuit has been added to the pool
        @param CircuitPool pool: the pool to which the circuit has been added
        @param Circuit circuit: the circuit that has been added
        """
        pass

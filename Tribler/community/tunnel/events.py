"""
Event handling related module

Can be safely imported as it does not import any dependencies in the global
 namespace
"""

__author__ = 'chris'


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

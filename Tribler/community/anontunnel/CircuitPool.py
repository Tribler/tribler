import logging
import threading
from Tribler.community.anontunnel.events import TunnelObserver

__author__ = 'chris'


class NotEnoughCircuitsException(Exception):
    pass


class CircuitPool(object, TunnelObserver):
    def __init__(self, proxy, size, name):
        super(CircuitPool, self).__init__()

        self._logger = logging.getLogger(__name__)
        self._logger.warning("Creating a circuit pool of size %d with name '%s'", size, name)

        self.proxy = proxy
        self.lock = threading.RLock()
        self.size = size
        self.circuits = set()
        self.allocated_circuits = set()
        self.name = name

        self.proxy.observers.append(self)

    def on_break_circuit(self, circuit):
        if circuit in self.circuits:
            self.remove_circuit(circuit)

    @property
    def lacking(self):
        return max(0, self.size - len(self.circuits))

    @property
    def available_circuits(self):
        return [circuit
                for circuit in self.circuits
                if circuit not in self.allocated_circuits]

    def remove_circuit(self, circuit):
        self._logger.warning("Removing circuit %d from pool '%s'", circuit.circuit_id, self.name)
        with self.lock:
            self.circuits.remove(circuit)

    def fill(self, circuit):
        self._logger.warning("Adding circuit %d to pool '%s'", circuit.circuit_id, self.name)

        with self.lock:
            self.circuits.add(circuit)

    def deallocate(self, circuit):
        self._logger.warning("Deallocate circuit %d from pool '%s'", circuit.circuit_id, self.name)

        with self.lock:
            self.allocated_circuits.remove(circuit)

    def allocate(self):

        with self.lock:
            try:
                circuit = next((c for c in self.circuits if c not in self.allocated_circuits))
                self.allocated_circuits.add(circuit)
                self._logger.warning("Allocate circuit %d from pool %s", circuit.circuit_id, self.name)

                return circuit

            except StopIteration:
                if not self.lacking:
                    self.size *= 2

                raise NotEnoughCircuitsException()
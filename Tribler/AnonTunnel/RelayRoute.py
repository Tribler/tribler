class RelayRoute(object):
    def __init__(self, circuit_id, from_address, to_address):
        self.from_address = from_address
        self.to_address = to_address
        self.circuit_id = circuit_id
class Circuit(object):
    """ Circuit data structure storing the id, status, first hop and all hops """

    def __init__(self, circuit_id, address):
        """
        Instantiate a new Circuit data structure

        :param circuit_id: the id of the circuit
        :param address: the first hop of the circuit
        :return: Circuit
        """
        self.created = False
        self.id = circuit_id
        self.address = address
        self.hops = [address]
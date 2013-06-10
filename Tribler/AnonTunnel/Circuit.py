""" Circuit data structure storing the id, status, first hop and all hops """


class Circuit(object):
    def __init__(self, circuit_id, address):
        self.created = False
        self.id = circuit_id
        self.address = address
        self.hops = [address]
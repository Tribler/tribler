""" Circuit data structure storing the id, status, first hop and all hops """
class Circuit:
    def __init__(self, circ_id, address):
        self.created = False
        self.id = circ_id
        self.address = address
        self.hops = [address]
__author__ = 'Chris'


class Hop:
    def __init__(self, address, pub_key, dh_first_part):
        self.address = address
        self.pub_key = pub_key
        self.session_key = None
        self.dh_first_part = dh_first_part

    @property
    def session_key(self):
        return self.session_key
    @property
    def dh_first_part(self):
        return self.dh_first_part

    @property
    def host(self):
        return self.address[0]

    @property
    def port(self):
        return self.address[1]

    @staticmethod
    def fromCandidate(candidate):
        hop = Hop(candidate.sock_addr, None, None)
        return hop

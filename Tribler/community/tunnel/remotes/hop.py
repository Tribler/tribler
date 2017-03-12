from Tribler.community.tunnel.remotes.remote_object import RemoteObject, shared
from Tribler.dispersy.crypto import LibNaCLPK


class Hop(RemoteObject):

    """
    Circuit Hop containing the address, its public key and the first part of
    the Diffie-Hellman handshake
    """

    def __init__(self, public_key):
        """
        @param None|LibNaCLPK public_key: public key object of the hop
        """

        assert isinstance(public_key, LibNaCLPK)

        self.session_keys = None
        self.dh_first_part = None
        self.dh_secret = None
        self.address = None
        self._public_key = public_key

        self.public_key = public_key

    @shared
    def address(self):
        pass

    @property
    def public_key(self):
        return self._public_key

    @public_key.setter
    def public_key(self, value):
        self._public_key = value
        self.node_public_key = value.key_to_bin()
        self.node_id = value.key_to_hash()

    @property
    def host(self):
        """
        The hop's hostname
        """
        if self.address:
            return self.address[0]
        return " UNKNOWN HOST "

    @property
    def port(self):
        """
        The hop's port
        """
        if self.address:
            return self.address[1]
        return " UNKNOWN PORT "

    @shared
    def node_id(self):
        """
        The hop's nodeid
        """
        pass

    @shared
    def node_public_key(self):
        """
        The hop's public_key
        """
        pass

    @shared(True)
    def hop_id(self):
        pass

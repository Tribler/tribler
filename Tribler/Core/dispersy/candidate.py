from time import time

from dispersydatabase import DispersyDatabase
from member import Member

if __debug__:
    from dprint import dprint

    def is_address(address):
        assert isinstance(address, tuple), type(address)
        assert len(address) == 2, len(address)
        assert isinstance(address[0], str), type(address[0])
        assert address[0], address[0]
        assert isinstance(address[1], int), type(address[1])
        assert address[1] >= 0, address[1]
        return True

class Candidate(object):
    """
    A wrapper around the candidate table in the dispersy database.
    """
    def __init__(self, dispersy, lan_address, wan_address, community=None, is_walk=False, is_stumble=False, is_introduction=False):
        if __debug__:
            from dispersy import Dispersy
            from community import Community
        assert isinstance(dispersy, Dispersy)
        assert is_address(lan_address)
        assert is_address(wan_address)
        assert isinstance(is_walk, bool)
        assert isinstance(is_stumble, bool)
        assert community is None or isinstance(community, Community)
        if __debug__: dprint("discovered ", wan_address[0], ":", wan_address[1], " (", lan_address[0], ":", lan_address[1], ")")
        self._dispersy = dispersy
        self._lan_address = lan_address
        self._wan_address = wan_address
        self._is_walk = is_walk
        self._is_stumble = is_stumble
        self._is_introduction = is_introduction
        self._timestamp = time()
        self._communities = set((community,)) if community else set()

    @property
    def lan_address(self):
        return self._lan_address

    @property
    def wan_address(self):
        return self._wan_address

    @property
    def address(self):
        return self._lan_address if self._dispersy.wan_address[0] == self._wan_address[0] else self._wan_address
    
    @property
    def is_walk(self):
        return self._is_walk

    @property
    def is_stumble(self):
        return self._is_stumble

    @property
    def is_introduction(self):
        return self._is_introduction
    
    @property
    def timestamp(self):
        return self._timestamp

    def in_community(self, community):
        return community in self._communities
    
    def inc_introduction_requests(self, lan_address, wan_address, community):
        if __debug__:
            from community import Community
        assert is_address(lan_address)
        assert is_address(wan_address)
        assert isinstance(community, Community)
        if __debug__: dprint("updated ", wan_address[0], ":", wan_address[1], " (", lan_address[0], ":", lan_address[1], ")")
        self._lan_address = lan_address
        self._wan_address = wan_address
        self._communities.add(community)
        self._timestamp = time()
        self._is_stumble = True

    def inc_introduction_response(self, lan_address, wan_address, community):
        if __debug__:
            from community import Community
        assert is_address(lan_address)
        assert is_address(wan_address)
        assert isinstance(community, Community)
        if __debug__: dprint("updated ", wan_address[0], ":", wan_address[1], " (", lan_address[0], ":", lan_address[1], ")")
        self._lan_address = lan_address
        self._wan_address = wan_address
        self._communities.add(community)
        self._timestamp = time()
        self._is_walk = True

    def inc_introduced(self, community):
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        if __debug__: dprint("updated")
        self._communities.add(community)
        self._is_introduction = True
        
    def inc_any(self, community):
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        if __debug__: dprint("updated ", self._wan_address[0], ":", self._wan_address[1], " (", self._lan_address[0], ":", self._lan_address[1], ")")
        self._communities.add(community)
        self._timestamp = time()

    @property
    def members(self):
        # TODO we should not just trust this information, a member can put any address in their
        # dispersy-identity message.  The database should contain a column with a 'verified' flag.
        # This flag is only set when a handshake was successfull.
        host, port = self.address
        return [Member.get_instance(str(public_key))
                for public_key,
                in list(DispersyDatabase.get_instance().execute(u"SELECT DISTINCT member.public_key FROM identity JOIN member ON member.id = identity.member WHERE identity.host = ? AND identity.port = ? -- AND verified = 1", (unicode(host), port)))]

class BootstrapCandidate(Candidate):
    def __init__(self, dispersy, wan_address):
        super(BootstrapCandidate, self).__init__(dispersy, wan_address, wan_address)

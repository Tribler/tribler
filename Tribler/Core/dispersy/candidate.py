from time import time

if __debug__:
    from dprint import dprint
    from member import Member

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
    def __init__(self, address, lan_address, wan_address, member=None, community=None, connection_type=u"unknown", is_walk=False, is_stumble=False, is_introduction=False):
        if __debug__:
            from community import Community
        assert is_address(address)    
        assert is_address(lan_address)
        assert is_address(wan_address)
        assert address == lan_address or address == wan_address
        assert isinstance(is_walk, bool)
        assert isinstance(is_stumble, bool)
        assert isinstance(is_introduction, bool)
#        assert (member is None and community is None) or (isinstance(member, Member) and isinstance(community, Community))
        assert isinstance(connection_type, unicode) and connection_type in (u"unknown", u"public", "symmetric-NAT")
        if __debug__: dprint("discovered ", wan_address[0], ":", wan_address[1], " (", lan_address[0], ":", lan_address[1], ")")
        self._address = address
        self._lan_address = lan_address
        self._wan_address = wan_address
        self._is_walk = is_walk
        self._is_stumble = is_stumble
        self._is_introduction = is_introduction
        self._connection_type = connection_type
        self._timestamp_incoming = time()
        self._timestamp_last_step = {(member, community.cid):time() - 30.0} if community else {}
        self._global_times = {}

    def __str__(self):
        return "".join(("[",
                        "%s:%d" % self._address if self._address else "",
                        "" if self._address == self._lan_address else " LAN %s:%d" % self._lan_address,
                        "" if self._address == self._wan_address else " WAN %s:%d" % self._wan_address,
                        "]"))
        
    @property
    def address(self):
        return self._address
        
    @property
    def lan_address(self):
        return self._lan_address

    @property
    def wan_address(self):
        return self._wan_address

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
    def connection_type(self):
        return self._connection_type
    
    @property
    def timestamp_incoming(self):
        return self._timestamp_incoming

    def set_global_time(self, community, global_time):
        self._global_times[community.cid] = max(self._global_times.get(community.cid, 0), global_time)

    def get_global_time(self, community):
        return self._global_times.get(community.cid, 0)
    
    def members_in_community(self, community):
        return (member for member, cid in self._timestamp_last_step.iterkeys() if member and cid == community.cid)
    
    def timestamp_last_step_in_community(self, community, default=0.0):
        try:
            return max(timestamp for (_, cid), timestamp in self._timestamp_last_step.iteritems() if cid == community.cid)
        except ValueError:
            return default
    
    def in_community(self, community):
        return any(cid == community.cid for _, cid in self._timestamp_last_step.iterkeys())
    
    def timeout(self, community):
        """
        Called on timeout of a dispersy-introduction-response message

        Returns True if there are communities left where this candidate did not timeout.
        """
        self._timestamp_last_step = dict((((member, cid), timestamp))
                                         for (member, cid), timestamp
                                         in self._timestamp_last_step.iteritems() if not cid == community.cid)
        if community.cid in self._global_times:
            del self._global_times[community.cid]
        return bool(self._timestamp_last_step)

    def out_introduction_request(self, community):
        self._timestamp_last_step = dict((((member, cid), time() if cid == community.cid else timestamp))
                                         for (member, cid), timestamp
                                         in self._timestamp_last_step.iteritems())
        self._timestamp_last_step[(None, community.cid)] = time()
        
    def inc_introduction_requests(self, member, community, lan_address, wan_address, connection_type):
        assert is_address(lan_address)
        assert is_address(wan_address)
        if __debug__: dprint("updated ", wan_address[0], ":", wan_address[1], " (", lan_address[0], ":", lan_address[1], ")")
        self._timestamp_last_step.setdefault((member, community.cid), time() - 30)
        self._lan_address = lan_address
        self._wan_address = wan_address
        self._connection_type = connection_type
        self._is_stumble = True
        self._timestamp_incoming = time()

    def inc_introduction_response(self, lan_address, wan_address, connection_type):
        assert is_address(lan_address)
        assert is_address(wan_address)
        if __debug__: dprint("updated ", wan_address[0], ":", wan_address[1], " (", lan_address[0], ":", lan_address[1], ")")
        self._lan_address = lan_address
        self._wan_address = wan_address
        self._connection_type = connection_type
        self._is_walk = True
        self._timestamp_incoming = time()

    def inc_introduced(self, member, community):
        if __debug__: dprint("updated")
        self._timestamp_last_step.setdefault((member, community.cid), time() - 30)
        self._is_introduction = True
        self._timestamp_incoming = time()

    def inc_puncture_request(self):
        self._timestamp_incoming = time()
        
    def inc_puncture(self, member, community, address, lan_address, wan_address):
        assert is_address(address)
        assert is_address(lan_address)
        assert is_address(wan_address)
        assert address == lan_address or address == wan_address
        if __debug__: dprint("updated ", wan_address[0], ":", wan_address[1], " (", lan_address[0], ":", lan_address[1], ")")
        self._timestamp_last_step.setdefault((member, community.cid), time() - 30)
        self._address = address
        self._lan_address = lan_address
        self._wan_address = wan_address
        self._timestamp_incoming = time()
        
class LocalhostCandidate(Candidate):
    def __init__(self, dispersy):
        super(LocalhostCandidate, self).__init__(dispersy.lan_address, dispersy.lan_address, dispersy.wan_address)
        
class BootstrapCandidate(Candidate):
    def __init__(self, wan_address):
        super(BootstrapCandidate, self).__init__(wan_address, wan_address, wan_address, connection_type=u"public")

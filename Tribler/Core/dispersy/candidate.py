if __debug__:
    from dprint import dprint
    from member import Member

    def is_address(address):
        assert isinstance(address, tuple), type(address)
        assert len(address) == 2, len(address)
        assert isinstance(address[0], str), type(address[0])
        assert address[0], address[0]
        assert not address[0] == "0.0.0.0", address
        assert isinstance(address[1], int), type(address[1])
        assert address[1] >= 0, address[1]
        return True

# delay and lifetime values are chosen to ensure that a candidate will not exceed 60.0 or 30.0
# seconds.  However, taking into account round trip time and processing delay we to use smaller
# values without conflicting with the next 5.0 walk cycle.  Hence, we pick 2.5 seconds below the
# actual cutoff point.
CANDIDATE_ELIGIBLE_DELAY = 27.5
CANDIDATE_ELIGIBLE_BOOTSTRAP_DELAY = 57.5
CANDIDATE_WALK_LIFETIME = 57.5
CANDIDATE_STUMBLE_LIFETIME = 57.5
CANDIDATE_INTRO_LIFETIME = 27.5
CANDIDATE_LIFETIME = 180.0
assert isinstance(CANDIDATE_ELIGIBLE_DELAY, float)
assert isinstance(CANDIDATE_ELIGIBLE_BOOTSTRAP_DELAY, float)
assert isinstance(CANDIDATE_WALK_LIFETIME, float)
assert isinstance(CANDIDATE_STUMBLE_LIFETIME, float)
assert isinstance(CANDIDATE_INTRO_LIFETIME, float)
assert isinstance(CANDIDATE_LIFETIME, float)

class Candidate(object):
    def __init__(self, sock_addr, tunnel):
        assert is_address(sock_addr), sock_addr
        assert isinstance(tunnel, bool), type(tunnel)
        self._sock_addr = sock_addr
        self._tunnel = tunnel

    # @property
    def __get_sock_addr(self):
        return self._sock_addr
    # @sock_addr.setter
    def __set_sock_addr(self, sock_addr):
        self._sock_addr = sock_addr
    # .setter was introduced in Python 2.6
    sock_addr = property(__get_sock_addr, __set_sock_addr)

    @property
    def tunnel(self):
        return self._tunnel

    def get_destination_address(self, wan_address):
        assert is_address(wan_address), wan_address
        return self._sock_addr

    def get_members(self, community):
        # preferably use the WalkerCandidate directly
        candidate = community.dispersy.get_candidate(self._sock_addr)
        if candidate:
            return candidate.get_members(community)
        else:
            return []

    def __str__(self):
        return "{%s:%d}" % self._sock_addr

class WalkCandidate(Candidate):
    """
    A Candidate instance represents a communication endpoint with one or more member/community
    pairs.

    A WalkCandidate is added and removed by the Dispersy random walker when events occur.  These
    events results in the following marks:

    - WALK: we sent an introduction-request.  Viable up to CANDIDATE_WALK_LIFETIME seconds after the
      message was sent.

    - STUMBLE: we received an introduction-request.  Viable up to CANDIDATE_STUMBLE_LIFETIME seconds
      after the message was received.

    - INTRO: we know about this candidate through hearsay.  Viable up to CANDIDATE_INACTIVE seconds
      after the introduction-response message (talking about the candidate) was received.
    """
    class Timestamps(object):
        __slots__ = ["last_walk", "last_stumble", "last_intro"]

        def __init__(self):
            self.last_walk = 0.0
            self.last_stumble = 0.0
            self.last_intro = 0.0

        def merge(self, other):
            assert isinstance(other, WalkCandidate.Timestamps), other
            self.last_walk = max(self.last_walk, other.last_walk)
            self.last_stumble = max(self.last_stumble, other.last_stumble)
            self.last_intro = max(self.last_intro, other.last_intro)

    def __init__(self, sock_addr, tunnel, lan_address, wan_address, connection_type):
        assert is_address(sock_addr), sock_addr
        assert isinstance(tunnel, bool), type(tunnel)
        assert is_address(lan_address)
        assert is_address(wan_address)
        assert isinstance(connection_type, unicode) and connection_type in (u"unknown", u"public", u"symmetric-NAT")

        super(WalkCandidate, self).__init__(sock_addr, tunnel)
        self._lan_address = lan_address
        self._wan_address = wan_address
        self._connection_type = connection_type
        self._associations = set()
        self._timestamps = dict()
        self._global_times = dict()

        if __debug__:
            if not (self.sock_addr == self._lan_address or self.sock_addr == self._wan_address):
                dprint("Either LAN ", self._lan_address, " or the WAN ", self._wan_address, " should be SOCK_ADDR ", self.sock_addr, level="error", stack=True)
                assert False

    @property
    def lan_address(self):
        return self._lan_address

    @property
    def wan_address(self):
        return self._wan_address

    @property
    def connection_type(self):
        return self._connection_type

    def get_destination_address(self, wan_address):
        assert is_address(wan_address), wan_address
        return self._lan_address if wan_address[0] == self._wan_address[0] else self._wan_address

    def merge(self, other):
        assert isinstance(other, WalkCandidate), other
        self._associations.update(other._associations)
        for cid, timestamps in other._timestamps.iteritems():
            if cid in self._timestamps:
                self._timestamps[cid].merge(timestamps)
            else:
                self._timestamps[cid] = timestamps
        for cid, global_time in self._global_times.iteritems():
            self._global_times[cid] = max(self._global_times.get(cid, 0), global_time)

    def set_global_time(self, community, global_time):
        self._global_times[community.cid] = max(self._global_times.get(community.cid, 0), global_time)

    def get_global_time(self, community):
        return self._global_times.get(community.cid, 0)

    def _get_or_create_timestamps(self, community):
        if __debug__:
            from community import Community
            assert isinstance(community, Community)
        timestamps = self._timestamps.get(community.cid)
        if not timestamps:
            self._timestamps[community.cid] = timestamps = self.Timestamps()
        return timestamps

    def associate(self, community, member):
        """
        Once it is confirmed that the candidate is represented by a member, i.e. though a 3-way
        handshake, the member can be associated with the candidate.
        """
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert isinstance(member, Member)
        self._associations.add((community.cid, member))

    def is_associated(self, community, member):
        """
        Check if the (community, member) pair is associated with this candidate.
        """
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert isinstance(member, Member)
        return (community.cid, member) in self._associations

    def disassociate(self, community, member):
        """
        Remove the association with a member.
        """
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert isinstance(member, Member)
        self._associations.remove((community.cid, member))
        if community.cid in self._global_times:
            del self._global_times[community.cid]

    def get_members(self, community):
        """
        Returns all unique Member instances in COMMUNITY associated to this candidate.
        """
        return set(member for cid, member in self._associations if community.cid == cid)

    def in_community(self, community, now):
        """
        Returns True if SELF is either walk, stumble, or intro in COMMUNITY.
        """
        timestamps = self._timestamps.get(community.cid)
        if timestamps:
            return (now < timestamps.last_walk + CANDIDATE_WALK_LIFETIME or
                    now < timestamps.last_stumble + CANDIDATE_STUMBLE_LIFETIME or
                    now < timestamps.last_intro + CANDIDATE_INTRO_LIFETIME)
        else:
            return False

    def is_active(self, community, now):
        """
        Returns True if SELF is either walk or stumble in COMMUNITY.
        """
        timestamps = self._timestamps.get(community.cid)
        if timestamps:
            return (now < timestamps.last_walk + CANDIDATE_WALK_LIFETIME or
                    now < timestamps.last_stumble + CANDIDATE_STUMBLE_LIFETIME)
        return False

    def is_any_active(self, now):
        """
        Returns True if SELF is either walk or stumble in any of the associated communities.

        This is used when deciding if this candidate can be used for communication, the assumption
        is that if any community is still active, that all will still be active.  The exception to
        this rule is when a node decides to leave one or more communities while remaining active in
        one or more others.
        """
        return any(now < timestamps.last_walk + CANDIDATE_WALK_LIFETIME or now < timestamps.last_stumble + CANDIDATE_STUMBLE_LIFETIME
                   for timestamps
                   in self._timestamps.itervalues())

    def is_all_obsolete(self, now):
        """
        Returns True if SELF exceeded the CANDIDATE_LIFETIME of all the associated communities.
        """
        return all(max(timestamps.last_walk, timestamps.last_stumble, timestamps.last_intro) + CANDIDATE_LIFETIME < now
                   for timestamps
                   in self._timestamps.itervalues())

    def age(self, now):
        """
        Returns the time between NOW and the most recent walk or stumble or any of the associated communities.
        """
        return now - max(max(timestamps.last_walk, timestamps.last_stumble) for timestamps in self._timestamps.itervalues())

    def inactive(self, community, now):
        """
        Called to set SELF to inactive for COMMUNITY.
        """
        timestamps = self._timestamps.get(community.cid)
        if timestamps:
            timestamps.last_walk = now - CANDIDATE_WALK_LIFETIME
            timestamps.last_stumble = now - CANDIDATE_STUMBLE_LIFETIME
            timestamps.last_intro = now - CANDIDATE_INTRO_LIFETIME

    def obsolete(self, community, now):
        """
        Called to set SELF to obsolete for all associated communities.
        """
        timestamps = self._timestamps.get(community.cid)
        if timestamps:
            timestamps.last_walk = now - CANDIDATE_LIFETIME
            timestamps.last_stumble = now - CANDIDATE_LIFETIME
            timestamps.last_intro = now - CANDIDATE_LIFETIME

    def all_inactive(self, now):
        """
        Called to set SELF to inactive (or keep it at OBSOLETE) for all associated communities.

        This is used when a timeout occurs while waiting for an introduction-response.  We choose to
        set all communities to inactive to improve churn handling.  Setting the entire candidate to
        inactive will not remove it and any associated 3-way handshake information.  This is
        retained until the entire candidate becomes obsolete.
        """
        for timestamps in self._timestamps.itervalues():
            timestamps.last_walk = now - CANDIDATE_WALK_LIFETIME
            timestamps.last_stumble = now - CANDIDATE_STUMBLE_LIFETIME
            timestamps.last_intro = now - CANDIDATE_INTRO_LIFETIME

    def is_eligible_for_walk(self, community, now):
        """
        Returns True when the candidate is eligible for taking a step.

        A candidate is eligible when:
        - SELF is either walk, stumble, or intro in COMMUNITY; and
        - the previous step is more than CANDIDATE_ELIGIBLE_DELAY ago.
        """
        timestamps = self._timestamps.get(community.cid)
        if timestamps:
            return (timestamps.last_walk + CANDIDATE_ELIGIBLE_DELAY <= now and
                    (now < timestamps.last_walk + CANDIDATE_WALK_LIFETIME or
                     now < timestamps.last_stumble + CANDIDATE_STUMBLE_LIFETIME or
                     now < timestamps.last_intro + CANDIDATE_INTRO_LIFETIME))
        else:
            return False

    def last_walk(self, community):
        assert community.cid in self._timestamps
        return self._timestamps[community.cid].last_walk

    def last_stumble(self, community):
        assert community.cid in self._timestamps
        return self._timestamps[community.cid].last_stumble

    def last_intro(self, community):
        assert community.cid in self._timestamps
        return self._timestamps[community.cid].last_intro

    def get_category(self, community, now):
        """
        Returns the category (u"walk", u"stumble", u"intro", or u"none") depending on the current
        time NOW.
        """
        assert community.cid in self._timestamps
        timestamps = self._timestamps[community.cid]

        if now < timestamps.last_walk + CANDIDATE_WALK_LIFETIME:
            return u"walk"

        if now < timestamps.last_stumble + CANDIDATE_STUMBLE_LIFETIME:
            return u"stumble"

        if now < timestamps.last_intro + CANDIDATE_INTRO_LIFETIME:
            return u"intro"

        return u"none"

    def walk(self, community, now):
        """
        Called when we are about to send an introduction-request to this candidate.
        """
        self._get_or_create_timestamps(community).last_walk = now

    def stumble(self, community, now):
        """
        Called when we receive an introduction-request from this candidate.
        """
        self._get_or_create_timestamps(community).last_stumble = now

    def intro(self, community, now):
        """
        Called when we receive an introduction-response introducing this candidate.
        """
        self._get_or_create_timestamps(community).last_intro = now

    def update(self, tunnel, lan_address, wan_address, connection_type):
        assert isinstance(tunnel, bool)
        assert is_address(lan_address), lan_address
        assert is_address(wan_address), wan_address
        assert isinstance(connection_type, unicode), type(connection_type)
        assert connection_type in (u"unknown", u"public", "symmetric-NAT"), connection_type
        self._tunnel = tunnel
        self._lan_address = lan_address
        self._wan_address = wan_address
        # someone can also reset from a known connection_type to unknown (i.e. it now believes it is
        # no longer public nor symmetric NAT)
        self._connection_type = u"public" if connection_type == u"unknown" and lan_address == wan_address else connection_type

        if __debug__:
            if not (self.sock_addr == self._lan_address or self.sock_addr == self._wan_address):
                dprint("Either LAN ", self._lan_address, " or the WAN ", self._wan_address, " should be SOCK_ADDR ", self.sock_addr, level="error", stack=True)

    def __str__(self):
        if self._sock_addr == self._lan_address == self._wan_address:
            return "{%s:%d}" % self._lan_address
        elif self._sock_addr in (self._lan_address, self._wan_address):
            return "{%s:%d %s:%d}" % (self._lan_address[0], self._lan_address[1], self._wan_address[0], self._wan_address[1])
        else:
            # should not occur
            return "{%s:%d %s:%d %s:%d}" % (self._sock_addr[0], self._sock_addr[1], self._lan_address[0], self._lan_address[1], self._wan_address[0], self._wan_address[1])

class BootstrapCandidate(WalkCandidate):
    def __init__(self, sock_addr, tunnel):
        super(BootstrapCandidate, self).__init__(sock_addr, tunnel, sock_addr, sock_addr, connection_type=u"public")

    def in_community(self, community, now):
        """
        Bootstrap nodes are, by definition, in every possible community.
        """
        if not community.cid in self._timestamps:
            self._timestamps[community.cid] = self.Timestamps()
        return True

    def is_eligible_for_walk(self, community, now):
        """
        Bootstrap nodes are, by definition, always online, hence the timeouts do not apply.
        """
        assert community.cid in self._timestamps
        timestamps = self._timestamps[community.cid]
        return now >= timestamps.last_walk + CANDIDATE_ELIGIBLE_BOOTSTRAP_DELAY

    def __str__(self):
        return "B!" + super(BootstrapCandidate, self).__str__()

class LoopbackCandidate(Candidate):
    def __init__(self):
        super(LoopbackCandidate, self).__init__(("localhost", 0), False)

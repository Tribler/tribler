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

CANDIDATE_ACTIVE = 0.0
CANDIDATE_INACTIVE = 60.0
CANDIDATE_OBSOLETE = 180.0
assert isinstance(CANDIDATE_ACTIVE, float)
assert isinstance(CANDIDATE_INACTIVE, float)
assert isinstance(CANDIDATE_OBSOLETE, float)
assert CANDIDATE_ACTIVE == 0.0, "assumed to be 0.0, otherwise code below needs modification"
assert CANDIDATE_ACTIVE < CANDIDATE_INACTIVE < CANDIDATE_OBSOLETE

# delay and lifetime values are chosen to ensure that a candidate will not exceed 60.0 or 30.0
# seconds.  However, taking into account round trip time and processing delay we to use smaller
# values without conflicting with the next 5.0 walk cycle.  Hence, we pick 2.5 seconds below the
# actual cutoff point.
CANDIDATE_ELIGIBLE_DELAY = 27.5
CANDIDATE_ELIGIBLE_BOOTSTRAP_DELAY = 57.5
CANDIDATE_WALK_LIFETIME = 57.5
CANDIDATE_STUMBLE_LIFETIME = 57.5
CANDIDATE_INTRO_LIFETIME = 27.5
assert isinstance(CANDIDATE_ELIGIBLE_DELAY, float)
assert isinstance(CANDIDATE_WALK_LIFETIME, float)
assert isinstance(CANDIDATE_STUMBLE_LIFETIME, float)
assert isinstance(CANDIDATE_INTRO_LIFETIME, float)

class Candidate(object):
    """
    A Candidate instance represents a communication endpoint with one or more member/community
    pairs.

    Each Candidate can be in one of three states:

    - ACTIVE: the candidate is returned by yield_all_candidates.  Viable between CANDIDATE_ACTIVE
      and CANDIDATE_INACTIVE seconds after receiving any message.

    - INACTIVE: the candidate is not returned by yield_all_candidates but remains available in case
      the candidate becomes active again.  Viable between CANDIDATE_INACTIVE and CANDIDATE_OBSOLETE
      seconds after receiving any message.

    - OBSOLETE: the candidate is removed upon the next call to yield_all_candidates, information
      regarding this candidate is lost.  I.e. the 3-way handshake will need to be performed again.
      Viable after CANDIDATE_OBSOLETE seconds.

                                    ---------------> obsolete() --------------->
                                   /                                             \
                                  / --> inactive() --> \  / <--- inactive() <---- \
    (initial)                    /                      \/                         \
    OBSOLETE -> active() -> ACTIVE -> time-passes -> INACTIVE -> time-passes -> OBSOLETE
                                \                       /                          /
                                  <---------- active() ----------------------------
    """
    class Timestamps(object):
        def __init__(self):
            self.last_active = 0.0

    def __init__(self, key):
        # key can be anything
        # - for WalkCandidate's it is sock_addr
        self._key = key
        self._associations = set()
        self._timestamps = dict()
        self._global_times = dict()

    @property
    def key(self):
        return self._key

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

    def in_community(self, community, now):
        """
        Returns True if the candidate is not OBSOLETE in COMMUNITY.
        """
        if __debug__:
            from community import Community
            assert isinstance(community, Community)
        timestamps = self._timestamps.get(community.cid)
        if timestamps:
            return now < timestamps.last_active + CANDIDATE_OBSOLETE
        else:
            return False

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

    def is_active(self, community, now):
        """
        Returns True if SELF is active in COMMUNITY.
        """
        if community.cid in self._timestamps:
            return now <= self._timestamps[community.cid].last_active + CANDIDATE_INACTIVE
        return False

    def is_any_active(self, now):
        """
        Returns True if any of the associated communities are still active.

        This is used when deciding if this candidate can be used for communication, the assumption
        is that if any community is still active, that all will still be active.  The exception to
        this rule is when a node decides to leave one or more communities while remaining active in
        one or more others.
        """
        if self._timestamps:
            return now <= max(timestamps.last_active for timestamps in self._timestamps.itervalues()) + CANDIDATE_INACTIVE
        return False

    def is_all_obsolete(self, now):
        """
        Returns True when all the associated communities are obsolete.
        """
        if self._timestamps:
            return max(timestamps.last_active for timestamps in self._timestamps.itervalues()) + CANDIDATE_OBSOLETE < now
        return True

    # def get_state(self, now):
    #     """
    #     Returns the state of this candidate.

    #     - u"active" when NOW <= last-active + CANDIDATE_INACTIVE
    #     - u"inactive" when last-active + CANDIDATE_INACTIVE < NOW <= last-active + CANDIDATE_OBSOLETE
    #     - u"obsolete" when last-active + CANDIDATE_OBSOLETE < NOW

    #     Or u"obsolete" when none of the above applies, i.e. we have not had any activity on this
    #     candidate yet.
    #     """
    #     if self._timestamps:
    #         if now <= max(timestamps.last_active for timestamps in self._timestamps.itervalues()) + CANDIDATE_INACTIVE:
    #             return u"active"

    #         elif max(timestamps.last_active for timestamps in self._timestamps.itervalues()) + CANDIDATE_OBSOLETE < now:
    #             return u"obsolete"

    #         else:
    #             return u"inactive"

    #     return u"obsolete"

    def age(self, now):
        return now - max(timestamps.last_active for timestamps in self._timestamps.itervalues())

    def active(self, community, now):
        """
        Called when we receive any message from this candidate.
        """
        self._get_or_create_timestamps(community).last_active = now

    def inactive(self, community, now):
        """
        Called to explicitly set this candidate to inactive.
        """
        self._get_or_create_timestamps(community).last_active = now - CANDIDATE_INACTIVE

    def obsolete(self, community, now):
        self._get_or_create_timestamps(community).last_active = now - CANDIDATE_OBSOLETE

    def all_inactive(self, now):
        """
        Sets the state to INACTIVE (or keep it at OBSOLETE) for all associated communities.

        This is used when a timeout occurs while waiting for an introduction-response.  We choose to
        set all communities to inactive to improve churn handling.  Setting the entire candidate to
        inactive will not remove it and any associated 3-way handshake information.  This is
        retained until the entire candidate becomes obsolete.
        """
        for timestamps in self._timestamps.itervalues():
            timestamps.last_active = min(now - CANDIDATE_INACTIVE, timestamps.last_active)

class WalkCandidate(Candidate):
    """
    A Candidate representing an IPv4-address endpoint discovered through the Dispersy random walker.

    These candidates are added and removed by the Dispersy random walker.  Each WalkCandidate has
    the following four markers:

    - WALK: we sent an introduction-request.  Viable up to CANDIDATE_WALK_LIFETIME seconds after the
      message was sent.

    - STUMBLE: we received an introduction-request.  Viable up to CANDIDATE_STUMBLE_LIFETIME seconds
      after the message was received.

    - INTRO: we know about this candidate though hearsay.  Viable up to CANDIDATE_INACTIVE seconds
      after the introduction-response message (talking about the candidate) was received.

    Based on these markers the candidate is placed into one specific category:

    - IS_WALK: when the WALK marker is set.

    - IS_STUMBLE: when the STUMBLE marker is set and neither the WALK nor the INTRO marker are set.

    - IS_INTRO: when the INTRO marker is set and neither the WALK nor the STUMBLE marker are set.

    - IS_SANDI: when both the STUMBLE and the INTRO markers are set and the WALK marker is not set.

    - IS_NONE: when neither the WALK nor the STUMBLE nor the INTRO markers are set.
    """
    class Timestamps(object):
        def __init__(self):
            self.last_active = 0.0
            self.last_walk = 0.0
            self.last_stumble = 0.0
            self.last_intro = 0.0

    def __init__(self, sock_addr, lan_address, wan_address, connection_type=u"unknown"):
        super(WalkCandidate, self).__init__(sock_addr)

        assert is_address(sock_addr)
        assert is_address(lan_address)
        assert is_address(wan_address)
        assert isinstance(connection_type, unicode) and connection_type in (u"unknown", u"public", "symmetric-NAT")
        self._lan_address = lan_address
        self._wan_address = wan_address
        self._connection_type = connection_type

    @property
    def sock_addr(self):
        return self._key

    @property
    def lan_address(self):
        return self._lan_address

    @property
    def wan_address(self):
        return self._wan_address

    @property
    def connection_type(self):
        return self._connection_type

    def is_any_active(self, now):
        """
        Returns True if any of the associated communities are still active.

        A WalkCandidate is active if the category is either u"walk", u"stumble", or u"sandi".
        """
        if self._timestamps:
            return (now < max(timestamps.last_walk for timestamps in self._timestamps.itervalues()) + CANDIDATE_WALK_LIFETIME or
                    now < max(timestamps.last_stumble for timestamps in self._timestamps.itervalues()) + CANDIDATE_STUMBLE_LIFETIME)
        return False

    def is_active(self, community, now):
        """
        Returns True if COMMUNITY is still active.
        """
        if community.cid in self._timestamps:
            return (now <= self._timestamps[community.cid].last_walk + CANDIDATE_WALK_LIFETIME or
                    now <= self._timestamps[community.cid].last_stumble + CANDIDATE_STUMBLE_LIFETIME)
        return False

    def inactive(self, community, now):
        """
        Called to explicitly set this candidate to inactive.
        """
        timestamps = self._get_or_create_timestamps(community)
        timestamps.last_active = now - CANDIDATE_INACTIVE
        timestamps.last_walk = now - CANDIDATE_WALK_LIFETIME
        timestamps.last_stumble = now - CANDIDATE_STUMBLE_LIFETIME

    def all_inactive(self, now):
        """
        Sets the state to INACTIVE (or keep it at OBSOLETE) for all associated communities.

        This is used when a timeout occurs while waiting for an introduction-response.  We choose to
        set all communities to inactive to improve churn handling.  Setting the entire candidate to
        inactive will not remove it and any associated 3-way handshake information.  This is
        retained until the entire candidate becomes obsolete.
        """
        for timestamps in self._timestamps.itervalues():
            timestamps.last_active = min(now - CANDIDATE_INACTIVE, timestamps.last_active)
            timestamps.last_walk = min(now - CANDIDATE_WALK_LIFETIME, timestamps.last_walk)
            timestamps.last_stumble = min(now - CANDIDATE_STUMBLE_LIFETIME, timestamps.last_stumble)

    def is_eligible_for_walk(self, community, now):
        """
        Returns True when the candidate is eligible for taking a step.

        A candidate is eligible when all below is True:
        - the category is WALK, STUMBLE, INTRO, or SANDI.
        - it is CANDIDATE_ELIGIBLE_DELAY or more seconds since the previous step.
        """
        assert community.cid in self._timestamps
        timestamps = self._timestamps[community.cid]
        return (now >= timestamps.last_walk + CANDIDATE_ELIGIBLE_DELAY and
                (now < timestamps.last_walk + CANDIDATE_WALK_LIFETIME or
                 now < timestamps.last_stumble + CANDIDATE_STUMBLE_LIFETIME or
                 now < timestamps.last_intro + CANDIDATE_INTRO_LIFETIME))

    def last_walk(self, community):
        assert community.cid in self._timestamps
        return self._timestamps[community.cid].last_walk

    def last_stumble(self, community):
        assert community.cid in self._timestamps
        return self._timestamps[community.cid].last_stumble

    def last_intro(self, community):
        assert community.cid in self._timestamps
        return self._timestamps[community.cid].last_intro

    def last_sandi(self, community):
        assert community.cid in self._timestamps
        return self._timestamps[community.cid].last_sandi

    def get_category(self, community, now):
        """
        Returns the category (u"walk", u"stumble", u"intro", u"sandi", or u"none") depending on the
        current time NOW.
        """
        assert community.cid in self._timestamps
        timestamps = self._timestamps[community.cid]

        if now < timestamps.last_walk + CANDIDATE_WALK_LIFETIME:
            return u"walk"

        if now < timestamps.last_stumble + CANDIDATE_STUMBLE_LIFETIME and now >= timestamps.last_intro + CANDIDATE_INTRO_LIFETIME:
            return u"stumble"

        if now < timestamps.last_intro + CANDIDATE_INTRO_LIFETIME and now >= timestamps.last_stumble + CANDIDATE_STUMBLE_LIFETIME:
            return u"intro"

        if now < timestamps.last_stumble + CANDIDATE_STUMBLE_LIFETIME and now < timestamps.last_intro + CANDIDATE_INTRO_LIFETIME:
            return u"sandi"

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

    def update(self, lan_address, wan_address, connection_type):
        assert is_address(lan_address)
        assert is_address(wan_address)
        assert isinstance(connection_type, unicode) and connection_type in (u"unknown", u"public", "symmetric-NAT")
        self._lan_address = lan_address
        self._wan_address = wan_address
        self._connection_type = u"public" if connection_type == u"unknown" and lan_address == wan_address else connection_type

    def __str__(self):
        if self._lan_address == self._wan_address:
            return "%s:%d" % self._lan_address

        else:
            return "%s:%d (%s:%d)" % (self._lan_address[0], self._lan_address[1], self._wan_address[0], self._wan_address[1])

class BootstrapCandidate(WalkCandidate):
    def __init__(self, sock_addr):
        super(BootstrapCandidate, self).__init__(sock_addr, sock_addr, sock_addr, connection_type=u"public")

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
        super(LoopbackCandidate, self).__init__(u"loopback")

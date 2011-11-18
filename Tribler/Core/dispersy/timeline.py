"""
The Timeline is an important part of Dispersy.  The Timeline can be
queried as to who had what actions at some point in time.
"""

from itertools import count, groupby

from authentication import MemberAuthentication, MultiMemberAuthentication
from resolution import PublicResolution, LinearResolution, DynamicResolution

if __debug__:
    from dprint import dprint

class Timeline(object):
    def __init__(self, community):
        if __debug__:
            from community import Community
            assert isinstance(community, Community)

        # the community that this timeline is keeping track off
        self._community = community

        # _members contains the permission grants and revokes per member
        # Member / [(global_time, {u'permission^message-name':(True/False, [Message.Implementation])})]
        self._members = {}

        # _policies contains the policies that the community is currently using (dynamic settings)
        # [(global_time, {u'resolution^message-name':(resolution-policy, [Message.Implementation])})]
        self._policies = []

    if __debug__:
        def printer(self):
            for global_time, dic in self._policies:
                dprint("policy @", global_time)
                for key, (policy, proofs) in dic.iteritems():
                    dprint("policy ", "%50s" % key, "  ", policy, " based on ", len(proofs), " proofs")

            for member, lst in self._members.iteritems():
                dprint("member ", member.database_id, " ", member.mid.encode("HEX"))
                for global_time, dic in lst:
                    dprint("member ", member.database_id, " @", global_time)
                    for key, (allowed, proofs) in dic.iteritems():
                        if allowed:
                            assert all(proof.name == u"dispersy-authorize" for proof in proofs)
                            dprint("member ", member.database_id, " ", "%50s" % key, "  ", allowed, " granted by ", ", ".join(str(proof.authentication.member.database_id) for proof in proofs), " in ", ", ".join(str(proof.packet_id) for proof in proofs))
                        else:
                            assert all(proof.name == u"dispersy-revoke" for proof in proofs)
                            dprint("member ", member.database_id, " ", "%50s" % key, "  ", allowed, " revoked by ", ", ".join(str(proof.authentication.member.database_id) for proof in proofs), " in ", ", ".join(str(proof.packet_id) for proof in proofs))

    def check(self, message, permission=u"permit"):
        """
        Check if message is allowed.

        Returns an (allowed, proofs) tuple where allowed is either True or False and proofs is a
        list containing zero or more Message.Implementation instances that grant or revoke
        permissions.
        """
        if __debug__:
            from message import Message
        assert isinstance(message, Message.Implementation), message
        assert isinstance(message.authentication, (MemberAuthentication.Implementation, MultiMemberAuthentication.Implementation)), message.authentication
        assert isinstance(permission, unicode)
        assert permission in (u'permit', u'authorize', u'revoke')
        if isinstance(message.authentication, MemberAuthentication.Implementation):
            # MemberAuthentication

            if message.name == u"dispersy-authorize" or message.name == u"dispersy-revoke":
                if __debug__:
                    dprint("collecting proof for container message ", message.name)
                    self.printer()

                # if one or more of the contained permission_triplets are allowed, we will allow the
                # entire message.  when the message is processed only the permission_triplets that
                # are still valid will be used
                all_allowed = []
                all_proofs = set()

                # question: is message.authentication.member allowed to authorize or revoke one or
                # more of the contained permission triplets?

                # proofs for the permission triplets in the payload
                key = lambda (member, sub_message, _): sub_message
                for sub_message, iterator in groupby(message.payload.permission_triplets, key=key):
                    permission_pairs = [(sub_message, sub_permission) for _, _, sub_permission in iterator]
                    allowed, proofs = self._check(message.authentication.member, message.distribution.global_time, sub_message.resolution, permission_pairs)
                    all_allowed.append(allowed)
                    all_proofs.update(proofs)
                if __debug__: dprint("is one or more permission triplets allowed? ", any(all_allowed), ".  based on ", len(all_proofs), " proofs")

                return any(all_allowed), [proof for proof in all_proofs]

            else:
                return self._check(message.authentication.member, message.distribution.global_time, message.resolution, [(message.meta, permission)])
        else:
            # MultiMemberAuthentication
            all_proofs = set()
            for member in message.authentication.members:
                allowed, proofs = self._check(member, message.distribution.global_time, message.resolution, [(message.meta, permission)])
                all_proofs.update(proofs)
                if not allowed:
                    return (False, [proof for proof in all_proofs])
            return (True, [proof for proof in all_proofs])

    def allowed(self, meta, global_time=0, permission=u"permit"):
        """
        Check if we are allowed to create a message.
        """
        if __debug__:
            from message import Message
        assert isinstance(meta, Message)
        assert isinstance(global_time, (int, long))
        assert global_time >= 0
        assert isinstance(permission, unicode)
        assert permission in (u'permit', u'authorize', u'revoke')
        return self._check(self._community.my_member, global_time if global_time else self._community.global_time, meta.resolution, [(meta, permission)])

    def _check(self, member, global_time, resolution, permission_pairs):
        """
        Check is MEMBER has all of the permission pairs in PERMISSION_PAIRS at GLOBAL_TIME.

        Returns a (allowed, proofs) tuple where allowed is either True or False and proofs is a list
        containing the Message.Implementation instances grant or revoke the permissions.
        """
        if __debug__:
            from member import Member
            from message import Message
            assert isinstance(member, Member)
            assert isinstance(global_time, (int, long))
            assert global_time > 0
            assert isinstance(permission_pairs, list)
            assert len(permission_pairs) > 0
            for pair in permission_pairs:
                assert isinstance(pair, tuple)
                assert len(pair) == 2
                assert isinstance(pair[0], Message), "Requires meta message"
                assert isinstance(pair[1], unicode)
                assert pair[1] in (u'permit', u'authorize', u'revoke')
            assert isinstance(resolution, (PublicResolution.Implementation, LinearResolution.Implementation, DynamicResolution.Implementation, PublicResolution, LinearResolution, DynamicResolution)), resolution

        # TODO: we can make this more efficient by changing the loop a bit.  make a shallow copy of
        # the permission_pairs and remove one after another as they succeed.  key is to loop though
        # the self._members[member] once (currently looping over the timeline for every item in
        # permission_pairs).

        all_proofs = []

        for message, permission in permission_pairs:
            # the master member can do anything
            if member == self._community.master_member:
                if __debug__: dprint("ACCEPT time:", global_time, " user:", member.database_id, " -> ", permission, "^", message.name, " (master member)")

            else:
                # dynamically set the resolution policy
                if isinstance(resolution, DynamicResolution):
                    resolution, proofs = self.get_resolution_policy(message, global_time)
                    assert isinstance(resolution, (PublicResolution, LinearResolution))
                    all_proofs.extend(proofs)

                elif isinstance(resolution, DynamicResolution.Implementation):
                    local_resolution, proofs = self.get_resolution_policy(message, global_time)
                    assert isinstance(local_resolution, (PublicResolution, LinearResolution))
                    all_proofs.extend(proofs)

                    if not resolution.policy.meta == local_resolution:
                        if __debug__: dprint("FAIL time:", global_time, " user:", member.database_id, " (conflicting resolution policy, ", resolution.policy.meta, ", ", local_resolution, ")")
                        return (False, all_proofs)

                    resolution = resolution.policy
                    if __debug__: dprint("APPLY time:", global_time, " resolution^", message.name, " -> ", resolution.__class__.__name__)

                # everyone is allowed PublicResolution
                if isinstance(resolution, (PublicResolution, PublicResolution.Implementation)):
                    if __debug__: dprint("ACCEPT time:", global_time, " user:", member.database_id, " -> ", permission, "^", message.name, " (public resolution)")

                # allowed LinearResolution is stored in Timeline
                elif isinstance(resolution, (LinearResolution, LinearResolution.Implementation)):
                    key = permission + "^" + message.name

                    if member in self._members:
                        iterator = reversed(self._members[member])
                        try:
                            # go backwards while time > global_time
                            while True:
                                time, permissions = iterator.next()
                                if time <= global_time:
                                    break

                            # check permissions and continue backwards in time
                            while True:
                                if key in permissions:
                                    assert isinstance(permissions[key], tuple)
                                    assert len(permissions[key]) == 2
                                    assert isinstance(permissions[key][0], bool)
                                    assert isinstance(permissions[key][1], list)
                                    assert len(permissions[key][1]) > 0
                                    assert not filter(lambda x: not isinstance(x, Message.Implementation), permissions[key][1])
                                    allowed, proofs = permissions[key]

                                    if allowed:
                                        if __debug__: dprint("ACCEPT time:", global_time, " user:", member.database_id, " -> ", key, " (authorized)")
                                        all_proofs.extend(proofs)
                                        break
                                    else:
                                        if __debug__: dprint("DENIED time:", global_time, " user:", member.database_id, " -> ", key, " (revoked)", level="warning")
                                        return (False, [proofs])

                                time, permissions = iterator.next()

                        except StopIteration:
                            if __debug__: dprint("FAIL time:", global_time, " user:", member.database_id, " -> ", key, " (not authorized)", level="warning")
                            return (False, [])
                    else:
                        if __debug__: dprint("FAIL time:", global_time, " user:", member.database_id, " -> ", key, " (no authorization)", level="warning")
                        return (False, [])

                    # accept with proof
                    assert len(all_proofs) > 0

                else:
                    raise NotImplementedError("Unknown Resolution")

        return (True, all_proofs)

    def authorize(self, author, global_time, permission_triplets, proof):
        if __debug__:
            from authentication import MemberAuthentication
            from member import Member
            from message import Message
            assert isinstance(author, Member)
            assert isinstance(global_time, (int, long))
            assert global_time > 0
            assert isinstance(permission_triplets, list)
            assert len(permission_triplets) > 0
            for triplet in permission_triplets:
                assert isinstance(triplet, tuple)
                assert len(triplet) == 3
                assert isinstance(triplet[0], Member)
                assert isinstance(triplet[1], Message)
                assert isinstance(triplet[1].resolution, (LinearResolution, DynamicResolution))
                assert isinstance(triplet[1].authentication, MemberAuthentication)
                assert isinstance(triplet[2], unicode)
                assert triplet[2] in (u'permit', u'authorize', u'revoke')
            assert isinstance(proof, Message.Implementation)

        # TODO: we must remove duplicates in the below permission_pairs list
        # check that AUTHOR is allowed to perform these authorizations
        authorize_allowed, authorize_proofs = self._check(author, global_time, LinearResolution(), [(message, u"authorize") for _, message, __ in permission_triplets])
        if not authorize_allowed:
            if __debug__:
                dprint("the author is NOT allowed to perform authorizations for one or more of the given permission triplets")
                dprint("-- the author is... master member? ", author == self._community.master_member, "; my member? ", author == self._community.my_member)
            return (False, authorize_proofs)

        for member, message, permission in permission_triplets:
            if isinstance(message.resolution, (LinearResolution, DynamicResolution)):
                if not member in self._members:
                    self._members[member] = []

                key = permission + "^" + message.name

                for index, (time, permissions) in zip(count(0), self._members[member]):
                    # extend when time == global_time
                    if time == global_time:
                        if key in permissions:
                            allowed, proofs = permissions[key]
                            if allowed:
                                # multiple proofs for the same permissions at this exact time
                                if __debug__: dprint("AUTHORIZE time:", global_time, " user:", member.database_id, " -> ", key, " (extending duplicate)")
                                proofs.append(proof)

                            else:
                                # TODO: when two authorize contradict each other on the same global
                                # time, the ordering of the packet will decide the outcome.  we need
                                # those packets!  [SELECT packet FROM sync WHERE ...]
                                raise NotImplementedError("Requires ordering by packet to resolve permission conflict")

                        else:
                            # no earlier proof on this global time
                            if __debug__: dprint("AUTHORIZE time:", global_time, " user:", member.database_id, " -> ", key, " (extending)")
                            permissions[key] = (True, [proof])
                        break

                    # insert when time > global_time
                    elif time > global_time:
                        # TODO: ensure that INDEX is correct!
                        if __debug__: dprint("AUTHORIZE time:", global_time, " user:", member.database_id, " -> ", key, " (inserting)")
                        self._members[member].insert(index, (global_time, {key:(True, [proof])}))
                        break

                    # otherwise: go forward while time < global_time

                else:
                    # we have reached the end without a BREAK: append the permission
                    if __debug__: dprint("AUTHORIZE time:", global_time, " user:", member.database_id, " -> ", key, " (appending)")
                    self._members[member].append((global_time, {key:(True, [proof])}))

            else:
                raise NotImplementedError(message.resolution)

        return (True, authorize_proofs)

    def revoke(self, author, global_time, permission_triplets, proof):
        if __debug__:
            from authentication import MemberAuthentication
            from member import Member
            from message import Message
            assert isinstance(author, Member)
            assert isinstance(global_time, (int, long))
            assert global_time > 0
            assert isinstance(permission_triplets, list)
            assert len(permission_triplets) > 0
            for triplet in permission_triplets:
                assert isinstance(triplet, tuple)
                assert len(triplet) == 3
                assert isinstance(triplet[0], Member)
                assert isinstance(triplet[1], Message)
                assert isinstance(triplet[1].resolution, (LinearResolution, DynamicResolution))
                assert isinstance(triplet[1].authentication, MemberAuthentication)
                assert isinstance(triplet[2], unicode)
                assert triplet[2] in (u'permit', u'authorize', u'revoke')
            assert isinstance(proof, Message.Implementation)

        # TODO: we must remove duplicates in the below permission_pairs list
        # check that AUTHOR is allowed to perform these authorizations
        revoke_allowed, revoke_proofs = self._check(author, global_time, LinearResolution(), [(message, u"revoke") for _, message, __ in permission_triplets])
        if not revoke_allowed:
            if __debug__: dprint("the author is NOT allowed to perform authorizations for one or more of the given permission triplets")
            return (False, revoke_proofs)

        for member, message, permission in permission_triplets:
            if isinstance(message.resolution, (LinearResolution, DynamicResolution)):
                if not member in self._members:
                    self._members[member] = []

                key = permission + "^" + message.name

                for index, (time, permissions) in zip(count(0), self._members[member]):
                    # extend when time == global_time
                    if time == global_time:
                        if key in permissions:
                            allowed, proofs = permissions[key]
                            if allowed:
                                # TODO: when two authorize contradict each other on the same global
                                # time, the ordering of the packet will decide the outcome.  we need
                                # those packets!  [SELECT packet FROM sync WHERE ...]
                                raise NotImplementedError("Requires ordering by packet to resolve permission conflict")

                            else:
                                # multiple proofs for the same permissions at this exact time
                                if __debug__: dprint("REVOKE time:", global_time, " user:", member.database_id, " -> ", key, " (extending duplicate)")
                                proofs.append(proof)

                        else:
                            # no earlier proof on this global time
                            if __debug__: dprint("REVOKE time:", global_time, " user:", member.database_id, " -> ", key, " (extending)")
                            permissions[key] = (False, [proof])
                        break

                    # insert when time > global_time
                    elif time > global_time:
                        # TODO: ensure that INDEX is correct!
                        if __debug__: dprint("REVOKE time:", global_time, " user:", member.database_id, " -> ", key, " (inserting)")
                        self._members[member].insert(index, (global_time, {key:(False, [proof])}))
                        break

                    # otherwise: go forward while time < global_time

                else:
                    # we have reached the end without a BREAK: append the permission
                    if __debug__: dprint("REVOKE time:", global_time, " user:", member.database_id, " -> ", key, " (appending)")
                    self._members[member].append((global_time, {key:(False, [proof])}))

            else:
                raise NotImplementedError(message.resolution)

        return (True, revoke_proofs)

    def get_resolution_policy(self, message, global_time):
        """
        Returns the resolution policy and associated proof that is used for MESSAGE at time
        GLOBAL_TIME.
        """
        if __debug__:
            from message import Message
        assert isinstance(message, Message)
        assert isinstance(global_time, (int, long))

        key = u"resolution^" + message.name
        for policy_time, policies in reversed(self._policies):
            if policy_time < global_time and key in policies:
                if __debug__: dprint("using ", policies[key][0].__class__.__name__, " for time ", global_time, " (configured at ", policy_time, ")")
                return policies[key]

        if __debug__: dprint("using ", message.resolution.default.__class__.__name__, " for time ", global_time, " (default)")
        return message.resolution.default, []

    def change_resolution_policy(self, message, global_time, policy, proof):
        if __debug__:
            from message import Message
        assert isinstance(message, Message)
        assert isinstance(global_time, (int, long))
        assert isinstance(policy, (PublicResolution, LinearResolution))
        assert isinstance(proof, Message.Implementation)

        for policy_time, policies in reversed(self._policies):
            if policy_time == global_time:
                if __debug__: dprint("extending")
                break
        else:
            if __debug__: dprint("creating")
            policies = {}
            self._policies.append((global_time, policies))
            self._policies.sort()

        # TODO it is possible that different members set different policies at the same time
        policies[u"resolution^" + message.name] = (policy, [proof])
        if __debug__: dprint(self._policies, lines=1)

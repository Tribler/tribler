"""
The Timeline is an important part of Dispersy.  The Timeline can be
queried as to who had what actions at some point in time.
"""

from itertools import count

from authentication import MemberAuthentication, MultiMemberAuthentication
from member import Member, MasterMember
from resolution import PublicResolution, LinearResolution

if __debug__:
    from dprint import dprint

class Timeline(object):
    class Node(object):
        def __init__(self):
            self.timeline = [] # (global_time, {u'permission^message-name':(True/False, [Message.Implementation])})

    def __init__(self):
        self._nodes = {}

    def check(self, message, permission=u"permit"):
        """
        Check if message is allowed.
        """
        if __debug__:
            from message import Message
        assert isinstance(message, Message.Implementation), message
        assert isinstance(message.authentication, (MemberAuthentication.Implementation, MultiMemberAuthentication.Implementation)), message.authentication
        assert isinstance(permission, unicode)
        assert permission in (u'permit', u'authorize', u'revoke')
        if isinstance(message.authentication, MemberAuthentication.Implementation):
            # MemberAuthentication
            return self._check(message.authentication.member, message.distribution.global_time, [(message.meta, permission)])
        else:
            # MultiMemberAuthentication
            all_proofs = []
            for member in  message.authentication.members:
                allowed, proofs = self._check(member, message.distribution.global_time, [(message.meta, permission)])
                all_proofs.extend(proofs)
                if not allowed:
                    return (False, all_proofs)
            return (True, all_proofs)

    def _check(self, member, global_time, permission_pairs):
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

        # TODO: we can make this more efficient by changing the loop a bit.  make a shallow copy of
        # the permission_pairs and remove one after another as they succeed.  key is to loop though
        # the self._nodes[member].timeline once (currently looping over the timeline for every item
        # in permission_pairs).

        all_proofs = []

        for message, permission in permission_pairs:
            # everyone is allowed PublicResolution
            if isinstance(message.resolution, PublicResolution):
                if __debug__: dprint("ACCEPT time:", global_time, " user:", member.database_id, " -> ", permission, "^", message.name, " (public resolution)")

            # the MasterMember can do anything
            elif isinstance(member, MasterMember):
                if __debug__: dprint("ACCEPT time:", global_time, " user:", member.database_id, " -> ", permission, "^", message.name, " (master member)")

            # allowed LinearResolution is stored in Timeline
            elif isinstance(message.resolution, LinearResolution):
                key = permission + "^" + message.name

                if member in self._nodes:
                    iterator = reversed(self._nodes[member].timeline)
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
            
                if __debug__: dprint("ACCEPT time:", global_time, " user:", member.database_id, " -> ", permission, "^", message.name, " (see above)")
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
                assert isinstance(triplet[1].resolution, LinearResolution)
                assert isinstance(triplet[1].authentication, MemberAuthentication)
                assert isinstance(triplet[2], unicode)
                assert triplet[2] in (u'permit', u'authorize', u'revoke')
            assert isinstance(proof, Message.Implementation)

        # TODO: we must remove duplicates in the below permission_pairs list
        # check that AUTHOR is allowed to perform these authorizations
        authorize_allowed, authorize_proofs = self._check(author, global_time, [(message, u"authorize") for _, message, __ in permission_triplets])
        if not authorize_allowed:
            if __debug__: dprint("the author is NOT allowed to perform authorizations for one or more of the given permission triplets")
            return (False, authorize_proofs)

        for member, message, permission in permission_triplets:
            if isinstance(message.resolution, LinearResolution):
                if not member in self._nodes:
                    self._nodes[member] = self.Node()

                key = permission + "^" + message.name

                for index, (time, permissions) in zip(count(0), self._nodes[member].timeline):
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
                        self._nodes[member].timeline.insert(index, (global_time, {key:(True, [proof])}))
                        break

                    # otherwise: go forward while time < global_time

                else:
                    # we have reached the end without a BREAK: append the permission
                    if __debug__: dprint("AUTHORIZE time:", global_time, " user:", member.database_id, " -> ", key, " (appending)")
                    self._nodes[member].timeline.append((global_time, {key:(True, [proof])}))

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
                assert isinstance(triplet[1].resolution, LinearResolution)
                assert isinstance(triplet[1].authentication, MemberAuthentication)
                assert isinstance(triplet[2], unicode)
                assert triplet[2] in (u'permit', u'authorize', u'revoke')
            assert isinstance(proof, Message.Implementation)

        # TODO: we must remove duplicates in the below permission_pairs list
        # check that AUTHOR is allowed to perform these authorizations
        revoke_allowed, revoke_proofs = self._check(author, global_time, [(message, u"revoke") for _, message, __ in permission_triplets])
        if not revoke_allowed:
            if __debug__: dprint("the author is NOT allowed to perform authorizations for one or more of the given permission triplets")
            return (False, revoke_proofs)

        for member, message, permission in permission_triplets:
            if isinstance(message.resolution, LinearResolution):
                if not member in self._nodes:
                    self._nodes[member] = self.Node()

                key = permission + "^" + message.name

                for index, (time, permissions) in zip(count(0), self._nodes[member].timeline):
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
                        self._nodes[member].timeline.insert(index, (global_time, {key:(False, [proof])}))
                        break

                    # otherwise: go forward while time < global_time

                else:
                    # we have reached the end without a BREAK: append the permission
                    if __debug__: dprint("REVOKE time:", global_time, " user:", member.database_id, " -> ", key, " (appending)")
                    self._nodes[member].timeline.append((global_time, {key:(False, [proof])}))

            else:
                raise NotImplementedError(message.resolution)

        return (True, revoke_proofs)

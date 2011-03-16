"""
The Timeline is an important part of Dispersy.  The Timeline can be
queried as to who had what actions at some point in time.
"""

from itertools import count

from member import Member, MasterMember
from resolution import PublicResolution, LinearResolution

if __debug__:
    from dprint import dprint

class Timeline(object):
    class Node(object):
        def __init__(self):
            self.timeline = [] # (global_time, {u'permission^message-name':True|False})

    def __init__(self, community):
        self._global_time = 1
        self._nodes = {}

    @property
    def global_time(self):
        return self._global_time

    def claim_global_time(self):
        self._global_time += 1
        return self._global_time

    def check(self, message, permission=u"permit"):
        """
        Check if message is allowed.
        """
        if __debug__:
            from message import Message
            from authentication import MemberAuthentication
        assert isinstance(message, Message.Implementation), message
        assert isinstance(message.authentication, MemberAuthentication.Implementation), message.authentication
        assert isinstance(permission, unicode)
        assert permission in (u'permit', u'authorize', u'revoke')

        if self._check(message.authentication.member, message.distribution.global_time, [(message.meta, permission)]):
            self._global_time = max(self._global_time, message.distribution.global_time + 1)
            return True

        else:
            return False

    def _check(self, member, global_time, permission_pairs):
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
                                assert isinstance(permissions[key], bool)
                                if permissions[key]:
                                    if __debug__: dprint("ACCEPT time:", global_time, " user:", member.database_id, " -> ", key, " (authorized)")
                                    break
                                else:
                                    if __debug__: dprint("DENIED time:", global_time, " user:", member.database_id, " -> ", key, " (revoked)", level="warning")
                                    return False

                            time, permissions = iterator.next()

                    except StopIteration():
                        if __debug__: dprint("FAIL time:", global_time, " user:", member.database_id, " -> ", key, " (not authorized)", level="warning")
                        return False

            else:
                raise NotImplementedError("Unknown Resolution")

        return True

    def authorize(self, author, global_time, permission_triplets):
        if __debug__:
            from authentication import MemberAuthentication
            from member import Member, Private
            from message import Message
            assert isinstance(author, Private)
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

        # TODO: we must remove duplicates in the below permission_pairs list
        # check that AUTHOR is allowed to perform these authorizations
        if not self._check(author, global_time, [(message, u"authorize") for _, message, __ in permission_triplets]):
            if __debug__: dprint("the author is NOT allowed to perform authorizations for one or more of the given permission triplets")
            return False

        for member, message, permission in permission_triplets:
            if isinstance(message.resolution, LinearResolution):
                if not member in self._nodes:
                    self._nodes[member] = self.Node()

                key = permission + "^" + message.name

                for index, (time, permissions) in zip(count(0), self._nodes[member].timeline):
                    # extend when time == global_time
                    if time == global_time:
                        if key in permissions and permissions[key] == False:
                            # TODO: when two authorize contradict each other on the same global
                            # time, the ordering of the packet will decide the outcome.  we need
                            # those packets!  [SELECT packet FROM sync WHERE ...]
                            raise NotImplementedError("Requires ordering by packet to resolve permission conflict")
                        if __debug__: dprint("AUTHORIZE time:", global_time, " user:", member.database_id, " -> ", key, " (extending)")
                        permissions[key] = True
                        break

                    # insert when time > global_time
                    elif time > global_time:
                        # TODO: ensure that INDEX is correct!
                        if __debug__: dprint("AUTHORIZE time:", global_time, " user:", member.database_id, " -> ", key, " (inserting)")
                        self._nodes[member].timeline.insert(index, (global_time, {key:True}))
                        break

                    # otherwise: go forward while time < global_time

                else:
                    # we have reached the end without a BREAK: append the permission
                    if __debug__: dprint("AUTHORIZE time:", global_time, " user:", member.database_id, " -> ", key, " (appending)")
                    self._nodes[member].timeline.append((global_time, {key:True}))

            else:
                raise NotImplementedError(message.resolution)

        return True

    def revoke(self, author, global_time, permission_triplets):
        if __debug__:
            from authentication import MemberAuthentication
            from member import Member, Private
            from message import Message
            assert isinstance(author, Private)
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

        # TODO: we must remove duplicates in the below permission_pairs list
        # check that AUTHOR is allowed to perform these authorizations
        if not self._check(author, global_time, [(message, u"revoke") for _, message, __ in permission_triplets]):
            if __debug__: dprint("the author is NOT allowed to perform authorizations for one or more of the given permission triplets")
            return False

        for member, message, permission in permission_triplets:
            if isinstance(message.resolution, LinearResolution):
                if not member in self._nodes:
                    self._nodes[member] = self.Node()

                key = permission + "^" + message.name

                for index, (time, permissions) in zip(count(0), self._nodes[member].timeline):
                    # extend when time == global_time
                    if time == global_time:
                        if key in permissions and permissions[key] == True:
                            # TODO: when two authorize contradict each other on the same global
                            # time, the ordering of the packet will decide the outcome.  we need
                            # those packets!  [SELECT packet FROM sync WHERE ...]
                            raise NotImplementedError("Requires ordering by packet to resolve permission conflict")
                        if __debug__: dprint("REVOKE time:", global_time, " user:", member.database_id, " -> ", key, " (extending)")
                        permissions[key] = False
                        break

                    # insert when time > global_time
                    elif time > global_time:
                        # TODO: ensure that INDEX is correct!
                        if __debug__: dprint("REVOKE time:", global_time, " user:", member.database_id, " -> ", key, " (inserting)")
                        self._nodes[member].timeline.insert(index, (global_time, {key:False}))
                        break

                    # otherwise: go forward while time < global_time

                else:
                    # we have reached the end without a BREAK: append the permission
                    if __debug__: dprint("REVOKE time:", global_time, " user:", member.database_id, " -> ", key, " (appending)")
                    self._nodes[member].timeline.append((global_time, {key:False}))

            else:
                raise NotImplementedError(message.resolution)

        return True

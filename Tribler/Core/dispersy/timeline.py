"""
The Timeline is an important part of Dispersy.  The Timeline can be
queried as to who had what actions at some point in time.
"""

from member import Member, MasterMember
from resolution import PublicResolution, LinearResolution

if __debug__:
    from dprint import dprint

class Timeline(object):
    class Node(object):
        def __init__(self):
            self.timeline = [] # (global_time, [actions])

        def get_actions(self, global_time):
            assert isinstance(global_time, (int, long))
            for time, allowed_actions in reversed(self.timeline):
                if global_time >= time:
                    return time, allowed_actions
            return -1, []

        def __str__(self):
            def time_pair((global_time, actions)):
                return "%d=[%s]" % (global_time, ",".join(["%s:%s" % (time, allowed_actions) for time, allowed_actions in actions]))
            return "<Node " + ", ".join(map(time_pair, reversed(self.timeline))) + ">"

    def __init__(self, community):
        self._global_time = 1
        self._nodes = {}

    def __str__(self):
        def node_pair((hash, node)):
            return "HASH: " + str(node)
        return "\n".join(map(node_pair, self._nodes.iteritems()))

    @property
    def global_time(self):
        return self._global_time

    def claim_global_time(self):
        try:
            return self._global_time
        finally:
            self._global_time += 1

    def check(self, message):
        """
        Check if message is allowed.
        """
        if __debug__:
            from message import Message
        assert isinstance(message, Message.Implementation), message

        # everyone is allowed PublicResolution
        if isinstance(message.resolution, PublicResolution):
            self._global_time = max(self._global_time, message.distribution.global_time + 1)
            return True

        # the MasterMember can do anything
        if isinstance(message.authentication.member, MasterMember):
            self._global_time = max(self._global_time, message.distribution.global_time + 1)
            return True

        # allowed LinearResolution is stored in Timeline
        elif isinstance(message.resolution, LinearResolution):
            node = self._get_node(message.authentication.member, False)
            if node:
                pair = u"permit^{0.name}".format(message)
                _, allowed_actions = node.get_actions(message.distribution.global_time)
                if pair in allowed_actions:
                    self._global_time = max(self._global_time, message.distribution.global_time + 1)
                    return True

        else:
            raise NotImplementedError("Unknown Resolution")

        if __debug__: dprint("FAIL: Check ", message.authentication.member.database_id, "; ", message.name, "@", message.distribution.global_time, level="warning")
        return False

    def authorize(self, author, global_time, permission_triplets):
        if __debug__:
            from member import Member
            from message import Message
            for triplet in permission_triplets:
                assert isinstance(triplet, tuple)
                assert len(triplet) == 3
                assert isinstance(triplet[0], Member)
                assert isinstance(triplet[1], Message)
                assert isinstance(triplet[2], unicode)
                assert triplet[2] in (u'permit', u'authorize', u'revoke')

        for member, message, permission in permission_triplets:
            if isinstance(message.resolution, LinearResolution):
                node = self._get_node(member, True)
                time, allowed_actions = node.get_actions(global_time + 1)
                pair = u"{0}^{1.name}".format(permission, message)

                if not pair in allowed_actions:
                    if time == global_time + 1:
                        allowed_actions.append(pair)
                    else:
                        node.timeline.append((global_time + 1, allowed_actions + [pair]))

                if __debug__: dprint(["time:{0} -> {1}".format(time, ", ".join(pair)) for time, pair in node.timeline], lines=1)

            else:
                raise NotImplementedError(message.resolution)

        return True

    def _get_node(self, signed_by, create_new):
        """
        Get a Node from a signed_by.public_key.
        """
        isinstance(signed_by, Member)
        isinstance(create_new, bool)
        public_key = signed_by.public_key
        if create_new and not public_key in self._nodes:
            self._nodes[public_key] = self.Node()
        return self._nodes.get(public_key, None)


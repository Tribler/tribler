import hashlib

from community import DiscoveryCommunity
from database import DiscoveryDatabase
from payload import UserMetadataPayload, CommunityMetadataPayload

from Tribler.Core.dispersy.crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin
from Tribler.Core.dispersy.member import Member, MyMember
from Tribler.Core.dispersy.script import ScriptBase
from Tribler.Core.dispersy.debug import Node
from Tribler.Core.dispersy.dprint import dprint

class DiscoveryNode(Node):
    def create_community_metadata_message(self, cid, alias, comment, global_time, sequence_number):
        meta = self._community.get_meta_message(u"community-metadata")
        return meta.implement(meta.authentication.implement(self._my_member),
                              meta.distribution.implement(global_time, sequence_number),
                              meta.destination.implement(),
                              meta.payload.implement(cid, alias, comment))

    def create_user_metadata_message(self, address, alias, comment, global_time):
        meta = self._community.get_meta_message(u"user-metadata")
        return meta.implement(meta.authentication.implement(self._my_member),
                              meta.distribution.implement(global_time),
                              meta.destination.implement(),
                              meta.payload.implement(address, alias, comment))

class DiscoveryCommunityScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        master_key = ec_to_public_bin(ec)

        ec = ec_generate_key(u"low")
        self._my_member = MyMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)
        self._discovery = DiscoveryCommunity.join_community(master_key, self._my_member)
        self._discovery_database = DiscoveryDatabase.get_instance()

        self.caller(self.my_community_metadata)
        self.caller(self.food)
        self.caller(self.drink)
        self.caller(self.drinks)

    def my_community_metadata(self):
        """
        SELF creates a few communities and these need to end up in the
        discovery database.
        """
        cid, alias, comment = (hashlib.sha1("MY-FIRST-COMMUNITY").digest(), u"My First Community", u"My First Community Comment")
        self._discovery.create_community_metadata(cid, alias, comment)
        yield 0.1
        try:
            tup = self._discovery_database.execute(u"SELECT alias, comment FROM community_metadata WHERE cid = ?", (buffer(cid),)).next()
        except StopIteration:
            assert False, "Entry not found"
        assert tup[0] == alias
        assert tup[1] == comment

        cid, alias, comment = (hashlib.sha1("MY-SECOND-COMMUNITY").digest(), u"My Second Community", u"My Second Community Comment")
        self._discovery.create_community_metadata(cid, alias, comment)
        yield 0.1
        try:
            tup = self._discovery_database.execute(u"SELECT alias, comment FROM community_metadata WHERE cid = ?", (buffer(cid),)).next()
        except StopIteration:
            assert False, "Entry not found"
        assert tup[0] == alias
        assert tup[1] == comment

        cid, alias, comment = (hashlib.sha1("MY-THIRD-COMMUNITY").digest(), u"My Third Community", u"My Third Community Comment")
        self._discovery.create_community_metadata(cid, alias, comment)
        yield 0.1
        try:
            tup = self._discovery_database.execute(u"SELECT alias, comment FROM community_metadata WHERE cid = ?", (buffer(cid),)).next()
        except StopIteration:
            assert False, "Entry not found"
        assert tup[0] == alias
        assert tup[1] == comment

    def food(self):
        """
        NODE creates a community and updates its metadata one by one.
        Packets are send in order.
        """
        node = DiscoveryNode()
        node.init_socket()
        node.set_community(self._discovery)
        node.init_my_member()
        yield 0.1

        address = self._dispersy.socket.get_address()
        cid = hashlib.sha1("FOOD").digest()

        node.send_message(node.create_community_metadata_message(cid, u"Food-01", u"Comment-01", 10, 1), address)
        yield 0.1
        tup = self._discovery_database.execute(u"SELECT alias, comment FROM community_metadata WHERE cid = ?", (buffer(cid),)).next()
        assert tup[0] == u"Food-01"
        assert tup[1] == u"Comment-01"

        node.send_message(node.create_community_metadata_message(cid, u"Food-02", u"Comment-02", 20, 2), address)
        yield 0.1
        tup = self._discovery_database.execute(u"SELECT alias, comment FROM community_metadata WHERE cid = ?", (buffer(cid),)).next()
        assert tup[0] == u"Food-02"
        assert tup[1] == u"Comment-02"

        node.send_message(node.create_community_metadata_message(cid, u"Food-03", u"Comment-03", 30, 3), address)
        yield 0.1
        tup = self._discovery_database.execute(u"SELECT alias, comment FROM community_metadata WHERE cid = ?", (buffer(cid),)).next()
        assert tup[0] == u"Food-03"
        assert tup[1] == u"Comment-03"

    def drink(self):
        """
        NODE creates a community and updates its metadata one by one.
        Packets are send OUT OF order.  This must cause a request for
        the missing packet.
        """
        node = DiscoveryNode()
        node.init_socket()
        node.set_community(self._discovery)
        node.init_my_member()
        yield 0.1

        address = self._dispersy.socket.get_address()
        cid = hashlib.sha1("DRINK").digest()

        node.send_message(node.create_community_metadata_message(cid, u"Drink-01", u"Comment-01", 10, 1), address)
        yield 0.1
        try:
            tup = self._discovery_database.execute(u"SELECT alias, comment FROM community_metadata WHERE cid = ?", (buffer(cid),)).next()
        except StopIteration:
            assert False, "Entry not found"
        assert tup[0] == u"Drink-01"
        assert tup[1] == u"Comment-01"

        node.send_message(node.create_community_metadata_message(cid, u"Drink-03", u"Comment-03", 30, 3), address)
        yield 0.1
        try:
            tup = self._discovery_database.execute(u"SELECT alias, comment FROM community_metadata WHERE cid = ?", (buffer(cid),)).next()
        except StopIteration:
            assert False, "Entry not found"
        assert tup[0] == u"Drink-01"
        assert tup[1] == u"Comment-01"

        _, message = node.receive_message(addresses=[address], message_names=[u"dispersy-missing-sequence"])
        # must ask for missing sequence 2
        assert message.payload.member.public_key == node.my_member.public_key
        assert message.payload.message.name == u"community-metadata"
        assert message.payload.missing_low == 2
        assert message.payload.missing_high == 2

        node.send_message(node.create_community_metadata_message(cid, u"Drink-02", u"Comment-02", 20, 2), address)
        yield 0.1
        try:
            tup = self._discovery_database.execute(u"SELECT alias, comment FROM community_metadata WHERE cid = ?", (buffer(cid),)).next()
        except StopIteration:
            assert False, "Entry not found"
        assert tup[0] == u"Drink-03"
        assert tup[1] == u"Comment-03"

    def drinks(self):
        """
        NODE creates a community and updates its metadata one by one.
        Packets are send OUT OF order.  This must cause a request for
        the missing packet.

        Checks the same as self.drink, but with a bigger gap between
        the sequence numbers.
        """
        node = DiscoveryNode()
        node.init_socket()
        node.set_community(self._discovery)
        node.init_my_member()
        yield 0.1

        address = self._dispersy.socket.get_address()
        cid = hashlib.sha1("DRINKS").digest()

        node.send_message(node.create_community_metadata_message(cid, u"Drinks-01", u"Comment-01", 10, 1), address)
        yield 0.1
        try:
            tup = self._discovery_database.execute(u"SELECT alias, comment FROM community_metadata WHERE cid = ?", (buffer(cid),)).next()
        except StopIteration:
            assert False, "Entry not found"
        assert tup[0] == u"Drinks-01"
        assert tup[1] == u"Comment-01"

        node.send_message(node.create_community_metadata_message(cid, u"Drinks-05", u"Comment-05", 50, 5), address)
        yield 0.1
        try:
            tup = self._discovery_database.execute(u"SELECT alias, comment FROM community_metadata WHERE cid = ?", (buffer(cid),)).next()
        except StopIteration:
            assert False, "Entry not found"
        assert tup[0] == u"Drinks-01"
        assert tup[1] == u"Comment-01"

        _, message = node.receive_message(addresses=[address], message_names=[u"dispersy-missing-sequence"])
        # must ask for missing sequence 2, 3, and 4
        assert message.payload.member.public_key == node.my_member.public_key
        assert message.payload.message.name == u"community-metadata"
        assert message.payload.missing_low == 2
        assert message.payload.missing_high == 4

        node.send_message(node.create_community_metadata_message(cid, u"Drinks-03", u"Comment-03", 30, 3), address)
        yield 0.1
        try:
            tup = self._discovery_database.execute(u"SELECT alias, comment FROM community_metadata WHERE cid = ?", (buffer(cid),)).next()
        except StopIteration:
            assert False, "Entry not found"
        assert tup[0] == u"Drinks-01"
        assert tup[1] == u"Comment-01"

        node.send_message(node.create_community_metadata_message(cid, u"Drinks-04", u"Comment-04", 40, 4), address)
        yield 0.1
        try:
            tup = self._discovery_database.execute(u"SELECT alias, comment FROM community_metadata WHERE cid = ?", (buffer(cid),)).next()
        except StopIteration:
            assert False, "Entry not found"
        assert tup[0] == u"Drinks-01"
        assert tup[1] == u"Comment-01"

        node.send_message(node.create_community_metadata_message(cid, u"Drinks-02", u"Comment-02", 20, 2), address)
        yield 0.1
        try:
            tup = self._discovery_database.execute(u"SELECT alias, comment FROM community_metadata WHERE cid = ?", (buffer(cid),)).next()
        except StopIteration:
            assert False, "Entry not found"
        assert tup[0] == u"Drinks-05"
        assert tup[1] == u"Comment-05"

class DiscoveryUserScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        master_key = ec_to_public_bin(ec)

        ec = ec_generate_key(u"low")
        self._my_member = MyMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)
        self._discovery = DiscoveryCommunity.join_community(master_key, self._my_member)
        self._discovery_database = DiscoveryDatabase.get_instance()

        self.caller(self.my_user_metadata)
        self.caller(self.alice)
        self.caller(self.bob)

    def my_user_metadata(self):
        """
        SELF creates some user metadata and checks if this ends up in
        the database.
        """
        my_member = self._discovery.my_member

        address = self._dispersy.socket.get_address()
        self._discovery.create_user_metadata(address, u"My Alias", u"My Comment")
        try:
            tup = self._discovery_database.execute(u"SELECT alias, comment FROM user_metadata WHERE user = ?", (my_member.database_id,)).next()
        except StopIteration:
            assert False, "Entry not found"
        assert tup[0] == u"My Alias"
        assert tup[1] == u"My Comment"

    def alice(self):
        """
        NODE creates several metadata versions, only the most recent
        version should be in the database.  Versions are created
        IN-order.
        """
        node = DiscoveryNode()
        node.init_socket()
        node.set_community(self._discovery)
        node.init_my_member()
        yield 0.1

        address = self._dispersy.socket.get_address()
        node_address = node.socket.getsockname()

        node.send_message(node.create_user_metadata_message(node_address, u"Alice-01", u"Comment-01", 10), address)
        yield 0.1
        try:
            tup = self._discovery_database.execute(u"SELECT alias, comment FROM user_metadata WHERE user = ?", (node.my_member.database_id,)).next()
        except StopIteration:
            assert False, "Entry not found"
        assert tup[0] == u"Alice-01"
        assert tup[1] == u"Comment-01"

        node.send_message(node.create_user_metadata_message(node_address, u"Alice-03", u"Comment-03", 30), address)
        yield 0.1
        try:
            tup = self._discovery_database.execute(u"SELECT alias, comment FROM user_metadata WHERE user = ?", (node.my_member.database_id,)).next()
        except StopIteration:
            assert False, "Entry not found"
        assert tup[0] == u"Alice-03"
        assert tup[1] == u"Comment-03"

        node.send_message(node.create_user_metadata_message(node_address, u"Alice-02", u"Comment-02", 20), address)
        yield 0.1
        try:
            tup = self._discovery_database.execute(u"SELECT alias, comment FROM user_metadata WHERE user = ?", (node.my_member.database_id,)).next()
        except StopIteration:
            assert False, "Entry not found"
        assert tup[0] == u"Alice-03"
        assert tup[1] == u"Comment-03"

    def bob(self):
        """
        NODE creates several metadata versions, only the most recent
        version should be in the database.  Versions are created
        OUT-OF-order.
        """
        node = DiscoveryNode()
        node.init_socket()
        node.set_community(self._discovery)
        node.init_my_member()
        yield 0.1

        address = self._dispersy.socket.get_address()
        node_address = node.socket.getsockname()

        node.send_message(node.create_user_metadata_message(node_address, u"Bob-03", u"Comment-03", 30), address)
        yield 0.1
        try:
            tup = self._discovery_database.execute(u"SELECT alias, comment FROM user_metadata WHERE user = ?", (node.my_member.database_id,)).next()
        except StopIteration:
            assert False, "Entry not found"
        assert tup[0] == u"Bob-03"
        assert tup[1] == u"Comment-03"

        node.send_message(node.create_user_metadata_message(node_address, u"Bob-01", u"Comment-01", 10), address)
        yield 0.1
        try:
            tup = self._discovery_database.execute(u"SELECT alias, comment FROM user_metadata WHERE user = ?", (node.my_member.database_id,)).next()
        except StopIteration:
            assert False, "Entry not found"
        assert tup[0] == u"Bob-03"
        assert tup[1] == u"Comment-03"

        node.send_message(node.create_user_metadata_message(node_address, u"Bob-02", u"Comment-02", 20), address)
        yield 0.1
        try:
            tup = self._discovery_database.execute(u"SELECT alias, comment FROM user_metadata WHERE user = ?", (node.my_member.database_id,)).next()
        except StopIteration:
            assert False, "Entry not found"
        assert tup[0] == u"Bob-03"
        assert tup[1] == u"Comment-03"

class DiscoverySyncScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        master_key = ec_to_public_bin(ec)

        ec = ec_generate_key(u"low")
        self._my_member = MyMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)
        self._discovery = DiscoveryCommunity.join_community(master_key, self._my_member)
        self._discovery_database = DiscoveryDatabase.get_instance()

        self.caller(self.to_node)
        self.caller(self.from_node)

    def to_node(self):
        """
        We add the communities COPPER and TIN to SELF and then we send
        a dispersy-sync message with an empty bloom filter; SELF
        should respond by offering the COPPER and TIN metadata.
        """
        node = DiscoveryNode()
        node.init_socket()
        node.set_community(self._discovery)
        node.init_my_member()
        address = self._dispersy.socket.get_address()
        yield 0.1

        # create COPPER and TIN communities
        messages = []
        messages.append(node.create_community_metadata_message(hashlib.sha1("COPPER").digest(), u"Copper Community", u"Copper Community Comment", 10, 1))
        messages.append(node.create_community_metadata_message(hashlib.sha1("TIN").digest(), u"Tin Community", u"Tin Community Comment", 20, 2))
        packets = [node.encode_message(message) for message in messages]
        for packet in packets:
            node.send_packet(packet, address)
            yield 0.1

        # send empty bloomfilter
        node.send_message(node.create_dispersy_sync_message(1, 100, [], 3), address)
        yield 0.1

        # receive COPPER and TIN communities
        received = [False] * len(packets)
        while filter(lambda x: not x, received):
            _, pckt = node.receive_packet(addresses=[address], packets=packets)
            for index, packet in zip(xrange(len(packets)), packets):
                if pckt == packet:
                    received[index] = True
        assert not filter(lambda x: not x, received)

    def from_node(self):
        """
        We add the communities IRON and MITHRIL to SELF and wait until
        SELF sends a dispersy-sync message to ensure that the messages
        (containing the communities) are in its bloom filter.
        """
        node = DiscoveryNode()
        node.init_socket()
        node.set_community(self._discovery)
        node.init_my_member()
        address = self._dispersy.socket.get_address()
        yield 0.1

        # create messages should show up in the bloom filter from SELF
        messages = []
        messages.append(node.create_community_metadata_message(hashlib.sha1("IRON").digest(), u"Iron Community", u"Iron Community Comment", 10, 1))
        messages.append(node.create_community_metadata_message(hashlib.sha1("MITHRIL").digest(), u"Mithril Community", u"Mithril Community Comment", 20, 2))
        packets = [node.encode_message(message) for message in messages]
        for packet in packets:
            node.send_packet(packet, address)
            yield 0.1

        # wait for dispersy-sync message
        for _ in xrange(600):
            yield 0.1
            try:
                _, message = node.receive_message(addresses=[address], message_names=[u"dispersy-sync"])
            except:
                continue

            for packet in packets:
                assert packet in message.payload.bloom_filter
            break

        else:
            assert False

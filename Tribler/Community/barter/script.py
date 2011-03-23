# Python 2.5 features
from __future__ import with_statement

from hashlib import sha1
import time

from payload import BarterRecordPayload
from community import BarterCommunity
from lencoder import log

from Tribler.Core.dispersy.crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin
from Tribler.Core.dispersy.member import Member, MyMember
from Tribler.Core.dispersy.script import ScriptBase
from Tribler.Core.dispersy.debug import Node
from Tribler.Core.dispersy.dprint import dprint

from random import random

class BarterNode(Node):
    def create_barter_record(self, second_member, first_upload, second_upload, global_time):
        meta = self._community.get_meta_message(u"barter-record")
        return meta.implement(meta.authentication.implement([self._my_member, second_member]),
                              meta.distribution.implement(global_time),
                              meta.destination.implement(),
                              meta.payload.implement(first_upload, second_upload))

class BarterScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = MyMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)

        self.caller(self.test_incoming_barter_record)
        #todo: fix test
        # self.caller(self.test_create_barter_record)

    def is_database_empty(self, community):
        try:
            community._database.execute(u"SELECT 1 FROM record WHERE community = ?", (community.database_id,)).next()
        except StopIteration:
            return True
        else:
            return False

    def test_incoming_barter_record(self):
        """
        1. Create a record signed only by NODE
        2. Send signature request from NODE to SELF
        3. Receive signature reply from SELF to NODE
        4. Check the signature
        5. Send double signed record from NODE to SELF
        6. Check that the record is stored in the database at SELF
        """
        community = BarterCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()

        # create node and ensure that SELF knows the node address
        node = BarterNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.1
        assert self.is_database_empty(community), "Database should be empty (for this community id)"

        # 1. Create a record signed only by NODE
        self_member = Member(community._my_member.public_key, sync_with_database=False)
        record = node.create_barter_record(self_member, 10, 2, 1)

        # 2. Send signature request from NODE to SELF
        request = node.create_dispersy_signature_request_message(record, 2, self_member)
        node.send_message(request, address)
        yield 0.1

        # 3. Receive signature reply from SELF to NODE
        # 4. Check the signature
        _, response = node.receive_message(addresses=[address], message_names=[u"dispersy-signature-response"])
        first_signature_offset = len(record.packet) - sum([member.signature_length for member in record.authentication.members])
        identifier = sha1(request.packet).digest()
        assert response.payload.identifier == identifier
        assert self_member.verify(record.packet[:first_signature_offset], response.payload.signature)

        # 5. Send double signed record from NODE to SELF
        second_signature_offset = len(record.packet) - record.authentication.members[1].signature_length
        packet = record.packet[:second_signature_offset] + response.payload.signature
        node.send_packet(packet, address)
        yield 0.1

        # 6. Check that the record is stored in the database at SELF
        try:
            community._database.execute(u"SELECT 1 FROM record WHERE community = ? AND global_time = ? AND first_member = ? AND second_member = ? AND upload_first_member = ? AND upload_second_member = ?",
                                        (community.database_id, 1, node.my_member.database_id, community._my_member.database_id, 10, 2)).next()
        except StopIteration:
            assert False

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

    def test_create_barter_record(self):
        """
        1. Create a single signed barter record
        2. Send signature request from SELF to NODE
        3. Add signature and send barter record from NODE to SELF
        4. Check database for the new record
        """
        community = BarterCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()

        # create node and ensure that SELF knows the node address
        node = BarterNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.1
        assert self.is_database_empty(community), "Database should be empty (for this community id)"

        # send single signed barter record
        message = community.create_barter_record(Member.get_instance(node.my_member.public_key), 10, 2)
        yield 0.1

        # receive signature request
        _, message = node.receive_message(addresses=[address], message_names=[u"dispersy-signature-request"])
        assert message.payload.message.name == u"barter-record"
        assert message.payload.message.authentication.members[0].public_key == community.my_member.public_key
        assert message.payload.message.authentication.members[1].public_key == node.my_member.public_key
        assert message.payload.message.authentication.signed_members[0][0]
        assert not message.payload.message.authentication.is_signed
        assert not message.payload.message.authentication.signed_members[1][0]
        assert message.payload.message.payload.first_upload == 10
        assert message.payload.message.payload.second_upload == 2

        # create signature and send data back
        message = message.payload.message
        first_signature_offset = len(message.packet) - sum(member.signature_length for member in message.authentication.members)
        signature = node.my_member.sign(message.packet, length=first_signature_offset)
        message.authentication.set_signature(Member.get_instance(node.my_member.public_key), signature)
        node.send_message(message, address)
        yield 0.1
        try:
            community._database.execute(u"SELECT 1 FROM record WHERE community = ? AND global_time = ? AND first_member = ? AND second_member = ? AND upload_first_member = ? AND upload_second_member = ?",
                                        (community.database_id, message.distribution.global_time, node.my_member.database_id, community._my_member.database_id, 10, 2)).next()
        except StopIteration:
            assert False

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

class BarterScenarioScript(ScriptBase):
    def __init__(self, script, name, **kargs):
        ScriptBase.__init__(self, script, name, **kargs)
        self._timestep = float(kargs.get('timestep', 1.0))
        self._stepcount = 0
        self._starting_timestamp = float(kargs.get('starting_timestamp', time.time()))

    def find_peer_by_name(self, peername):
        assert isinstance(peername, str)
        if not peername in self._members:
            with open('data/peers') as fp:
                for line in fp:
                    name, ip, port, public_key, _ = line.split()
                    if name == peername:
                        public_key = public_key.decode("HEX")
                        self._members[name] = (Member(public_key, sync_with_database=True), (ip, int(port)))
                        break
                else:
                    raise ValueError("Node with name '%s' not in nodes db" % peername)
        return self._members[peername]

    def set_online(self):
        """ Restore on_incoming_packets and _send functions of
        dispersy back to normal.

        This simulates a node coming online, since it's able to send
        and receive messages.
        """
        dprint("Going online")
        self._dispersy.on_incoming_packets = self.original_on_incoming_packets
        self._dispersy._send = self.original_send

    def set_offline(self):
        """ Replace on_incoming_packets and _sends functions of
        dispersy with dummies

        This simulates a node going offline, since it's not able to
        send or receive any messages
        """
        def dummy_function(*params):
            return
        dprint("Going offline")
        self._dispersy.on_incoming_packets = dummy_function
        self._dispersy._send = dummy_function

    def get_commands_from_fp(self, fp, step):
        """ Return a list of commands from file handle for step

        Read lines from fp and return all the lines starting at
        timestamp equal to step. If we read the end of the file,
        without commands to return, then I return -1.
        """
        commands = []
        while True:
            cursor_position = fp.tell()
            line = fp.readline().strip()
            if not line:
                if commands: return commands
                else: return -1

            cmdstep, command = line.split(' ', 1)

            cmdstep = int(cmdstep)
            if cmdstep < step:
                continue
            elif cmdstep == step:
                commands.append(command)
            else:
                # restore cursor position and break
                fp.seek(cursor_position)
                break

        return commands

    def sleep(self):
        """ Calculate the time to sleep.
        """
        now = time.time()
        expected_time = self._starting_timestamp + (self._timestep * self._stepcount)
        st = max(0.0, expected_time - now) * random()
        log("barter.log", "sleep", delay=st, diff=expected_time - now, stepcount=self._stepcount)
        return st

    def run(self):
        if __debug__: log("barter.log", "start-barter-script")
        # this master key NEEDS to be the same as that in BarterTrackerScript as they work together
        master_key = "3081a7301006072a8648ce3d020106052b81040027038192000403cbbfd2dfb67a7db66c88988df56f93fa6e7f982f9a6a0fa8898492c8b8cae23e10b159ace60b7047012082a5aa4c6e221d7e58107bb550436d57e046c11ab4f51f0ab18fa8f58d0346cc12d1cc2b61fc86fe5ed192309152e11e3f02489e30c7c971dd989e1ce5030ea0fb77d5220a92cceb567cbc94bc39ba246a42e215b55e9315b543ddeff0209e916f77c0d747".decode("HEX")

        self._members = {}
        self.original_on_incoming_packets = self._dispersy.on_incoming_packets
        self.original_send = self._dispersy._send

        #
        # Read our configuration from the peer.conf file
        # name, ip, port, public and private key
        #
        with open('data/peer.conf') as fp:
            my_name, ip, port, public_key, private_key = fp.readline().split()
            public_key = public_key.decode("HEX")
            private_key = private_key.decode("HEX")
            my_address = (ip, int(port))
        if __debug__: log("barter.log", "read-config-done")

        # create mymember
        my_member = MyMember(public_key, private_key, sync_with_database=True)
        dprint(my_member)

        # join the barter community with the newly created member
        self._barter = BarterCommunity.join_community(sha1(master_key).digest(), master_key, my_member)
        dprint("Joined barter community ", self._barter._my_member)
        if __debug__:
            log("barter.log", "joined-barter-community")
            log("barter.log", "barter-community-property", name="sync_interval", value=self._barter.dispersy_sync_interval)
            log("barter.log", "barter-community-property", name="sync_member_count", value=self._barter.dispersy_sync_member_count)
            log("barter.log", "barter-community-property", name="sync_response_limit", value=self._barter.dispersy_sync_response_limit)

        yield 2.0

        # create a dispersy-identity message for my_member and the
        # self._barter community.  This message will be sent to all
        # the peers in the 'peers' file to (a) add them to our candidate
        # table (b) let them know about our existance and our public
        # key
        meta = self._barter.get_meta_message(u"dispersy-identity")
        message = meta.implement(meta.authentication.implement(meta.community._my_member),
                                 meta.distribution.implement(meta.community._timeline.claim_global_time()),
                                 meta.destination.implement(),
                                 meta.payload.implement(my_address))
        self._dispersy.store_update_forward([message], True, True, False)

        # now send the dispersy-identity message to everybody the
        # dispersy-identity is a CommunityDestination message but
        # currently we don't know anyone else in the
        # community. Therefore we have to specifically forward the
        # message to peers using the _dispersy._send function with
        # (ip, port) combinations we read from the 'data/peers' file
        if __debug__:
            _peer_counter = 0
        with self._dispersy.database as execute:
            with open('data/peers') as file:
                for line in file:
                    name, ip, port, public_key, _ = line.split(' ', 4)
                    if __debug__:
                        _peer_counter += 1
                        log("barter.log", "read-peer-config", position=_peer_counter, name=name, ip=ip, port=port)
                    if name == my_name: continue
                    public_key = public_key.decode('HEX')
                    port = int(port)

                    #self._dispersy._send([(ip, port)], [message.packet])
                    execute(u"INSERT OR IGNORE INTO candidate(community, host, port, incoming_time, outgoing_time) VALUES(?, ?, ?, DATETIME(), '2010-01-01 00:00:00')", (message.community.database_id, unicode(ip), port))
                    execute(u"INSERT OR IGNORE INTO user(mid, public_key, host, port) VALUES(?, ?, ?, ?)", (buffer(sha1(public_key).digest()), buffer(public_key), unicode(ip), port))
                    if __debug__:
                        log("barter.log", "mid_add", mid=sha1(public_key).digest())
            execute(u"DELETE FROM candidate where community=0")

        if __debug__:
            log("barter.log", "done-reading-peers")

        yield 2.0

        # open the scenario files, as generated from Mircea's Scenario
        # Generator
        bartercast_fp = open('data/bartercast.log')
        availability_fp = open('data/availability.log')

        self._stepcount = 0

        # wait until we reach the starting time
        yield self.sleep()

        self._stepcount = 1

        # start the scenario
        while True:
            # get commands
            barter_cmds = self.get_commands_from_fp(bartercast_fp, self._stepcount)
            availability_cmds = self.get_commands_from_fp(availability_fp, self._stepcount)

            # if there are no commands exit the while loop
            if barter_cmds == -1 and availability_cmds == -1:
                if __debug__: log("barter.log", "no-commands")
                break
            else:
                # if there is a start in the avaibility_cmds then go
                # online
                if availability_cmds != -1 and 'start' in availability_cmds:
                    self.set_online()

                # if there are barter_cmds then execute them
                if barter_cmds != -1:
                    for cmd in barter_cmds:
                        name, up, down = cmd.split()
                        up, down = map(int, (up, down))
                        # note a peer creates a record when it has
                        # interest (e.g. it's upload is larger than
                        # its download)
                        if up >= down:
                            peer_member, address = self.find_peer_by_name(name)
                            self._barter.create_barter_record(peer_member, up, down)

                # if there is a stop in the availability_cmds then go
                # offline
                if availability_cmds != -1 and 'stop' in availability_cmds:
                    self.set_offline()

            # sleep until the next step
            yield self.sleep()
            self._stepcount += 1

        # I finished the scenario execution. I should stay online
        # until killed. Note that I can still sync and exchange
        # messages with other peers.
        while True:
            # wait to be killed
            yield 100.0


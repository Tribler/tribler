# Python 2.5 features
from __future__ import with_statement

"""
Run some python code, usually to test one or more features.
"""

import hashlib
import types
from struct import pack, unpack_from

from authentication import MultiMemberAuthentication
from bloomfilter import BloomFilter
from community import Community
from conversion import BinaryConversion
from crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin
from debug import Node
from destination import CommunityDestination
from dispersy import Dispersy
from dispersydatabase import DispersyDatabase
from distribution import FullSyncDistribution, LastSyncDistribution
from dprint import dprint
from member import Member, MyMember
from message import Message, DropMessage
from resolution import PublicResolution
from singleton import Singleton

from debugcommunity import DebugCommunity, DebugNode

class Script(Singleton):
    def __init__(self, rawserver):
        self._call_generators = []
        self._scripts = {}
        self._rawserver = rawserver

    def add(self, name, script, args={}, include_with_all=True):
        assert isinstance(name, str)
        assert not name in self._scripts
        assert issubclass(script, ScriptBase)
        self._scripts[name] = (include_with_all, script, args)

    def load(self, name):
        dprint(name)

        if name == "all":
            for name, (include_with_all, script, args) in self._scripts.iteritems():
                if include_with_all:
                    dprint(name)
                    script(self, name, **args)

        elif name in self._scripts:
            self._scripts[name][1](self, name, **self._scripts[name][2])

        else:
            for available in sorted(self._scripts):
                dprint("available: ", available)
            raise ValueError("Unknown script '%s'" % name)

    def add_generator(self, call, call_generator):
        self._call_generators.append((call, call_generator))
        if len(self._call_generators) == 1:
            self._start(call)
            self._rawserver.add_task(self._process_generators, 0.0)

    def _start(self, call):
#         dprint("start ", call.__self__.__class__.__name__, ".", call.__name__, line=1)
        dprint("start ", call, line=1)
        if call.__doc__:
            dprint(call.__doc__, box=1)

    def _process_generators(self):
        if self._call_generators:
            call, call_generator = self._call_generators[0]
            try:
                delay = call_generator.next()

            except StopIteration:
                self._call_generators.pop(0)
                delay = 0.01
#                 dprint("finished: ", call.__self__.__class__.__name__, ".", call.__name__)
                dprint("finished ", call)
                if self._call_generators:
                    call, call_generator = self._call_generators[0]
                    self._start(call)

            self._rawserver.add_task(self._process_generators, delay)

        else:
            dprint("shutdown", box=1)
            self._rawserver.doneflag.set()
            self._rawserver.shutdown()

class ScriptBase(object):
    def __init__(self, script, name, **kargs):
        self._script = script
        self._name = name
        self._dispersy = Dispersy.get_instance()
        self._dispersy_database = DispersyDatabase.get_instance()
        self.caller(self.run)

    def caller(self, run):
        run_generator = run()
        if isinstance(run_generator, types.GeneratorType):
            self._script.add_generator(run, run_generator)

    def run():
        raise NotImplementedError("Must implement a generator or use self.caller(...)")

class DispersyTimelineScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = MyMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)

        self.caller(self.succeed_check)
        self.caller(self.fail_check)
        self.caller(self.loading_community)

    def succeed_check(self):
        """
        Create a community and perform check if a hard-kill message is accepted.

        Whenever a community is created the owner message is authorized to use the
        dispersy-destroy-community message.  Hence, this message should be accepted by the
        timeline.check().
        """
        # create a community.
        community = DebugCommunity.create_community(self._my_member)
        # the master member must have given my_member all permissions for dispersy-destroy-community
        yield 0.1

        dprint("master_member: ", community.master_member.database_id, ", ", community.master_member.mid.encode("HEX"))
        dprint("    my_member: ", community.my_member.database_id, ", ", community.my_member.mid.encode("HEX"))

        # check if we are still allowed to send the message
        message = community.create_dispersy_destroy_community(u"hard-kill", store=False, update=False, forward=False)
        assert message.authentication.member == self._my_member
        result = list(message.check_callback([message]))
        assert result == [message], "check_... methods should return a generator with the accepted messages"

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

    def fail_check(self):
        """
        Create a community and perform check if a hard-kill message is NOT accepted.

        Whenever a community is created the owner message is authorized to use the
        dispersy-destroy-community message.  We will first revoke the authorization (to use this
        message) and ensure that the message is no longer accepted by the timeline.check().
        """
        # create a community.
        community = DebugCommunity.create_community(self._my_member)
        # the master member must have given my_member all permissions for dispersy-destroy-community
        yield 0.1

        dprint("master_member: ", community.master_member.database_id, ", ", community.master_member.mid.encode("HEX"))
        dprint("    my_member: ", community.my_member.database_id, ", ", community.my_member.mid.encode("HEX"))

        # remove the right to hard-kill
        community.create_dispersy_revoke([(community.my_member, community.get_meta_message(u"dispersy-destroy-community"), u"permit")], sign_with_master=True, store=False, forward=False)

        # check if we are still allowed to send the message
        message = community.create_dispersy_destroy_community(u"hard-kill", store=False, update=False, forward=False)
        assert message.authentication.member == self._my_member
        result = list(message.check_callback([message]))
        assert len(result) == 1, "check_... methods should return a generator with the accepted messages"
        assert isinstance(result[0], DropMessage), "check_... methods should return a generator with the accepted messages"

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill", sign_with_master=True)

    def loading_community(self):
        """
        When a community is loaded it must load all available dispersy-authorize and dispersy-revoke
        message from the database.
        """
        # load_communities will load all communities with the same classification
        class LoadingCommunityTestCommunity(DebugCommunity):
            pass

        # create a community.  the master member must have given my_member all permissions for
        # dispersy-destroy-community
        community = LoadingCommunityTestCommunity.create_community(self._my_member)
        master_key = community.master_member.public_key

        dprint("master_member: ", community.master_member.database_id, ", ", community.master_member.mid.encode("HEX"))
        dprint("    my_member: ", community.my_member.database_id, ", ", community.my_member.mid.encode("HEX"))

        self._dispersy.remove_community(community)
        yield 0.1

        # load the same community and see if the same permissions are loaded
        communities = LoadingCommunityTestCommunity.load_communities()
        assert len(communities) == 1

        # check if we are still allowed to send the message
        message = community.create_dispersy_destroy_community(u"hard-kill", store=False, update=False, forward=False)
        assert community._timeline.check(message)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

class DispersyCandidateScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = MyMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)

        self.caller(self.incoming_candidate_request)
        self.caller(self.outgoing_candidate_response)
        self.caller(self.outgoing_candidate_request)

    def incoming_candidate_request(self):
        """
        Sending a dispersy-candidate-request from NODE to SELF.

        - Test that SELF stores the routes in its database.
        - TODO: Test that duplicate routes are updated (timestamp)
        """
        community = DebugCommunity.create_community(self._my_member)
        conversion_version = community.get_conversion().version
        address = self._dispersy.socket.get_address()

        # create node
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member(candidate=False)
        yield 0.01

        # send a dispersy-candidate-request message
        routes = [(("123.123.123.123", 123), 60.0),
                  (("124.124.124.124", 124), 120.0)]
        node.send_message(node.create_dispersy_candidate_request_message(node.socket.getsockname(), address, conversion_version, routes, 10), address)
        yield 0.01

        # routes must be placed in the database
        items = [((str(host), port), float(age)) for host, port, age in self._dispersy_database.execute(u"SELECT host, port, STRFTIME('%s', DATETIME('now')) - STRFTIME('%s', external_time) AS age FROM candidate WHERE community = ?", (community.database_id,))]
        for route in routes:
            off_by_one_second = (route[0], route[1]+1)
            assert route in items or off_by_one_second in items

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

    def outgoing_candidate_response(self):
        """
        Sending a dispersy-candidate-request from NODE to SELF must result in a
        dispersy-candidate-response from SELF to NODE.

        - Test that some routes in SELF database are part of the response.
        """
        community = DebugCommunity.create_community(self._my_member)
        conversion_version = community.get_conversion().version
        address = self._dispersy.socket.get_address()

        # create node
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member(candidate=False)
        yield 0.01

        routes = [(u"1.2.3.4", 5),
                  (u"2.3.4.5", 6)]

        # put some routes in the database that we expect back
        with self._dispersy_database as execute:
            for host, port in routes:
                execute(u"INSERT INTO candidate (community, host, port, incoming_time, outgoing_time) VALUES (?, ?, ?, DATETIME('now'), DATETIME('now'))", (community.database_id, host, port))

        # send a dispersy-candidate-request message
        node.send_message(node.create_dispersy_candidate_request_message(node.socket.getsockname(), address, conversion_version, [], 10), address)
        yield 0.01

        # catch dispersy-candidate-response message
        _, message = node.receive_message(addresses=[address], message_names=[u"dispersy-candidate-response"])
        dprint(message.payload.routes, lines=1)
        for route in routes:
            assert (route, 0.0) in message.payload.routes, (route, message.payload.routes)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

    def outgoing_candidate_request(self):
        """
        SELF must send a dispersy-candidate-request every community.dispersy_candidate_request_interval
        seconds.
        """
        class TestCommunity(DebugCommunity):
            @property
            def dispersy_candidate_request_initial_delay(self):
                return 5.0

            @property
            def dispersy_candidate_request_interval(self):
                return 7.0

            @property
            def dispersy_candidate_request_member_count(self):
                return 10

            @property
            def dispersy_candidate_request_destination_diff_range(self):
                return (0.0, 30.0)

            @property
            def dispersy_candidate_request_destination_age_range(self):
                return (0.0, 30.0)

        community = TestCommunity.create_community(self._my_member)
        conversion_version = community.get_conversion().version
        address = self._dispersy.socket.get_address()

        # create node
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member(candidate=False)

        # wait initial delay
        for counter in range(community.dispersy_candidate_request_initial_delay):
            dprint("waiting... ", community.dispersy_candidate_request_initial_delay - counter)
            # do NOT receive dispersy-candidate-request
            try:
                _, message = node.receive_message(addresses=[address], message_names=[u"dispersy-candidate-request"])
            except:
                pass
            else:
                assert False

            # wait interval
            yield 1.0
        yield 0.1

        # receive dispersy-candidate-request
        _, message = node.receive_message(addresses=[address], message_names=[u"dispersy-candidate-request"])

        # wait interval
        for counter in range(community.dispersy_candidate_request_interval):
            dprint("waiting... ", community.dispersy_candidate_request_interval - counter)
            # do NOT receive dispersy-candidate-request
            try:
                _, message = node.receive_message(addresses=[address], message_names=[u"dispersy-candidate-request"])
            except:
                pass
            else:
                assert False

            # wait interval
            yield 1.0

        yield 0.1

        # receive dispersy-candidate-request from 2nd interval
        _, message = node.receive_message(addresses=[address], message_names=[u"dispersy-candidate-request"])

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

class DispersyDestroyCommunityScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = MyMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)

        # todo: test that after a hard-kill, all new incoming messages are dropped.
        # todo: test that after a hard-kill, nothing is added to the candidate table anymore

        self.caller(self.hard_kill)

    def hard_kill(self):
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        message = community.get_meta_message(u"full-sync-text")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.01

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id)))
        assert len(times) == 0, times

        # send a message
        global_time = 10
        node.send_message(node.create_full_sync_text_message("should be accepted (1)", global_time), address)
        yield 0.01
        times = [x for x, in self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert len(times) == 1
        assert global_time in times

        # destroy the community
        community.create_dispersy_destroy_community(u"hard-kill")
        yield 0.01

        # node should receive the dispersy-destroy-community message
        _, message = node.receive_message(addresses=[address], message_names=[u"dispersy-destroy-community"])
        assert not message.payload.is_soft_kill
        assert message.payload.is_hard_kill

        # the candidate table must be empty
        assert not list(self._dispersy_database.execute(u"SELECT * FROM candidate WHERE community = ?", (community.database_id,)))

        # the database should have been cleaned
        # todo

class DispersyMemberTagScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = MyMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)

        self.caller(self.ignore_test)
        self.caller(self.drop_test)

    def ignore_test(self):
        """
        Test the must_ignore = True feature.

        When we ignore a specific member we will still accept messages from that member and store
        them in our database.  However, the GUI may choose not to display any messages from them.
        """
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        message = community.get_meta_message(u"full-sync-text")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.01

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON (reference_user_sync.sync = sync.id) WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id)))
        assert len(times) == 0, times

        # send a message
        global_time = 10
        node.send_message(node.create_full_sync_text_message("should be accepted (1)", global_time), address)
        yield 0.01
        times = [x for x, in self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON (reference_user_sync.sync = sync.id) WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert times == [10], times

        # we now tag the member as ignore
        Member.get_instance(node.my_member.public_key).must_ignore = True

        tags, = self._dispersy_database.execute(u"SELECT tags FROM user WHERE id = ?", (node.my_member.database_id,)).next()
        assert tags & 2

        # send a message and ensure it is in the database (ignore still means it must be stored in
        # the database)
        global_time = 20
        node.send_message(node.create_full_sync_text_message("should be accepted (2)", global_time), address)
        yield 0.01
        times = [x for x, in self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON (reference_user_sync.sync = sync.id) WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert sorted(times) == [10, 20], times

        # we now tag the member not to ignore
        Member.get_instance(node.my_member.public_key).must_ignore = False

        # send a message
        global_time = 30
        node.send_message(node.create_full_sync_text_message("should be accepted (3)", global_time), address)
        yield 0.01
        times = [x for x, in self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON (reference_user_sync.sync = sync.id) WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert sorted(times) == [10, 20, 30], times

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

    def drop_test(self):
        """
        Test the must_drop = True feature.

        When we 'drop' a specific member we will no longer accept or store messages from that
        member.  No callback will be given to the community code.
        """
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        message = community.get_meta_message(u"full-sync-text")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.01

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON (reference_user_sync.sync = sync.id) WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id)))
        assert len(times) == 0, times

        # send a message
        global_time = 10
        node.send_message(node.create_full_sync_text_message("should be accepted (1)", global_time), address)
        yield 0.01
        times = [x for x, in self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON (reference_user_sync.sync = sync.id) WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert len(times) == 1
        assert global_time in times

        # we now tag the member as drop
        Member.get_instance(node.my_member.public_key).must_drop = True

        tags, = self._dispersy_database.execute(u"SELECT tags FROM user WHERE id = ?", (node.my_member.database_id,)).next()
        assert tags & 4

        # send a message and ensure it is not in the database
        global_time = 20
        node.send_message(node.create_full_sync_text_message("should NOT be accepted (2)", global_time), address)
        yield 0.01
        times = [x for x, in self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON (reference_user_sync.sync = sync.id) WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert len(times) == 1
        assert global_time not in times

        # we now tag the member not to drop
        Member.get_instance(node.my_member.public_key).must_drop = False

        # send a message
        global_time = 30
        node.send_message(node.create_full_sync_text_message("should be accepted (3)", global_time), address)
        yield 0.01
        times = [x for x, in self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON (reference_user_sync.sync = sync.id) WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert len(times) == 2
        assert global_time in times

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

class DispersySyncScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = MyMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)

        # scaling: when we have to many messages in the sync bloom filter
        self.caller(self.large_sync)

        # different sync policies
        self.caller(self.in_order_test)
        self.caller(self.out_order_test)
        self.caller(self.random_order_test)
        self.caller(self.mixed_order_test)
        self.caller(self.last_1_test)
        self.caller(self.last_9_nosequence_test)
        # self.caller(self.last_9_sequence_test)

    def large_sync(self):
        """
        The sync bloomfilter covers a certain global-time range.  Hence, as time goes on, multiple
        bloomfilters should be generated and periodically synced.

        We use a dispersy_sync_bloom_filter_step off 25.  Hence each bloom filter must cover ranges:
        1-25, 26-50, 51-75, etc.
        """
        class TestCommunity(DebugCommunity):
            @property
            def dispersy_sync_bloom_filter_step(self):
                return 25

        community = TestCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.01

        # create a few messages in each sync bloomfilter range
        messages = []
        messages.append(node.send_message(node.create_in_order_text_message("Range 1 <= 24 <= 25", 24), address))
        yield 0.01
        messages.append(node.send_message(node.create_in_order_text_message("Range 1 <= 25 <= 25", 25), address))
        yield 0.01
        messages.append(node.send_message(node.create_in_order_text_message("Range 26 <= 26 <= 50", 26), address))
        yield 0.01
        messages.append(node.send_message(node.create_in_order_text_message("Range 26 <= 49 <= 50", 49), address))
        yield 0.01
        messages.append(node.send_message(node.create_in_order_text_message("Range 26 <= 50 <= 50", 50), address))
        yield 0.01
        messages.append(node.send_message(node.create_in_order_text_message("Range 51 <= 51 <= 75", 51), address))
        yield 0.01
        messages.append(node.send_message(node.create_in_order_text_message("Range 51 <= 74 <= 75", 74), address))
        yield 0.01
        messages.append(node.send_message(node.create_in_order_text_message("Range 51 <= 75 <= 75", 75), address))
        yield 0.01

        for message in messages:
            assert message.packet in community.get_bloom_filter(message.distribution.global_time)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

    def in_order_test(self):
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        message = community.get_meta_message(u"in-order-text")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.01

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON (reference_user_sync.sync = sync.id) WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id)))
        assert len(times) == 0, times

        # create some data
        global_times = range(10, 15)
        for global_time in global_times:
            node.send_message(node.create_in_order_text_message("Message #%d" % global_time, global_time), address)
            yield 0.01

        # send an empty sync message to obtain all messages in-order
        node.send_message(node.create_dispersy_sync_message(min(global_times), max(global_times), [], max(global_times)), address)
        yield 0.01

        for global_time in global_times:
            _, message = node.receive_message(addresses=[address], message_names=[u"in-order-text"])
            assert message.distribution.global_time == global_time

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

    def out_order_test(self):
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        message = community.get_meta_message(u"out-order-text")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.01

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON (reference_user_sync.sync = sync.id) WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id)))
        assert len(times) == 0, times

        # create some data
        global_times = range(10, 15)
        for global_time in global_times:
            node.send_message(node.create_out_order_text_message("Message #%d" % global_time, global_time), address)
            yield 0.01

        # send an empty sync message to obtain all messages out-order
        node.send_message(node.create_dispersy_sync_message(min(global_times), max(global_times), [], max(global_times)), address)
        yield 0.01

        for global_time in reversed(global_times):
            _, message = node.receive_message(addresses=[address], message_names=[u"out-order-text"])
            assert message.distribution.global_time == global_time

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

    def random_order_test(self):
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        message = community.get_meta_message(u"random-order-text")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.01

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON (reference_user_sync.sync = sync.id) WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id)))
        assert len(times) == 0, times

        # create some data
        global_times = range(10, 15)
        for global_time in global_times:
            node.send_message(node.create_random_order_text_message("Message #%d" % global_time, global_time), address)
            yield 0.01

        def get_messages_back():
            received_times = []
            for _ in range(len(global_times)):
                _, message = node.receive_message(addresses=[address], message_names=[u"random-order-text"])
                received_times.append(message.distribution.global_time)

            return received_times

        lists = []
        for _ in range(5):
            # send an empty sync message to obtain all messages in random-order
            node.send_message(node.create_dispersy_sync_message(min(global_times), max(global_times), [], max(global_times)), address)
            yield 0.01

            received_times = get_messages_back()
            if not received_times in lists:
                lists.append(received_times)

        dprint(lists, lines=True)
        assert len(lists) > 1

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

    def mixed_order_test(self):
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        in_order_message = community.get_meta_message(u"in-order-text")
        out_order_message = community.get_meta_message(u"out-order-text")
        random_order_message = community.get_meta_message(u"random-order-text")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.01

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON (reference_user_sync.sync = sync.id) WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name IN (?, ?, ?)", (community.database_id, node.my_member.database_id, in_order_message.database_id, out_order_message.database_id, random_order_message.database_id)))
        assert len(times) == 0, times

        # create some data
        global_times = range(10, 25, 3)
        in_order_times = []
        out_order_times = []
        random_order_times = []
        for global_time in global_times:
            in_order_times.append(global_time)
            node.send_message(node.create_in_order_text_message("Message #%d" % global_time, global_time), address)
            yield 0.01
            global_time += 1
            out_order_times.append(global_time)
            node.send_message(node.create_out_order_text_message("Message #%d" % global_time, global_time), address)
            yield 0.01
            global_time += 1
            random_order_times.append(global_time)
            node.send_message(node.create_random_order_text_message("Message #%d" % global_time, global_time), address)
            yield 0.01
        out_order_times.sort(reverse=True)
        dprint("Total in:", len(in_order_times), "; out:", len(out_order_times), "; rand:", len(random_order_times))

        def get_messages_back():
            received_times = []
            for _ in range(len(global_times) * 3):
                _, message = node.receive_message(addresses=[address], message_names=[u"in-order-text", u"out-order-text", u"random-order-text"])
                received_times.append(message.distribution.global_time)

            return received_times

        lists = []
        for _ in range(5):
            # send an empty sync message to obtain all messages in random-order
            node.send_message(node.create_dispersy_sync_message(min(global_times), 0, [], max(global_times)), address)
            yield 0.01

            received_times = get_messages_back()

            # the first items must be in-order
            received_in_times = received_times[0:len(in_order_times)]
            assert in_order_times == received_in_times

            # followed by out-order
            received_out_times = received_times[len(in_order_times):len(in_order_times) + len(out_order_times)]
            assert out_order_times == received_out_times

            # followed by random-order
            received_random_times = received_times[len(in_order_times) + len(out_order_times):]
            for global_time in received_random_times:
                assert global_time in random_order_times

            if not received_times in lists:
                lists.append(received_times)

        dprint(lists, lines=True)
        assert len(lists) > 1

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

    def last_1_test(self):
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        message = community.get_meta_message(u"last-1-test")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.01

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id)))
        assert len(times) == 0, times

        # send a message
        global_time = 10
        node.send_message(node.create_last_1_test_message("should be accepted (1)", global_time), address)
        yield 0.01
        times = [x for x, in self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert len(times) == 1
        assert global_time in times

        # send a message
        global_time = 11
        node.send_message(node.create_last_1_test_message("should be accepted (2)", global_time), address)
        yield 0.01
        times = [x for x, in self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert len(times) == 1
        assert global_time in times

        # send a message (older: should be dropped)
        node.send_message(node.create_last_1_test_message("should be dropped (1)", 8), address)
        yield 0.01
        times = [x for x, in self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert len(times) == 1
        assert global_time in times

        # as proof for the drop, the newest message should be sent back
        _, message = node.receive_message(addresses=[address], message_names=[u"last-1-test"])
        assert message.distribution.global_time == 11

        # send a message (duplicate: should be dropped)
        node.send_message(node.create_last_1_test_message("should be dropped (2)", global_time), address)
        yield 0.01
        times = [x for x, in self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert len(times) == 1
        assert global_time in times

        # send a message
        global_time = 12
        node.send_message(node.create_last_1_test_message("should be accepted (3)", global_time), address)
        yield 0.01
        times = [x for x, in self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert len(times) == 1
        assert global_time in times

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

    def last_9_nosequence_test(self):
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        message = community.get_meta_message(u"last-9-nosequence-test")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.01

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id)))
        assert len(times) == 0

        number_of_messages = 0
        for global_time in [21, 20, 28, 27, 22, 23, 24, 26, 25]:
            # send a message
            message = node.create_last_9_nosequence_test_message(str(global_time), global_time)
            node.send_message(message, address)
            number_of_messages += 1
            yield 0.01
            packet, = self._dispersy_database.execute(u"SELECT sync.packet FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.global_time = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, global_time, message.database_id)).next()
            assert str(packet) == message.packet
            times = [x for x, in self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
            dprint(sorted(times))
            assert len(times) == number_of_messages, (len(times), number_of_messages)
            assert global_time in times
        assert number_of_messages == 9, number_of_messages

        for global_time in [11, 12, 13, 19, 18, 17]:
            # send a message (older: should be dropped)
            node.send_message(node.create_last_9_nosequence_test_message(str(global_time), global_time), address)
            yield 0.01
            times = [x for x, in self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
            assert len(times) == 9, len(times)
            assert not global_time in times

        for global_time in [21, 20, 28, 27, 22, 23, 24, 26, 25]:
            # send a message (duplicate: should be dropped)
            message = node.create_last_9_nosequence_test_message("wrong content!", global_time)
            node.send_message(message, address)
            yield 0.01
            packet, = self._dispersy_database.execute(u"SELECT sync.packet FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.global_time = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, global_time, message.database_id)).next()
            assert not str(packet) == message.packet
            times = [x for x, in self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
            assert sorted(times) == range(20, 29), sorted(times)

        match_times = sorted(times[:])
        for global_time in [30, 35, 37, 31, 32, 34, 33, 36, 38, 45, 44, 43, 42, 41, 40, 39]:
            # send a message (should be added and old one removed)
            message = node.create_last_9_nosequence_test_message("wrong content!", global_time)
            node.send_message(message, address)
            match_times.pop(0)
            match_times.append(global_time)
            match_times.sort()
            yield 0.01
            packet, = self._dispersy_database.execute(u"SELECT sync.packet FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.global_time = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, global_time, message.database_id)).next()
            assert str(packet) == message.packet
            times = [x for x, in self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
            dprint(sorted(times))
            assert sorted(times) == match_times, sorted(times)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

    # def last_9_sequence_test(self):
    #     community = DebugCommunity.create_community(self._my_member)
    #     address = self._dispersy.socket.get_address()
    #     message = community.get_meta_message(u"last-9-sequence-test")

    #     # create node and ensure that SELF knows the node address
    #     node = DebugNode()
    #     node.init_socket()
    #     node.set_community(community)
    #     node.init_my_member()
    #     yield 0.01

    #     # should be no messages from NODE yet
    #     times = list(self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id)))
    #     assert len(times) == 0

    #     number_of_messages = 0
    #     for global_time in [21, 20, 28, 27, 22, 23, 24, 26, 25]:
    #         # send a message
    #         message = node.create_last_9_sequence_test_message(str(global_time), global_time)
    #         node.send_message(message, address)
    #         number_of_messages += 1
    #         yield 0.01
    #         packet, = self._dispersy_database.execute(u"SELECT packet FROM sync WHERE community = ? AND user = ? AND global_time = ? AND name = ?", (community.database_id, node.my_member.database_id, global_time, message.database_id)).next()
    #         assert str(packet) == message.packet
    #         times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
    #         dprint(sorted(times))
    #         assert len(times) == number_of_messages, (len(times), number_of_messages)
    #         assert global_time in times
    #     assert number_of_messages == 9, number_of_messages

    #     for global_time in [11, 12, 13, 19, 18, 17]:
    #         # send a message (older: should be dropped)
    #         node.send_message(node.create_last_9_sequence_test_message(str(global_time), global_time), address)
    #         yield 0.01
    #         times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
    #         assert len(times) == 9, len(times)
    #         assert not global_time in times

    #         # as proof for the drop, the newest message should be sent back
    #         for global_time in [20, 21, 22, 23, 25, 25, 26, 27, 28]:
    #             _, message = node.receive_message(addresses=[address], message_names=[u"last-9-sequence-test"])
    #             assert message.distribution.global_time == global_time

    #     for global_time in [21, 20, 28, 27, 22, 23, 24, 26, 25]:
    #         # send a message (duplicate: should be dropped)
    #         message = node.create_last_9_sequence_test_message("wrong content!", global_time)
    #         node.send_message(message, address)
    #         yield 0.01
    #         packet, = self._dispersy_database.execute(u"SELECT packet FROM sync WHERE community = ? AND user = ? AND global_time = ? AND name = ?", (community.database_id, node.my_member.database_id, global_time, message.database_id)).next()
    #         assert not str(packet) == message.packet
    #         times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
    #         assert sorted(times) == range(20, 29), sorted(times)

    #     match_times = sorted(times[:])
    #     for global_time in [30, 35, 37, 31, 32, 34, 33, 36, 38, 45, 44, 43, 42, 41, 40, 39]:
    #         # send a message (should be added and old one removed)
    #         message = node.create_last_9_sequence_test_message("wrong content!", global_time)
    #         node.send_message(message, address)
    #         match_times.pop(0)
    #         match_times.append(global_time)
    #         match_times.sort()
    #         yield 0.01
    #         packet, = self._dispersy_database.execute(u"SELECT packet FROM sync WHERE community = ? AND user = ? AND global_time = ? AND name = ?", (community.database_id, node.my_member.database_id, global_time, message.database_id)).next()
    #         assert str(packet) == message.packet
    #         times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
    #         dprint(sorted(times))
    #         assert sorted(times) == match_times, sorted(times)

    #     # cleanup
    #     community.create_dispersy_destroy_community(u"hard-kill")

class DispersySignatureScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = MyMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)

        self.caller(self.double_signed_timeout)
        self.caller(self.double_signed_response)
        self.caller(self.triple_signed_timeout)
        self.caller(self.triple_signed_response)

    def double_signed_timeout(self):
        """
        SELF will request a signature from NODE.  Node will ignore this request and SELF should get
        a timeout on the signature request after a few seconds.
        """
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        container = {"timeout":0}

        # create node and ensure that SELF knows the node address
        node = Node()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.01

        dprint("SELF requests NODE to double sign")
        def on_response(response):
            assert response is None
            container["timeout"] += 1
        request = community.create_double_signed_text("Accept=<does not reach this point>", Member.get_instance(node.my_member.public_key), on_response, (), 3.0)
        yield 0.01

        dprint("NODE receives dispersy-signature-request message")
        _, message = node.receive_message(addresses=[address], message_names=[u"dispersy-signature-request"])
        # do not send a response

        # should time out
        for counter in range(4):
            dprint("waiting... ", 4 - counter)
            yield 1.0
        yield 0.1

        dprint("SELF must have timed out by now")
        assert container["timeout"] == 1, container["timeout"]

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

    def double_signed_response(self):
        ec = ec_generate_key(u"low")
        my_member = MyMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        container = {"response":0}

        # create node and ensure that SELF knows the node address
        node = Node()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.01

        # SELF requests NODE to double sign
        def on_response(response):
            assert container["response"] == 0, container["response"]
            assert request.authentication.is_signed
            container["response"] += 1
        request = community.create_double_signed_text("Accept=False", Member.get_instance(node.my_member.public_key), on_response, (), 3.0)
        yield 0.01

        # receive dispersy-signature-request message
        address, message = node.receive_message(addresses=[address], message_names=[u"dispersy-signature-request"])
        submsg = message.payload.message
        second_signature_offset = len(submsg.packet) - community.my_member.signature_length
        first_signature_offset = second_signature_offset - node.my_member.signature_length
        assert submsg.packet[second_signature_offset:] == "\x00" * node.my_member.signature_length
        signature = node.my_member.sign(submsg.packet, length=first_signature_offset)

        # send dispersy-signature-response message
        request_id = hashlib.sha1(request.packet).digest()
        global_time = community._timeline.global_time
        node.send_message(node.create_dispersy_signature_response_message(request_id, signature, global_time, address), address)

        # should not time out
        for counter in range(4):
            dprint("waiting... ", 4 - counter)
            yield 1.0
        yield 0.1

        assert container["response"] == 1, container["response"]

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

    def triple_signed_timeout(self):
        ec = ec_generate_key(u"low")
        my_member = MyMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        container = {"timeout":0}

        # create node and ensure that SELF knows the node address
        node1 = Node()
        node1.init_socket()
        node1.set_community(community)
        node1.init_my_member()
        yield 0.01

        # create node and ensure that SELF knows the node address
        node2 = Node()
        node2.init_socket()
        node2.set_community(community)
        node2.init_my_member()
        yield 0.01

        # SELF requests NODE1 and NODE2 to double sign
        def on_response(response):
            assert response is None
            container["timeout"] += 1
        request = community.create_triple_signed_text("Hello World!", Member.get_instance(node1.my_member.public_key), Member.get_instance(node2.my_member.public_key), on_response, (), 3.0)
        yield 0.01

        # receive dispersy-signature-request message
        _, message = node1.receive_message(addresses=[address], message_names=[u"dispersy-signature-request"])
        _, message = node2.receive_message(addresses=[address], message_names=[u"dispersy-signature-request"])
        # do not send a response

        # should time out
        for counter in range(4):
            dprint("waiting... ", 4 - counter)
            yield 1.0
        yield 0.1

        assert container["timeout"] == 1, container["timeout"]

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

    def triple_signed_response(self):
        ec = ec_generate_key(u"low")
        my_member = MyMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        container = {"response":0}

        # create node and ensure that SELF knows the node address
        node1 = Node()
        node1.init_socket()
        node1.set_community(community)
        node1.init_my_member()
        yield 0.2

        # create node and ensure that SELF knows the node address
        node2 = Node()
        node2.init_socket()
        node2.set_community(community)
        node2.init_my_member()
        yield 0.2

        # SELF requests NODE1 and NODE2 to add their signature
        def on_response(response):
            assert container["response"] == 0 or request.authentication.is_signed
            container["response"] += 1
        request = community.create_triple_signed_text("Hello World!", Member.get_instance(node1.my_member.public_key), Member.get_instance(node2.my_member.public_key), on_response, (), 3.0)

        # receive dispersy-signature-request message
        address, message = node1.receive_message(addresses=[address], message_names=[u"dispersy-signature-request"])
        submsg = message.payload.message
        third_signature_offset = len(submsg.packet) - node2.my_member.signature_length
        second_signature_offset = third_signature_offset - node1.my_member.signature_length
        first_signature_offset = second_signature_offset - community.my_member.signature_length
        assert submsg.packet[second_signature_offset:third_signature_offset] == "\x00" * node1.my_member.signature_length
        signature1 = node1.my_member.sign(submsg.packet, length=first_signature_offset)

        # send dispersy-signature-response message
        request_id = hashlib.sha1(request.packet).digest()
        global_time = community._timeline.global_time
        node1.send_message(node1.create_dispersy_signature_response_message(request_id, signature1, global_time, address), address)

        # receive dispersy-signature-request message
        address, message = node2.receive_message(addresses=[address], message_names=[u"dispersy-signature-request"])
        submsg = message.payload.message
        third_signature_offset = len(submsg.packet) - node2.my_member.signature_length
        second_signature_offset = third_signature_offset - node1.my_member.signature_length
        first_signature_offset = second_signature_offset - community.my_member.signature_length
        assert submsg.packet[third_signature_offset:] == "\x00" * node2.my_member.signature_length
        signature2 = node2.my_member.sign(submsg.packet, length=first_signature_offset)

        # send dispersy-signature-response message
        request_id = hashlib.sha1(request.packet).digest()
        global_time = community._timeline.global_time
        node2.send_message(node2.create_dispersy_signature_response_message(request_id, signature2, global_time, address), address)

        # should not time out
        for counter in range(4):
            dprint("waiting... ", 4 - counter)
            yield 1.0
        yield 0.1

        assert container["response"] == 2, container["response"]

class DispersySubjectiveSetScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = MyMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)

        self.caller(self.storage)
        self.caller(self.full_sync)
        self.caller(self.subjective_set_request)

    def storage(self):
        """
         - a message from a member in the subjective set MUST be stored
         - a message from a member NOT in the subjective set MUST NOT be stored
        """
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        message = community.get_meta_message(u"subjective-set-text")

        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.01

        # node is NOT in self._my_member's subjective set.  the message MUST NOT be stored
        global_time = 10
        node.send_message(node.create_subjective_set_text_message("Must not be stored", global_time), address)
        yield 0.01
        times = [global_time for global_time, in self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert times == [], times

        # node is in self._my_member's subjective set.  the message MUST be stored
        community.create_dispersy_subjective_set(message.destination.cluster, [node.my_member])
        global_time = 20
        node.send_message(node.create_subjective_set_text_message("Must be stored", global_time), address)
        yield 0.01
        times = [global_time for global_time, in self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert times == [global_time]

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

    def full_sync(self):
        """
        Using full sync check that:
         - messages from a member in the subjective set are sent back
         - messages from a member NOT in the set are NOT sent back
        """
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        meta_message = community.get_meta_message(u"subjective-set-text")

        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.01

        # make available the subjective set
        subjective_set = BloomFilter(100, 0.1)
        subjective_set.add(node.my_member.public_key)
        node.send_message(node.create_dispersy_subjective_set_message(meta_message.destination.cluster, subjective_set, 10), address)
        yield 0.01

        # SELF will store and forward for NODE
        community.create_dispersy_subjective_set(meta_message.destination.cluster, [node.my_member])
        global_time = 20
        node.send_message(node.create_subjective_set_text_message("Must be stored", global_time), address)
        yield 0.01
        times = [global_time for global_time, in self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, meta_message.database_id))]
        assert times == [global_time]

        # a dispersy-sync message MUST return the message that was just sent
        node.send_message(node.create_dispersy_sync_message(10, 0, [], 20), address)
        yield 0.01
        _, message = node.receive_message(addresses=[address], message_names=[u"subjective-set-text"])
        assert message.distribution.global_time == global_time

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")

    def subjective_set_request(self):
        """
        When we receive a dispersy-sync message we NEED to have the dispersy-subjective-set message
        to be able to send back messages that use the SubjectiveDestination policy.

        We will test that a dispersy-subjective-set-request is sent when we are missing this
        information.  Some important characteristics:

         - When a dispersy-subjective-set-request is sent, no other missing packets are sent.  None
           whatsoever.  The entire dispery-sync message is paused and reprocessed once the
           dispersy-subjective-set is received.
        """
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        meta_message = community.get_meta_message(u"subjective-set-text")

        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.01

        # SELF will store and forward for NODE
        community.create_dispersy_subjective_set(meta_message.destination.cluster, [node.my_member])
        global_time = 20
        node.send_message(node.create_subjective_set_text_message("Must be stored", global_time), address)
        yield 0.01
        times = [global_time for global_time, in self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?", (community.database_id, node.my_member.database_id, meta_message.database_id))]
        assert times == [global_time]

        # a dispersy-sync message MUST return a dispersy-subjective-set-request message
        node.send_message(node.create_dispersy_sync_message(10, 0, [], 20), address)
        yield 0.01
        _, message = node.receive_message(addresses=[address], message_names=[u"dispersy-subjective-set-request", u"subjective-set-text"])
        assert message.name == u"dispersy-subjective-set-request", "should NOT sent back the subjective-set-text"
        assert message.payload.cluster == meta_message.destination.cluster
        try:
            _, message = node.receive_message(addresses=[address], message_names=[u"dispersy-subjective-set-request", u"subjective-set-text"])
            assert False, "should be no more messages"
        except:
            pass

        # make available the subjective set
        subjective_set = BloomFilter(100, 0.1)
        subjective_set.add(node.my_member.public_key)
        node.send_message(node.create_dispersy_subjective_set_message(meta_message.destination.cluster, subjective_set, 10), address)
        yield 0.01

        # the dispersy-sync message should now be processed (again) and result in the missing
        # subjective-set-text message
        _, message = node.receive_message(addresses=[address], message_names=[u"subjective-set-text"])
        assert message.distribution.global_time == global_time

# class DispersySimilarityScript(ScriptBase):
#     def run(self):
#         ec = ec_generate_key(u"low")
#         self._my_member = MyMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)

#         # self.caller(self.similarity_check_incoming_packets)
#         self.caller(self.similarity_fullsync)
#         self.caller(self.similarity_lastsync)
#         self.caller(self.similarity_missing_sim)

#     def similarity_check_incoming_packets(self):
#         """
#         Check functionallity of accepting or rejecting
#         incoming packets based on similarity of the user
#         sending the packet
#         """
#         # create community
#         # taste-aware-record  uses SimilarityDestination with the following parameters
#         # 16 Bits Bloom Filter, minimum 6, maximum 10, threshold 12
#         community = DebugCommunity.create_community(self._my_member)
#         address = self._dispersy.socket.get_address()
#         container = {"timeout":0}

#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b11111111), chr(0b00000000)), 0)
#         self._dispersy._database.execute(u"INSERT INTO similarity (community, user, cluster, similarity) VALUES (?, ?, ?, ?)",
#                                          (community.database_id, community._my_member.database_id, 1, buffer(str(bf))))

#         # create first node - node-01
#         node = DebugNode()
#         node.init_socket()
#         node.set_community(community)
#         node.init_my_member()
#         yield 0.01

#         ##
#         ## Similar Nodes
#         ##

#         # create similarity for node-01
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b11111111), chr(0b00000000)), 0)
#         node.send_message(node.create_dispersy_similarity_message(1, community.database_id, bf, 20), address)
#         yield 0.01

#         msg = node.create_taste_aware_message(5, 10, 1)
#         msg_blob = node.encode_message(msg)
#         node.send_message(msg, address)
#         yield 0.01

#         dprint(len(msg_blob), "-", len(msg.packet))
#         dprint(msg_blob.encode("HEX"))
#         dprint(msg.packet.encode("HEX"))
#         assert msg_blob == msg.packet

#         dprint(msg_blob.encode("HEX"))

#         with self._dispersy.database as execute:
#             d, = execute(u"SELECT count(*) FROM sync WHERE packet = ?", (buffer(msg.packet),)).next()
#             assert d == 1, d

#         ##
#         ## Not Similar Nodes
#         ##

#         # create similarity for node-01
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b11111111), chr(0b11111111)), 0)
#         node.send_message(node.create_dispersy_similarity_message(1, community.database_id, bf, 30), address)
#         yield 0.01

#         msg = node.create_taste_aware_message(5, 20, 2)
#         msg_blob = node.encode_message(msg)
#         node.send_message(msg, address)
#         yield 0.01

#         with self._dispersy.database as execute:
#             d,= execute(u"SELECT count(*) FROM sync WHERE packet = ?", (buffer(str(msg_blob)),)).next()
#             assert d == 0

#     def similarity_fullsync(self):
#         # create community
#         # taste-aware-record  uses SimilarityDestination with the following parameters
#         # 16 Bits Bloom Filter, minimum 6, maximum 10, threshold 12
#         ec = ec_generate_key(u"low")
#         my_member = MyMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)
#         community = DebugCommunity.create_community(self._my_member)
#         address = self._dispersy.socket.get_address()

#         # setting similarity for self
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b11110000), chr(0b00000000)), 0)
#         self._dispersy._database.execute(u"INSERT INTO similarity (community, user, cluster, similarity) VALUES (?, ?, ?, ?)",
#                                          (community.database_id, community._my_member.database_id, 1, buffer(str(bf))))

#         # create first node - node-01
#         node = DebugNode()
#         node.init_socket()
#         node.set_community(community)
#         node.init_my_member()
#         yield 0.01

#         # create second node - node-02
#         node2 = DebugNode()
#         node2.init_socket()
#         node2.set_community(community)
#         node2.init_my_member()
#         yield 0.01

#         ##
#         ## Similar Nodes Threshold 12 Similarity 14
#         ##
#         dprint("Testing similar nodes")

#         # create similarity for node-01
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b11110000), chr(0b00000000)), 0)
#         node.send_message(node.create_dispersy_similarity_message(1, community.database_id, bf, 20), address)
#         yield 0.01

#         # create similarity for node-02
#         # node node-02 has 14/16 same bits with node-01
#         # ABOVE threshold
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b10111000), chr(0b00000000)), 0)
#         node2.send_message(node2.create_dispersy_similarity_message(1, community.database_id, bf, 20), address)
#         yield 0.01

#         # node-01 creates and sends a message to 'self'
#         node.send_message(node.create_taste_aware_message(5, 10, 1), address)
#         yield 0.01

#         # node-02 sends an sync message with an empty bloomfilter
#         # to 'self'. It should collect the message
#         node2.send_message(node2.create_dispersy_sync_message(1, 100, [], 3), address)
#         yield 0.01

#         # should receive a message
#         _, message = node2.receive_message(addresses=[address], message_names=[u"taste-aware-record"])

#         ##
#         ## Similar Nodes Threshold 12 Similarity 12
#         ##
#         dprint("Testing similar nodes 2")

#         # create similarity for node-02
#         # node node-02 has 12/16 same bits with node-01
#         # ABOVE threshold
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b11110011), chr(0b11000000)), 0)
#         node2.send_message(node2.create_dispersy_similarity_message(1, community.database_id, bf, 30), address)
#         yield 0.01

#         # node-02 sends an sync message with an empty bloomfilter
#         # to 'self'. It should collect the message
#         node2.send_message(node2.create_dispersy_sync_message(1, 100, [], 3), address)
#         yield 0.01

#         # should receive a message
#         _, message = node2.receive_message(addresses=[address], message_names=[u"taste-aware-record"])

#         ##
#         ## Not Similar Nodes Threshold 12 Similarity 2
#         ##
#         dprint("Testing not similar nodes")

#         # create similarity for node-02
#         # node node-02 has 2/16 same bits with node-01
#         # BELOW threshold
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b00001111), chr(0b11111100)), 0)
#         node2.send_message(node2.create_dispersy_similarity_message(1, community.database_id, bf, 40), address)
#         yield 0.01

#         # node-02 sends an sync message with an empty bloomfilter
#         # to 'self'. It should collect the message
#         node2.send_message(node2.create_dispersy_sync_message(1, 100, [], 3), address)
#         yield 0.01

#         # should NOT receive a message
#         try:
#             _, message = node2.receive_message(addresses=[address], message_names=[u"taste-aware-record"])
#             assert False
#         except:
#             pass

#         yield 1.0
#         ##
#         ## Not Similar Nodes Threshold 12 Similarity 11
#         ##
#         dprint("Testing not similar nodes 2")

#         # create similarity for node-02
#         # node node-02 has 11/16 same bits with node-01
#         # BELOW threshold
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b11110010), chr(0b00110011)), 0)
#         node2.send_message(node2.create_dispersy_similarity_message(1, community.database_id, bf, 50), address)
#         yield 0.01

#         # node-02 sends an sync message with an empty bloomfilter
#         # to 'self'. It should collect the message
#         node2.send_message(node2.create_dispersy_sync_message(1, 100, [], 3), address)
#         yield 0.01

#         # should NOT receive a message
#         try:
#             _, message = node2.receive_message(addresses=[address], message_names=[u"taste-aware-record"])
#             assert False
#         except:
#             pass

#     def similarity_lastsync(self):
#         # create community
#         # taste-aware-record  uses SimilarityDestination with the following parameters
#         # 16 Bits Bloom Filter, minimum 6, maximum 10, threshold 12
#         ec = ec_generate_key(u"low")
#         my_member = MyMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)
#         community = DebugCommunity.create_community(self._my_member)
#         address = self._dispersy.socket.get_address()
#         container = {"timeout":0}

#         # setting similarity for self
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b11110000), chr(0b00000000)), 0)
#         self._dispersy._database.execute(u"INSERT INTO similarity (community, user, cluster, similarity) VALUES (?, ?, ?, ?)",
#                                          (community.database_id, community._my_member.database_id, 2, buffer(str(bf))))

#         # create first node - node-01
#         node = DebugNode()
#         node.init_socket()
#         node.set_community(community)
#         node.init_my_member()
#         yield 0.01

#         # create second node - node-02
#         node2 = DebugNode()
#         node2.init_socket()
#         node2.set_community(community)
#         node2.init_my_member()
#         yield 0.01

#         ##
#         ## Similar Nodes
#         ##
#         dprint("Testing similar nodes")

#         # create similarity for node-01
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b11110000), chr(0b00000000)), 0)
#         node.send_message(node.create_dispersy_similarity_message(2, community.database_id, bf, 20), address)
#         yield 0.01

#         # create similarity for node-02
#         # node node-02 has 15/16 same bits with node-01
#         # ABOVE threshold
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b10111000), chr(0b00000000)), 0)
#         node2.send_message(node2.create_dispersy_similarity_message(2, community.database_id, bf, 20), address)
#         yield 0.01

#         # node-01 creates and sends a message to 'self'
#         node.send_message(node.create_taste_aware_message_last(5, 30, 1), address)

#         # node-02 sends a sync message with an empty bloomfilter
#         # to 'self'. It should collect the message
#         node2.send_message(node2.create_dispersy_sync_message(1, 100, [], 3), address)
#         yield 0.01

#         # receive a message
#         _, message = node2.receive_message(addresses=[address], message_names=[u"taste-aware-record-last"])

#         ##
#         ## Not Similar Nodes
#         ##
#         dprint("Testing not similar nodes")

#         # create similarity for node-02
#         # node node-02 has 11/16 same bits with node-01
#         # BELOW threshold
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b00100011), chr(0b00000000)), 0)
#         node2.send_message(node2.create_dispersy_similarity_message(2, community.database_id, bf, 30), address)
#         yield 0.01

#         # node-02 sends an sync message with an empty bloomfilter
#         # to 'self'. It should collect the message
#         node2.send_message(node2.create_dispersy_sync_message(1, 100, [], 3), address)
#         yield 0.01

#         # receive a message
#         try:
#             _, message = node2.receive_message(addresses=[address], message_names=[u"taste-aware-record-last"])
#             assert False
#         except:
#             pass

#     def similarity_missing_sim(self):
#         # create community
#         # taste-aware-record  uses SimilarityDestination with the following parameters
#         # 16 Bits Bloom Filter, minimum 6, maximum 10, threshold 12
#         ec = ec_generate_key(u"low")
#         my_member = MyMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)
#         community = DebugCommunity.create_community(self._my_member)
#         address = self._dispersy.socket.get_address()
#         container = {"timeout":0}

#         # setting similarity for self
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b11110000), chr(0b00000000)), 0)
#         self._dispersy._database.execute(u"INSERT INTO similarity (community, user, cluster, similarity) VALUES (?, ?, ?, ?)",
#                                          (community.database_id, community._my_member.database_id, 1, buffer(str(bf))))

#         # create first node - node-01
#         node = DebugNode()
#         node.init_socket()
#         node.set_community(community)
#         node.init_my_member()
#         yield 0.01

#         # create similarity for node-01
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b11110000), chr(0b00000000)), 0)
#         node.send_message(node.create_dispersy_similarity_message(1, community.database_id, bf, 20), address)
#         yield 0.01

#         # create second node - node-02
#         node2 = DebugNode()
#         node2.init_socket()
#         node2.set_community(community)
#         node2.init_my_member()
#         yield 0.01

#         # node-01 creates and sends a message to 'self'
#         node.send_message(node.create_taste_aware_message(5, 10, 1), address)
#         yield 0.01

#         # node-02 sends a sync message with an empty bloomfilter
#         # to 'self'. It should collect the message
#         node2.send_message(node2.create_dispersy_sync_message(1, 100, [], 3), address)
#         yield 0.01

#         # because 'self' does not have our similarity
#         # we should first receive a 'dispersy-similarity-request' message
#         # and 'synchronize' e.g. send our similarity
#         _, message = node2.receive_message(addresses=[address], message_names=[u"dispersy-similarity-request"])

#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b10111000), chr(0b00000000)), 0)
#         node2.send_message(node2.create_dispersy_similarity_message(1, community.database_id, bf, 20), address)
#         yield 0.01

#         # receive the taste message
#         _, message = node2.receive_message(addresses=[address], message_names=[u"taste-aware-record"])
#         assert  message.payload.number == 5

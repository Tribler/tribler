# Python 2.5 features
from __future__ import with_statement

"""
Run some python code, usually to test one or more features.
"""

from hashlib import sha1
from random import random
from struct import pack, unpack_from
from time import clock, time
import gc
import hashlib
import math
import types

from authentication import MultiMemberAuthentication
from bloomfilter import BloomFilter
from community import Community
from conversion import BinaryConversion
from crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin
from debug import Node
from destination import CommunityDestination
from dispersy import Dispersy
from dispersydatabase import DispersyDatabase
from dprint import dprint
from lencoder import log
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
                delay = 0.11
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

class ScenarioScriptBase(ScriptBase):
    #TODO: all bartercast references should be converted to some universal style    
    def __init__(self, script, name, logfile, **kargs):
        ScriptBase.__init__(self, script, name, **kargs)
        
        self._timestep = float(kargs.get('timestep', 1.0))
        self._stepcount = 0
        self._starting_timestamp = float(kargs.get('starting_timestamp', time()))
        self._logfile = logfile

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
        now = time()
        expected_time = self._starting_timestamp + (self._timestep * self._stepcount)
        st = max(0.0, expected_time - now) * random()
        log(self._logfile, "sleep", delay=st, diff=expected_time - now, stepcount=self._stepcount)
        return st
    
    def join_community(self, my_member):
        pass
    
    def execute_scenario_cmds(self, commands):
        pass

    def run(self):
        if __debug__: log(self._logfile, "start-barter-script")

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
        if __debug__: log(self._logfile, "read-config-done")

        # create mymember
        my_member = MyMember(public_key, private_key, sync_with_database=True)
        dprint(my_member)

        # join the community with the newly created member
        self._community = self.join_community(my_member)
        dprint("Joined barter community ", self._community._my_member)
        if __debug__:
            log(self._logfile, "joined-barter-community")
            log(self._logfile, "barter-community-property", name="sync_interval", value=self._community.dispersy_sync_interval)
            log(self._logfile, "barter-community-property", name="sync_member_count", value=self._community.dispersy_sync_member_count)
            log(self._logfile, "barter-community-property", name="sync_response_limit", value=self._community.dispersy_sync_response_limit)
            log(self._logfile, "barter-community-property", name="timestep", value=self._timestep)

        yield 2.0

        # create a dispersy-identity message for my_member and the
        # self._community community.  This message will be sent to all
        # the peers in the 'peers' file to (a) add them to our candidate
        # table (b) let them know about our existance and our public
        # key
        meta = self._community.get_meta_message(u"dispersy-identity")
        message = meta.implement(meta.authentication.implement(meta.community._my_member),
                                 meta.distribution.implement(meta.community.claim_global_time()),
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
            #remove original tracker
            execute(u"DELETE FROM candidate where community=0")
            
            with open('data/peers') as file:
                for line in file:
                    name, ip, port, public_key, _ = line.split(' ', 4)
                    if __debug__:
                        _peer_counter += 1
                        log(self._logfile, "read-peer-config", position=_peer_counter, name=name, ip=ip, port=port)
                    if name == my_name: continue
                    public_key = public_key.decode('HEX')
                    port = int(port)

                    #self._dispersy._send([(ip, port)], [message.packet])
                    
                    #inserting all peers from data/peer as 'trackers'
                    execute(u"INSERT OR IGNORE INTO candidate(community, host, port, incoming_time, outgoing_time) VALUES(?, ?, ?, DATETIME(), '2010-01-01 00:00:00')", (0, unicode(ip), port))
                    execute(u"INSERT OR IGNORE INTO user(mid, public_key, host, port) VALUES(?, ?, ?, ?)", (buffer(sha1(public_key).digest()), buffer(public_key), unicode(ip), port))
                    
                    #if __debug__:
                    #    log("barter.log", "mid_add", mid=sha1(public_key).digest())
        if __debug__:
            log(self._logfile, "done-reading-peers")

        yield 2.0

        # open the scenario files, as generated from Mircea's Scenario
        # Generator
        scenario_fp = open('data/bartercast.log')
        availability_fp = open('data/availability.log')

        self._stepcount = 0

        # wait until we reach the starting time
        yield self.sleep()

        self._stepcount = 1

        # start the scenario
        while True:
            # get commands
            scenario_cmds = self.get_commands_from_fp(scenario_fp, self._stepcount)
            availability_cmds = self.get_commands_from_fp(availability_fp, self._stepcount)

            # if there are no commands exit the while loop
            if scenario_cmds == -1 and availability_cmds == -1:
                if __debug__: log(self._logfile, "no-commands")
                break
            else:
                # if there is a start in the avaibility_cmds then go
                # online
                if availability_cmds != -1 and 'start' in availability_cmds:
                    self.set_online()

                # if there are barter_cmds then execute them
                if scenario_cmds != -1:
                    self.execute_scenario_cmds(scenario_cmds)

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

class DispersyClassificationScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = MyMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)

        self.caller(self.load_no_communities)
        self.caller(self.load_one_communities)
        self.caller(self.load_two_communities)
        self.caller(self.unloading_community)

        self.caller(self.enable_autoload)
        self.caller(self.enable_disable_autoload)

        self.caller(self.reclassify_unloaded_community)
        self.caller(self.reclassify_loaded_community)

    def reclassify_unloaded_community(self):
        """
        Load a community, reclassify it, load all communities of that classification to check.
        """
        class ClassTestA(DebugCommunity):
            pass

        class ClassTestB(DebugCommunity):
            pass

        # no communities should exist
        assert ClassTestA.load_communities() == []
        assert ClassTestB.load_communities() == []

        # create community
        cid = str((ClassTestA.get_classification() + "A" * 20)[:20])
        self._dispersy_database.execute(u"INSERT INTO community (user, classification, cid) VALUES (?, ?, ?)",
                                        (self._my_member.database_id, ClassTestA.get_classification(), buffer(cid)))

        # reclassify
        community = self._dispersy.reclassify_community(cid, ClassTestB)
        assert isinstance(community, ClassTestB)
        assert community.cid == cid
        try:
            classification, = self._dispersy_database.execute(u"SELECT classification FROM community WHERE cid = ?", (buffer(cid),)).next()
        except StopIteration:
            assert False
        assert classification == ClassTestB.get_classification()

        # cleanup
        community.unload_community()
        yield 0.0

    def reclassify_loaded_community(self):
        """
        Load a community, reclassify it, load all communities of that classification to check.
        """
        class ClassTestC(DebugCommunity):
            pass

        class ClassTestD(DebugCommunity):
            pass

        # no communities should exist
        assert ClassTestC.load_communities() == []
        assert ClassTestD.load_communities() == []

        # create community
        community_c = ClassTestC.create_community(self._my_member)
        assert len(list(self._dispersy_database.execute(u"SELECT * FROM community WHERE classification = ?", (ClassTestC.get_classification(),)))) == 1

        # reclassify
        community_d = self._dispersy.reclassify_community(community_c, ClassTestD)
        assert isinstance(community_d, ClassTestD)
        assert community_c.cid == community_d.cid
        try:
            classification, = self._dispersy_database.execute(u"SELECT classification FROM community WHERE cid = ?", (buffer(community_d.cid),)).next()
        except StopIteration:
            assert False
        assert classification == ClassTestD.get_classification()

        # cleanup
        community_d.unload_community()
        yield 0.0

    def load_no_communities(self):
        """
        Try to load communities of a certain classification while there are no such communities.
        """
        class ClassificationLoadNoCommunities(DebugCommunity):
            pass
        assert ClassificationLoadNoCommunities.load_communities() == []
        yield 0.0

    def load_one_communities(self):
        """
        Try to load communities of a certain classification while there is exactly one such
        community available.
        """
        class ClassificationLoadOneCommunities(DebugCommunity):
            pass

        # no communities should exist
        assert ClassificationLoadOneCommunities.load_communities() == []

        # create one community
        cid = ClassificationLoadOneCommunities.get_classification()[:20]
        self._dispersy_database.execute(u"INSERT INTO community (user, classification, cid) VALUES (?, ?, ?)",
                                        (self._my_member.database_id, ClassificationLoadOneCommunities.get_classification(), buffer(cid)))

        # load one community
        communities = ClassificationLoadOneCommunities.load_communities()
        assert len(communities) == 1
        assert isinstance(communities[0], ClassificationLoadOneCommunities)

        # cleanup
        communities[0].unload_community()
        yield 0.0

    def load_two_communities(self):
        """
        Try to load communities of a certain classification while there is exactly two such
        community available.
        """
        class LoadTwoCommunities(DebugCommunity):
            pass

        # no communities should exist
        assert LoadTwoCommunities.load_communities() == []

        # create two community
        cid = ("#1" + LoadTwoCommunities.get_classification())[:20]
        self._dispersy_database.execute(u"INSERT INTO community (user, classification, cid) VALUES (?, ?, ?)",
                                        (self._my_member.database_id, LoadTwoCommunities.get_classification(), buffer(cid)))
        cid = ("#2" + LoadTwoCommunities.get_classification())[:20]
        self._dispersy_database.execute(u"INSERT INTO community (user, classification, cid) VALUES (?, ?, ?)",
                                        (self._my_member.database_id, LoadTwoCommunities.get_classification(), buffer(cid)))

        # load two community
        communities = LoadTwoCommunities.load_communities()
        assert len(communities) == 2, len(communities)
        assert isinstance(communities[0], LoadTwoCommunities)
        assert isinstance(communities[1], LoadTwoCommunities)

        # cleanup
        communities[0].unload_community()
        communities[1].unload_community()
        yield 0.0

    def unloading_community(self):
        """
        Test that calling community.unload_community() eventually results in a call to
        community.__del__().
        """
        class ClassificationUnloadingCommunity(DebugCommunity):
            pass

        cid = ClassificationUnloadingCommunity.create_community(self._my_member).cid
        assert isinstance(self._dispersy.get_community(cid), ClassificationUnloadingCommunity)
        assert len([x for x in gc.get_objects() if isinstance(x, ClassificationUnloadingCommunity)]) == 1

        # unload the community
        self._dispersy.get_community(cid).unload_community()
        try:
            self._dispersy.get_community(cid, auto_load=False)
            assert False
        except KeyError:
            pass

        # must be garbage collected
        for i in range(10):
            dprint("waiting... ", i)
            gc.collect()
            if len([x for x in gc.get_objects() if isinstance(x, ClassificationUnloadingCommunity)]) == 0:
                break
            else:
                yield 1.0
        assert len([x for x in gc.get_objects() if isinstance(x, ClassificationUnloadingCommunity)]) == 0

        # load the community for cleanup
        community = ClassificationUnloadingCommunity.load_community(cid, "")
        assert len([x for x in gc.get_objects() if isinstance(x, ClassificationUnloadingCommunity)]) == 1

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

    def enable_autoload(self):
        """
        - Create community
        - Enable auto-load (should be enabled by default)
        - Unload community
        - Send community message
        - Verify that the community got auto-loaded
        """
        # create community
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        message = community.get_meta_message(u"full-sync-text")

        # create node
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member(candidate=False)
        yield 0.11

        dprint("verify auto-load is enabled (default)")
        assert community.dispersy_auto_load == True
        yield 0.11

        dprint("unload community")
        community.unload_community()
        try:
            self._dispersy.get_community(community.cid, auto_load=False)
            assert False
        except KeyError:
            pass
        yield 0.11

        dprint("send community message")
        global_time = 10
        node.send_message(node.create_full_sync_text_message("Should auto-load", global_time), address)
        yield 0.11

        dprint("verify that the community got auto-loaded")
        try:
            self._dispersy.get_community(community.cid)
        except KeyError:
            assert False
        # verify that the message was received
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert global_time in times
        yield 0.11

        dprint("cleanup")
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

    def enable_disable_autoload(self):
        """
        - Create community
        - Enable auto-load (should be enabled by default)
        - Unload community
        - Send community message
        - Verify that the community got auto-loaded
        - Disable auto-load
        - Send community message
        - Verify that the community did NOT get auto-loaded
        """
        # create community
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        message = community.get_meta_message(u"full-sync-text")

        # create node
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member(candidate=False)
        yield 0.11

        dprint("verify auto-load is enabled (default)")
        assert community.dispersy_auto_load == True
        yield 0.11

        dprint("unload community")
        community.unload_community()
        try:
            self._dispersy.get_community(community.cid, auto_load=False)
            assert False
        except KeyError:
            pass
        yield 0.11

        dprint("send community message")
        global_time = 10
        node.send_message(node.create_full_sync_text_message("Should auto-load", global_time), address)
        yield 0.11

        dprint("verify that the community got auto-loaded")
        try:
            self._dispersy.get_community(community.cid)
        except KeyError:
            assert False
        # verify that the message was received
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert global_time in times
        yield 0.11

        dprint("disable auto-load")
        community.dispersy_auto_load = False
        assert community.dispersy_auto_load == False
        yield 0.11

        dprint("unload community")
        community.unload_community()
        try:
            self._dispersy.get_community(community.cid, auto_load=False)
            assert False
        except KeyError:
            pass
        yield 0.11

        dprint("send community message")
        global_time = 11
        node.send_message(node.create_full_sync_text_message("Should not auto-load", global_time), address)
        yield 0.11

        dprint("verify that the community did not get auto-loaded")
        try:
            self._dispersy.get_community(community.cid, auto_load=False)
            assert False
        except KeyError:
            pass
        # verify that the message was NOT received
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert not global_time in times
        yield 0.11

        dprint("cleanup")
        DebugCommunity.load_community(community.cid, "")
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

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
        yield 0.11

        dprint("master_member: ", community.master_member.database_id, ", ", community.master_member.mid.encode("HEX"))
        dprint("    my_member: ", community.my_member.database_id, ", ", community.my_member.mid.encode("HEX"))

        # check if we are still allowed to send the message
        message = community.create_dispersy_destroy_community(u"hard-kill", store=False, update=False, forward=False)
        assert message.authentication.member == self._my_member
        result = list(message.check_callback([message]))
        assert result == [message], "check_... methods should return a generator with the accepted messages"

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

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
        yield 0.11

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
        community.unload_community()

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

        self._dispersy.detach_community(community)
        yield 0.11

        # load the same community and see if the same permissions are loaded
        communities = LoadingCommunityTestCommunity.load_communities()
        assert len(communities) == 1

        # check if we are still allowed to send the message
        message = community.create_dispersy_destroy_community(u"hard-kill", store=False, update=False, forward=False)
        assert community._timeline.check(message)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

class DispersyCandidateScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = MyMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)

        self.caller(self.incoming_candidate_request)
        self.caller(self.outgoing_candidate_response)
        self.caller(self.outgoing_candidate_request)

        self.caller(self.get_unknown_members_from_address)
        self.caller(self.get_known_members_from_address)

    def get_unknown_members_from_address(self):
        """
        Once we have a dispersy-identity we could obtain a member from the member's address.  Hence,
        when the dispersy-identity is unknown, no members should be returned.
        """
        community = DebugCommunity.create_community(self._my_member)
        assert community.get_members_from_address(("0.0.0.0", 0)) == []
        yield 0.11
        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

    def get_known_members_from_address(self):
        """
        Once we have a dispersy-identity we could obtain a member from the member's address.

        TODO At some point we will need to verify the addresses in the dispersy-identity messages.
        """
        community = DebugCommunity.create_community(self._my_member)

        # create node
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member(candidate=False)
        yield 0.11

        assert node.my_member in community.get_members_from_address(node.socket.getsockname())

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

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
        yield 0.11

        # send a dispersy-candidate-request message
        routes = [(("123.123.123.123", 123), 60.0),
                  (("124.124.124.124", 124), 120.0)]
        node.send_message(node.create_dispersy_candidate_request_message(node.socket.getsockname(), address, conversion_version, routes, 10), address)
        yield 0.11

        # routes must be placed in the database
        items = [((str(host), port), float(age)) for host, port, age in self._dispersy_database.execute(u"SELECT host, port, STRFTIME('%s', DATETIME('now')) - STRFTIME('%s', external_time) AS age FROM candidate WHERE community = ?", (community.database_id,))]
        for route in routes:
            off_by_one_second = (route[0], route[1]+1)
            assert route in items or off_by_one_second in items

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

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
        yield 0.11

        routes = [(u"1.2.3.4", 5),
                  (u"2.3.4.5", 6)]

        # put some routes in the database that we expect back
        with self._dispersy_database as execute:
            for host, port in routes:
                execute(u"INSERT INTO candidate (community, host, port, incoming_time, outgoing_time) VALUES (?, ?, ?, DATETIME('now'), DATETIME('now'))", (community.database_id, host, port))

        # send a dispersy-candidate-request message
        node.send_message(node.create_dispersy_candidate_request_message(node.socket.getsockname(), address, conversion_version, [], 10), address)
        yield 0.11

        # catch dispersy-candidate-response message
        _, message = node.receive_message(addresses=[address], message_names=[u"dispersy-candidate-response"])
        dprint(message.payload.routes, lines=1)
        for route in routes:
            assert (route, 0.0) in message.payload.routes, (route, message.payload.routes)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

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
        for counter in range(int(community.dispersy_candidate_request_initial_delay)):
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
        yield 0.11

        _, message = node.receive_message(addresses=[address], message_names=[u"dispersy-candidate-request"])

        # wait interval
        for counter in range(int(community.dispersy_candidate_request_interval)):
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
        yield 0.11

        # receive dispersy-candidate-request from 2nd interval
        _, message = node.receive_message(addresses=[address], message_names=[u"dispersy-candidate-request"])

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

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
        yield 0.11

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id)))
        assert len(times) == 0, times

        # send a message
        global_time = 10
        node.send_message(node.create_full_sync_text_message("should be accepted (1)", global_time), address)
        yield 0.11
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert len(times) == 1
        assert global_time in times

        # destroy the community
        community.create_dispersy_destroy_community(u"hard-kill")
        yield 0.11

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
        yield 0.11

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id)))
        assert len(times) == 0, times

        # send a message
        global_time = 10
        node.send_message(node.create_full_sync_text_message("should be accepted (1)", global_time), address)
        yield 0.11
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert times == [10], times

        # we now tag the member as ignore
        Member.get_instance(node.my_member.public_key).must_ignore = True

        tags, = self._dispersy_database.execute(u"SELECT tags FROM user WHERE id = ?", (node.my_member.database_id,)).next()
        assert tags & 2

        # send a message and ensure it is in the database (ignore still means it must be stored in
        # the database)
        global_time = 20
        node.send_message(node.create_full_sync_text_message("should be accepted (2)", global_time), address)
        yield 0.11
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert sorted(times) == [10, 20], times

        # we now tag the member not to ignore
        Member.get_instance(node.my_member.public_key).must_ignore = False

        # send a message
        global_time = 30
        node.send_message(node.create_full_sync_text_message("should be accepted (3)", global_time), address)
        yield 0.11
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert sorted(times) == [10, 20, 30], times

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

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
        yield 0.11

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id)))
        assert len(times) == 0, times

        # send a message
        global_time = 10
        node.send_message(node.create_full_sync_text_message("should be accepted (1)", global_time), address)
        yield 0.11
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert len(times) == 1
        assert global_time in times

        # we now tag the member as drop
        Member.get_instance(node.my_member.public_key).must_drop = True

        tags, = self._dispersy_database.execute(u"SELECT tags FROM user WHERE id = ?", (node.my_member.database_id,)).next()
        assert tags & 4

        # send a message and ensure it is not in the database
        global_time = 20
        node.send_message(node.create_full_sync_text_message("should NOT be accepted (2)", global_time), address)
        yield 0.11
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert len(times) == 1
        assert global_time not in times

        # we now tag the member not to drop
        Member.get_instance(node.my_member.public_key).must_drop = False

        # send a message
        global_time = 30
        node.send_message(node.create_full_sync_text_message("should be accepted (3)", global_time), address)
        yield 0.11
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert len(times) == 2
        assert global_time in times

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

class DispersyBatchScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = MyMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)

        # duplicate messages are removed
        self.caller(self.one_batch_binary_duplicate)
        self.caller(self.two_batches_binary_duplicate)
        self.caller(self.one_batch_user_global_time_duplicate)
        self.caller(self.two_batches_user_global_time_duplicate)

        # big batch test
        self.caller(self.one_big_batch)
        self.caller(self.many_small_batches)

    def one_batch_binary_duplicate(self):
        """
        When multiple binary identical UDP packets are received, the duplicate packets need to be
        reduced to one packet.
        """
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.11

        global_time = 10
        message = node.create_full_sync_text_message("duplicates", global_time)
        for _ in range(10):
            node.send_packet(message.packet, address)
        yield 0.11

        # only one message may be in the database
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert times == [global_time]

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

    def two_batches_binary_duplicate(self):
        """
        When multiple binary identical UDP packets are received, the duplicate packets need to be
        reduced to one packet.

        The second batch needs to be dropped aswell, while the last unique packet of the second
        batch is dropped when the when the database is consulted.
        """
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.11

        global_time = 10
        # first batch
        message = node.create_full_sync_text_message("duplicates", global_time)
        for _ in range(10):
            node.send_packet(message.packet, address)
        yield 0.11

        # only one message may be in the database
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert times == [global_time]

        # second batch
        for _ in range(10):
            node.send_packet(message.packet, address)
        yield 0.11

        # only one message may be in the database
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert times == [global_time]

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

    def one_batch_user_global_time_duplicate(self):
        """
        A member can create invalid duplicate messages that are binary different.

        For instance, two different messages that are created by the same member and have the same
        global_time, will be binary different while they are still duplicates.  Because dispersy
        uses the message creator and the global_time to uniquely identify messages.
        """
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        meta = community.get_meta_message(u"full-sync-text")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.11

        global_time = 10
        for index in range(10):
            node.send_message(node.create_full_sync_text_message("duplicates (%d)" % index, global_time), address)
        yield 0.11

        # only one message may be in the database
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, meta.database_id))]
        assert times == [global_time]

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

    def two_batches_user_global_time_duplicate(self):
        """
        A member can create invalid duplicate messages that are binary different.

        For instance, two different messages that are created by the same member and have the same
        global_time, will be binary different while they are still duplicates.  Because dispersy
        uses the message creator and the global_time to uniquely identify messages.

        The second batch needs to be dropped aswell, while the last unique packet of the second
        batch is dropped when the when the database is consulted.
        """
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        meta = community.get_meta_message(u"full-sync-text")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.11

        global_time = 10
        # first batch
        for index in range(10):
            node.send_message(node.create_full_sync_text_message("duplicates (%d)" % index, global_time), address)
        yield 0.11

        # only one message may be in the database
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, meta.database_id))]
        assert times == [global_time]

        # second batch
        for index in range(10):
            node.send_message(node.create_full_sync_text_message("duplicates (%d)" % index, global_time), address)
        yield 0.11

        # only one message may be in the database
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, meta.database_id))]
        assert times == [global_time]

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

    def one_big_batch(self):
        """
        Each community is handled in its own batch, hence we can measure performace differences when
        we make one large batch (using one community) and many small batches (using many different
        communities).
        """
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        meta = community.get_meta_message(u"full-sync-text")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.11

        dprint("START BIG BATCH")
        for global_time in range(10, 510):
            node.send_message(node.create_full_sync_text_message("Dprint=False, big batch #%d" % global_time, global_time), address, verbose=False)

        begin = clock()
        yield 0.11
        end = clock()
        self._big_batch_took = end - begin
        dprint("BIG BATCH TOOK ", self._big_batch_took, " SECONDS")

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

    def many_small_batches(self):
        """
        Each community is handled in its own batch, hence we can measure performace differences when
        we make one large batch (using one community) and many small batches (using many different
        communities).
        """
        exp = []
        for _ in range(500):
            community = DebugCommunity.create_community(self._my_member)
            address = self._dispersy.socket.get_address()
            meta = community.get_meta_message(u"full-sync-text")

            # create node and ensure that SELF knows the node address
            node = DebugNode()
            node.init_socket()
            node.set_community(community)
            node.init_my_member()

            exp.append((community, node))
            yield 0.11

        dprint("START SMALL BATCHES")
        global_time = 10
        for community, node in exp:
            node.send_message(node.create_full_sync_text_message("Dprint=False, small batches", global_time), address, verbose=False)

        begin = clock()
        yield 0.11
        end = clock()
        self._small_batches_took = end - begin
        dprint("SMALL BATCHES TOOK ", self._small_batches_took, " SECONDS")

        # cleanup
        for community, _ in exp:
            community.create_dispersy_destroy_community(u"hard-kill")
            community.unload_community()

        dprint("BIG BATCH TOOK ", self._big_batch_took, " SECONDS")
        dprint("SMALL BATCHES TOOK ", self._small_batches_took, " SECONDS")
        assert self._big_batch_took < self._small_batches_took

class DispersySyncScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = MyMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)

        # scaling: when we have to many messages in the sync bloom filter
        self.caller(self.batch_reversed_enlarging_sync_bloom)
        self.caller(self.batch_enlarging_sync_bloom)
        self.caller(self.reversed_enlarging_sync_bloom)
        self.caller(self.enlarging_sync_bloom)
        self.caller(self.large_sync)

        # scaling: when we have to few messages in the sync bloom filter
        self.caller(self.shrinking_sync_bloom)

        # different sync policies
        self.caller(self.in_order_test)
        self.caller(self.out_order_test)
        self.caller(self.random_order_test)
        self.caller(self.mixed_order_test)
        self.caller(self.last_1_test)
        self.caller(self.last_9_nosequence_test)
        self.caller(self.last_9_sequence_test)

        # multimember authentication and last sync policies
        self.caller(self.last_1_multimember)
        self.caller(self.last_1_multimember_unique_user_global_time)
        self.caller(self.last_1_multimember_sync_bloom_crash_test)
        # TODO add more checks for the multimemberauthentication case
        # self.caller(self.last_9_multimember)

    def assert_sync_ranges(self, community, messages, minimal_remaining=0, verbose=False):
        time_high = 0
        for sync_range in community._sync_ranges:
            if verbose: dprint("range [", sync_range.time_low, ":", time_high if time_high else "inf", "] space_remaining: ", sync_range.space_remaining, "; freed: ", sync_range.space_freed, "; used: ", sync_range.capacity - sync_range.space_remaining - sync_range.space_freed, "; capacity: ", sync_range.capacity)
            assert sync_range.space_remaining >= minimal_remaining, (sync_range.space_remaining, ">=", minimal_remaining)
            time_high = sync_range.time_low - 1

        for message in messages:
            for sync_range in community._sync_ranges:
                if sync_range.time_low <= message.distribution.global_time:
                    for bloom_filter in sync_range.bloom_filters:
                        assert message.packet in bloom_filter, (message.distribution.global_time, "[%d:?]" % sync_range.time_low, len([x for x in messages if x.distribution.global_time == message.distribution.global_time]))
                    break
            else:
                assert False, "should always find the sync_range"

    def enlarging_sync_bloom(self):
        """
        The sync bloomfilter should grow when to many packets are received in that time range.  Also
        tests that the sync bloom filters are initialized correctly when the community is loaded.
        """
        class TestCommunity(DebugCommunity):
            @property
            def dispersy_sync_bloom_filter_bits(self):
                # this results in a capacity off 10
                return 90

        community = TestCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        assert community._sync_ranges[0].capacity == 10

        messages = []
        for counter in xrange(11):
            if counter >= 9:
                minimal_remaining = 10 - counter - 2
            else:
                minimal_remaining = 0
            dprint("NODE #", counter, "; minimal_remaining: ", minimal_remaining)

            # create node and ensure that SELF knows the node address
            node = DebugNode()
            node.init_socket()
            node.set_community(community)
            node.init_my_member()
            yield 0.11
            self.assert_sync_ranges(community, messages, minimal_remaining=minimal_remaining)

            # create a few messages in each sync bloomfilter range
            for global_time in xrange(10, 20):
                messages.append(node.send_message(node.create_in_order_text_message("node: %d; global-time: %d; Dprint=False" % (counter, global_time), global_time), address))
                yield 0.11
            self.assert_sync_ranges(community, messages, minimal_remaining=minimal_remaining, verbose=True)

            # unload community
            community.unload_community()
            yield 0.11

            dprint("loading...")

            # load community
            community = TestCommunity.load_community(community.cid, "")
            self.assert_sync_ranges(community, messages, minimal_remaining=minimal_remaining, verbose=True)

        # TODO: run an 'optimizer' method to cleanup dead space in the sync ranges
        # optimal = math.ceil((2.0 + counter * 11.0) / 10.0)
        # assert len(community._sync_ranges) in (optimal, optimal+1), (len(community._sync_ranges), optimal)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

    def shrinking_sync_bloom(self):
        """
        The sync bloomfilter should shrink when there is too much free space in that time range.

        One trivial way to shrink is to remove any sync ranges that no longer store -any- messages.
        We will add messages until this happens.
        """
        class TestCommunity(DebugCommunity):
            @property
            def dispersy_sync_bloom_filter_bits(self):
                # this results in a capacity off 10
                return 90

        community = TestCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        assert community._sync_ranges[0].capacity == 10

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.11
        self.assert_sync_ranges(community, [])
        assert community._sync_ranges[0].space_remaining == 7 # 10 - 3 (disp-identity, disp-authorize, disp-identity)

        # create a lot of messages, the first few sync ranges should go 'empty'
        for global_time in xrange(10, 51):
            node.send_message(node.create_last_9_nosequence_test_message("global-time: %d; Dprint=False" % global_time, global_time), address)
            yield 0.11
        self.assert_sync_ranges(community, [], verbose=True)

        # at least one sync range must have been removed!
        assert len(community._sync_ranges) == 3

        # TODO: run an 'optimizer' method to cleanup dead space in the sync ranges
        # optimal = math.ceil((2.0 + counter * 11.0) / 10.0)
        # assert len(community._sync_ranges) in (optimal, optimal+1), (len(community._sync_ranges), optimal)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

    def reversed_enlarging_sync_bloom(self):
        """
        The sync bloomfilter should grow when to many packets are received in that time range Also
        tests that the sync bloom filters are initialized correctly when the community is loaded.
        """
        class TestCommunity(DebugCommunity):
            @property
            def dispersy_sync_bloom_filter_bits(self):
                # this results in a capacity off 10
                return 90

        community = TestCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        assert community._sync_ranges[0].capacity == 10

        messages = []
        for counter in xrange(11):
            if counter >= 9:
                minimal_remaining = 10 - counter - 2
            else:
                minimal_remaining = 0
            dprint("NODE #", counter, "; minimal_remaining: ", minimal_remaining)

            # create node and ensure that SELF knows the node address
            node = DebugNode()
            node.init_socket()
            node.set_community(community)
            node.init_my_member()
            yield 0.11

            # create a few messages in each sync bloomfilter range
            for global_time in xrange(20, 10, -1):
                messages.append(node.send_message(node.create_in_order_text_message("node: %d; global-time: %d; Dprint=False" % (counter, global_time), global_time), address))
                yield 0.11
            self.assert_sync_ranges(community, messages, minimal_remaining=minimal_remaining, verbose=True)

            # unload community
            community.unload_community()
            yield 0.11

            dprint("loading...")

            # load community
            community = TestCommunity.load_community(community.cid, "")
            self.assert_sync_ranges(community, messages, minimal_remaining=minimal_remaining, verbose=True)

        # TODO: run an 'optimizer' method to cleanup dead space in the sync ranges
        # optimal = math.ceil((2.0 + counter * 11.0) / 10.0)
        # assert len(community._sync_ranges) in (optimal, optimal+1), (len(community._sync_ranges), optimal)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

    def batch_enlarging_sync_bloom(self):
        """
        The sync bloomfilter should grow when to many packets are received in that time range.  Also
        tests that the sync bloom filters are initialized correctly when the community is loaded.
        """
        class TestCommunity(DebugCommunity):
            @property
            def dispersy_sync_bloom_filter_bits(self):
                # this results in a capacity off 10
                return 90

        community = TestCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        assert community._sync_ranges[0].capacity == 10

        messages = []
        for counter in xrange(11):
            if counter >= 9:
                minimal_remaining = 10 - counter - 2
            else:
                minimal_remaining = 0
            dprint("NODE #", counter, "; minimal_remaining: ", minimal_remaining)

            # create node and ensure that SELF knows the node address
            node = DebugNode()
            node.init_socket()
            node.set_community(community)
            node.init_my_member()
            yield 0.11
            self.assert_sync_ranges(community, messages, minimal_remaining=minimal_remaining)

            # create a few messages in each sync bloomfilter range
            for global_time in xrange(10, 20):
                messages.append(node.send_message(node.create_in_order_text_message("node: %d; global-time: %d; Dprint=False" % (counter, global_time), global_time), address))
                yield 0.11
            self.assert_sync_ranges(community, messages, minimal_remaining=minimal_remaining, verbose=True)

            # unload community
            community.unload_community()
            yield 0.11

            dprint("loading...")

            # load community
            community = TestCommunity.load_community(community.cid, "")
            self.assert_sync_ranges(community, messages, minimal_remaining=minimal_remaining, verbose=True)

        # TODO: run an 'optimizer' method to cleanup dead space in the sync ranges
        # optimal = math.ceil((2.0 + counter * 11.0) / 10.0)
        # assert len(community._sync_ranges) in (optimal, optimal+1), (len(community._sync_ranges), optimal)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

    def batch_reversed_enlarging_sync_bloom(self):
        """
        The sync bloomfilter should grow when to many packets are received in that time range.  Also
        tests that the sync bloom filters are initialized correctly when the community is loaded.
        """
        class TestCommunity(DebugCommunity):
            @property
            def dispersy_sync_bloom_filter_bits(self):
                # this results in a capacity off 10
                return 90

        community = TestCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        assert community._sync_ranges[0].capacity == 10

        messages = []
        for counter in xrange(11):
            if counter >= 9:
                minimal_remaining = 10 - counter - 2
            else:
                minimal_remaining = 0
            dprint("NODE #", counter, "; minimal_remaining: ", minimal_remaining)

            # create node and ensure that SELF knows the node address
            node = DebugNode()
            node.init_socket()
            node.set_community(community)
            node.init_my_member()
            yield 0.11

            # create a few messages in each sync bloomfilter range
            for global_time in xrange(20, 10, -1):
                messages.append(node.send_message(node.create_in_order_text_message("node: %d; global-time: %d; Dprint=False" % (counter, global_time), global_time), address))
                yield 0.11
            self.assert_sync_ranges(community, messages, minimal_remaining=minimal_remaining, verbose=True)


            # unload community
            community.unload_community()
            yield 0.11

            dprint("loading...")

            # load community
            community = TestCommunity.load_community(community.cid, "")
            self.assert_sync_ranges(community, messages, minimal_remaining=minimal_remaining, verbose=True)

        # TODO: run an 'optimizer' method to cleanup dead space in the sync ranges
        # optimal = math.ceil((2.0 + counter * 11.0) / 10.0)
        # assert len(community._sync_ranges) in (optimal, optimal+1), (len(community._sync_ranges), optimal)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

    def large_sync(self):
        """
        The sync bloomfilter covers a certain global-time range.  Hence, as time goes on, multiple
        bloomfilters should be generated and periodically synced.

        We use a dispersy_sync_bloom_filter_capacity of 25.  Hence each bloom filter must hold no
        more than 25 packets.
        """
        class TestCommunity(DebugCommunity):
            @property
            def dispersy_sync_bloom_filter_bits(self):
                # this results in a capacity off 25
                return 210

        community = TestCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        assert community._sync_ranges[0].capacity == 25, community._sync_ranges[0].capacity

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.11

        # create a few messages in each sync bloomfilter range
        messages = []
        for global_time in xrange(10, 110):
            messages.append(node.send_message(node.create_in_order_text_message("global-time: %d" % global_time, global_time), address))
            yield 0.01

        yield 0.11

        # we should have around 100 / 25 = 4 sync ranges
        for sync_range in community._sync_ranges:
            dprint("range [", sync_range.time_low, ":... space_remaining: ", sync_range.space_remaining)
            assert sync_range.space_remaining >= 0
        assert len(community._sync_ranges) in (4, 5)

        for message in messages:
            for sync_range in community._sync_ranges:
                if sync_range.time_low <= message.distribution.global_time:
                    for bloom_filter in sync_range.bloom_filters:
                        assert message.packet in bloom_filter
                    break
            else:
                assert False, "should always find the sync_range"

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

    def in_order_test(self):
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        message = community.get_meta_message(u"in-order-text")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.11

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id)))
        assert len(times) == 0, times

        # create some data
        global_times = range(10, 15)
        for global_time in global_times:
            node.send_message(node.create_in_order_text_message("Message #%d" % global_time, global_time), address)
            yield 0.11

        # send an empty sync message to obtain all messages in-order
        node.send_message(node.create_dispersy_sync_message(min(global_times), max(global_times), [], max(global_times)), address)
        yield 0.11

        for global_time in global_times:
            _, message = node.receive_message(addresses=[address], message_names=[u"in-order-text"])
            assert message.distribution.global_time == global_time

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

    def out_order_test(self):
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        message = community.get_meta_message(u"out-order-text")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.11

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id)))
        assert len(times) == 0, times

        # create some data
        global_times = range(10, 15)
        for global_time in global_times:
            node.send_message(node.create_out_order_text_message("Message #%d" % global_time, global_time), address)
            yield 0.11

        # send an empty sync message to obtain all messages out-order
        node.send_message(node.create_dispersy_sync_message(min(global_times), max(global_times), [], max(global_times)), address)
        yield 0.11

        for global_time in reversed(global_times):
            _, message = node.receive_message(addresses=[address], message_names=[u"out-order-text"])
            assert message.distribution.global_time == global_time

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

    def random_order_test(self):
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        message = community.get_meta_message(u"random-order-text")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.11

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id)))
        assert len(times) == 0, times

        # create some data
        global_times = range(10, 15)
        for global_time in global_times:
            node.send_message(node.create_random_order_text_message("Message #%d" % global_time, global_time), address)
            yield 0.11

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
            yield 0.11

            received_times = get_messages_back()
            if not received_times in lists:
                lists.append(received_times)

        dprint(lists, lines=True)
        assert len(lists) > 1

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

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
        yield 0.11

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
            yield 0.11
            global_time += 1
            out_order_times.append(global_time)
            node.send_message(node.create_out_order_text_message("Message #%d" % global_time, global_time), address)
            yield 0.11
            global_time += 1
            random_order_times.append(global_time)
            node.send_message(node.create_random_order_text_message("Message #%d" % global_time, global_time), address)
            yield 0.11
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
            yield 0.11

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
        community.unload_community()

    def last_1_test(self):
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        message = community.get_meta_message(u"last-1-test")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.11

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id)))
        assert len(times) == 0, times

        # send a message
        global_time = 10
        node.send_message(node.create_last_1_test_message("should be accepted (1)", global_time), address)
        yield 0.11
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert len(times) == 1
        assert global_time in times

        # send a message
        global_time = 11
        node.send_message(node.create_last_1_test_message("should be accepted (2)", global_time), address)
        yield 0.11
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert len(times) == 1, len(times)
        assert global_time in times

        # send a message (older: should be dropped)
        node.send_message(node.create_last_1_test_message("should be dropped (1)", 8), address)
        yield 0.11
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert len(times) == 1
        assert global_time in times

        # as proof for the drop, the newest message should be sent back
        _, message = node.receive_message(addresses=[address], message_names=[u"last-1-test"])
        assert message.distribution.global_time == 11

        # send a message (duplicate: should be dropped)
        node.send_message(node.create_last_1_test_message("should be dropped (2)", global_time), address)
        yield 0.11
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert len(times) == 1
        assert global_time in times

        # send a message
        global_time = 12
        node.send_message(node.create_last_1_test_message("should be accepted (3)", global_time), address)
        yield 0.11
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert len(times) == 1
        assert global_time in times

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

    def last_9_nosequence_test(self):
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        message = community.get_meta_message(u"last-9-nosequence-test")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.11

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id)))
        assert len(times) == 0

        number_of_messages = 0
        for global_time in [21, 20, 28, 27, 22, 23, 24, 26, 25]:
            # send a message
            message = node.create_last_9_nosequence_test_message(str(global_time), global_time)
            node.send_message(message, address)
            number_of_messages += 1
            yield 0.11
            try:
                packet, = self._dispersy_database.execute(u"SELECT packet FROM sync WHERE community = ? AND user = ? AND global_time = ? AND name = ?", (community.database_id, node.my_member.database_id, global_time, message.database_id)).next()
            except StopIteration:
                assert False
            assert str(packet) == message.packet
            times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
            dprint(sorted(times))
            assert len(times) == number_of_messages, (len(times), number_of_messages)
            assert global_time in times
        assert number_of_messages == 9, number_of_messages

        dprint("Older: should be dropped")
        for global_time in [11, 12, 13, 19, 18, 17]:
            # send a message (older: should be dropped)
            node.send_message(node.create_last_9_nosequence_test_message(str(global_time), global_time), address)
            yield 0.11
            times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
            assert len(times) == 9, len(times)
            assert not global_time in times

        dprint("Duplicate: should be dropped")
        for global_time in [21, 20, 28, 27, 22, 23, 24, 26, 25]:
            # send a message (duplicate: should be dropped)
            message = node.create_last_9_nosequence_test_message("wrong content!", global_time)
            node.send_message(message, address)
            yield 0.11
            try:
                packet, = self._dispersy_database.execute(u"SELECT packet FROM sync WHERE community = ? AND user = ? AND global_time = ? AND name = ?", (community.database_id, node.my_member.database_id, global_time, message.database_id)).next()
            except StopIteration:
                assert False
            assert not str(packet) == message.packet
            times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
            assert sorted(times) == range(20, 29), sorted(times)

        dprint("Should be added and old one removed")
        match_times = sorted(times[:])
        for global_time in [30, 35, 37, 31, 32, 34, 33, 36, 38, 45, 44, 43, 42, 41, 40, 39]:
            # send a message (should be added and old one removed)
            message = node.create_last_9_nosequence_test_message(str(global_time), global_time)
            node.send_message(message, address)
            match_times.pop(0)
            match_times.append(global_time)
            match_times.sort()
            yield 0.11
            try:
                packet, = self._dispersy_database.execute(u"SELECT packet FROM sync WHERE community = ? AND user = ? AND global_time = ? AND name = ?", (community.database_id, node.my_member.database_id, global_time, message.database_id)).next()
            except StopIteration:
                assert False
            assert str(packet) == message.packet
            times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
            dprint(sorted(times))
            assert sorted(times) == match_times, sorted(times)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

    def last_9_sequence_test(self):
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        message = community.get_meta_message(u"last-9-sequence-test")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.11

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id)))
        assert len(times) == 0

        number_of_messages = 0
        for sequence_number in range(1, 10):
            global_time = sequence_number * 100
            # send a message
            message = node.create_last_9_sequence_test_message("Wave 1 #%d" % global_time, global_time, sequence_number)
            node.send_message(message, address)
            number_of_messages += 1
            yield 0.11
            try:
                packet, = self._dispersy_database.execute(u"SELECT packet FROM sync WHERE community = ? AND user = ? AND global_time = ? AND distribution_sequence = ? AND name = ?", (community.database_id, node.my_member.database_id, global_time, sequence_number, message.database_id)).next()
            except StopIteration:
                dprint((community.database_id, node.my_member.database_id, global_time, sequence_number, message.database_id))
                assert False
            assert str(packet) == message.packet
            times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
            dprint(sorted(times))
            assert len(times) == number_of_messages, (len(times), number_of_messages)
            assert global_time in times
        assert number_of_messages == 9, number_of_messages

        for sequence_number in range(1, 10):
            global_time = sequence_number * 100
            # send a message (both global_time and sequence_number are duplicate: should be dropped)
            message = node.create_last_9_sequence_test_message("Wave 2 #%d (should be dropped)" % global_time, global_time, sequence_number)
            node.send_message(message, address)
            yield 0.11
            try:
                packet, = self._dispersy_database.execute(u"SELECT packet FROM sync WHERE community = ? AND user = ? AND global_time = ? AND distribution_sequence = ? AND name = ?", (community.database_id, node.my_member.database_id, global_time, sequence_number, message.database_id)).next()
            except StopIteration:
                assert False
            assert not str(packet) == message.packet
            times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
            assert sorted(times) == range(100, 1000, 100), sorted(times)

        match_times = sorted([x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))])
        for sequence_number in range(10, 25):
            global_time = sequence_number * 100
            # send a message (should be added and old one removed)
            message = node.create_last_9_sequence_test_message("Wave 3 #%d (should replace older)" % global_time, global_time, sequence_number)
            node.send_message(message, address)
            match_times.pop(0)
            match_times.append(global_time)
            yield 0.11
            try:
                packet, = self._dispersy_database.execute(u"SELECT packet FROM sync WHERE community = ? AND user = ? AND global_time = ? AND distribution_sequence = ? AND name = ?", (community.database_id, node.my_member.database_id, global_time, sequence_number, message.database_id)).next()
            except StopIteration:
                assert False
            assert str(packet) == message.packet
            times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
            dprint(sorted(times))
            assert sorted(times) == match_times, sorted(times)

        match_times = sorted([x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))])
        for sequence_number in range(1, 16):
            global_time = sequence_number * 100
            # send a message (older: should be dropped)
            node.send_message(node.create_last_9_sequence_test_message("Wave 4 #%d" % global_time, global_time, sequence_number), address)
            yield 0.11
            times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
            assert len(times) == 9, len(times)
            assert not global_time in times, (global_time, times)
            assert sorted(times) == match_times

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

    def last_1_multimember(self):
        """
        Normally the LastSyncDistribution policy stores the last N messages for each member that
        created the message.  However, when the MultiMemberAuthentication policy is used, there are
        multiple members.

        This can be handled in two ways:

         1. The first member who signed the message is still seen as the creator and hence the last
            N messages of this member are stored.

         2. Each member combination is used and the last N messages for each member combination is
            used.  For example: when member A and B sign a message it will not count toward the
            last-N of messages signed by A and C (which is another member combination.)

        Currently we only implement option #2.  There currently is no parameter to switch between
        these options.
        """
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        message = community.get_meta_message(u"last-1-multimember-text")

        # create node and ensure that SELF knows the node address
        nodeA = DebugNode()
        nodeA.init_socket()
        nodeA.set_community(community)
        nodeA.init_my_member()
        yield 0.11

        # create node and ensure that SELF knows the node address
        nodeB = DebugNode()
        nodeB.init_socket()
        nodeB.set_community(community)
        nodeB.init_my_member()
        yield 0.11

        # create node and ensure that SELF knows the node address
        nodeC = DebugNode()
        nodeC.init_socket()
        nodeC.set_community(community)
        nodeC.init_my_member()
        yield 0.11

        # # dump some junk data, TODO: should not use this btw in actual test...
        # self._dispersy_database.execute(u"INSERT INTO sync (community, name, user, global_time) VALUES (?, ?, 42, 9)", (community.database_id, message.database_id))
        # sync_id = self._dispersy_database.last_insert_rowid
        # self._dispersy_database.execute(u"INSERT INTO reference_user_sync (user, sync) VALUES (42, ?)", (sync_id,))
        # self._dispersy_database.execute(u"INSERT INTO reference_user_sync (user, sync) VALUES (43, ?)", (sync_id,))
        # #
        # self._dispersy_database.execute(u"INSERT INTO sync (community, name, user, global_time) VALUES (?, ?, 4, 9)", (community.database_id, message.database_id))
        # sync_id = self._dispersy_database.last_insert_rowid
        # self._dispersy_database.execute(u"INSERT INTO reference_user_sync (user, sync) VALUES (4, ?)", (sync_id,))
        # self._dispersy_database.execute(u"INSERT INTO reference_user_sync (user, sync) VALUES (43, ?)", (sync_id,))

        # send a message
        global_time = 10
        other_global_time = global_time + 1
        messages = []
        messages.append(nodeA.create_last_1_multimember_text_message([nodeB.my_member], "should be accepted (1)", global_time))
        messages.append(nodeA.create_last_1_multimember_text_message([nodeC.my_member], "should be accepted (1)", other_global_time))
        self._dispersy.on_incoming_packets([(nodeA.socket.getsockname(), message.packet) for message in messages])
        yield 0.11
        entries = list(self._dispersy_database.execute(u"SELECT sync.global_time, sync.user, reference_user_sync.user FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND sync.user = ? AND sync.name = ?", (community.database_id, nodeA.my_member.database_id, message.database_id)))
        assert len(entries) == 4, entries
        assert (global_time, nodeA.my_member.database_id, nodeA.my_member.database_id) in entries
        assert (global_time, nodeA.my_member.database_id, nodeB.my_member.database_id) in entries
        assert (other_global_time, nodeA.my_member.database_id, nodeA.my_member.database_id) in entries
        assert (other_global_time, nodeA.my_member.database_id, nodeC.my_member.database_id) in entries

        # send a message
        global_time = 20
        other_global_time = global_time + 1
        messages = []
        messages.append(nodeA.create_last_1_multimember_text_message([nodeB.my_member], "should be accepted (2)", global_time))
        messages.append(nodeA.create_last_1_multimember_text_message([nodeC.my_member], "should be accepted (2)", other_global_time))
        self._dispersy.on_incoming_packets([(nodeA.socket.getsockname(), message.packet) for message in messages])
        yield 0.11
        entries = list(self._dispersy_database.execute(u"SELECT sync.global_time, sync.user, reference_user_sync.user FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND sync.user = ? AND sync.name = ?", (community.database_id, nodeA.my_member.database_id, message.database_id)))
        assert len(entries) == 4, entries
        assert (global_time, nodeA.my_member.database_id, nodeA.my_member.database_id) in entries
        assert (global_time, nodeA.my_member.database_id, nodeB.my_member.database_id) in entries
        assert (other_global_time, nodeA.my_member.database_id, nodeA.my_member.database_id) in entries
        assert (other_global_time, nodeA.my_member.database_id, nodeC.my_member.database_id) in entries

        # send a message (older: should be dropped)
        old_global_time = 8
        messages = []
        messages.append(nodeA.create_last_1_multimember_text_message([nodeB.my_member], "should be dropped (1)", old_global_time))
        messages.append(nodeA.create_last_1_multimember_text_message([nodeC.my_member], "should be dropped (1)", old_global_time))
        self._dispersy.on_incoming_packets([(nodeA.socket.getsockname(), message.packet) for message in messages])
        yield 0.11
        entries = list(self._dispersy_database.execute(u"SELECT sync.global_time, sync.user, reference_user_sync.user FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND sync.user = ? AND sync.name = ?", (community.database_id, nodeA.my_member.database_id, message.database_id)))
        assert len(entries) == 4, entries
        assert (global_time, nodeA.my_member.database_id, nodeA.my_member.database_id) in entries
        assert (global_time, nodeA.my_member.database_id, nodeB.my_member.database_id) in entries
        assert (other_global_time, nodeA.my_member.database_id, nodeA.my_member.database_id) in entries, entries
        assert (other_global_time, nodeA.my_member.database_id, nodeC.my_member.database_id) in entries

        # send a message (older: should be dropped)
        old_global_time = 8
        messages = []
        messages.append(nodeB.create_last_1_multimember_text_message([nodeA.my_member], "should be dropped (1)", old_global_time))
        messages.append(nodeC.create_last_1_multimember_text_message([nodeA.my_member], "should be dropped (1)", old_global_time))
        self._dispersy.on_incoming_packets([(nodeA.socket.getsockname(), message.packet) for message in messages])
        yield 0.11
        entries = list(self._dispersy_database.execute(u"SELECT sync.global_time, sync.user, reference_user_sync.user FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND sync.user = ? AND sync.name = ?", (community.database_id, nodeA.my_member.database_id, message.database_id)))
        assert len(entries) == 4, entries
        assert (global_time, nodeA.my_member.database_id, nodeA.my_member.database_id) in entries
        assert (global_time, nodeA.my_member.database_id, nodeB.my_member.database_id) in entries
        assert (other_global_time, nodeA.my_member.database_id, nodeA.my_member.database_id) in entries
        assert (other_global_time, nodeA.my_member.database_id, nodeC.my_member.database_id) in entries

        # as proof for the drop, the newest message should be sent back
        _, message = nodeA.receive_message(addresses=[address], message_names=[u"last-1-multimember-text"])
        assert message.distribution.global_time == global_time

        # send a message (older + different member combination: should be dropped)
        old_global_time = 9
        messages = []
        messages.append(nodeB.create_last_1_multimember_text_message([nodeA.my_member], "should be dropped (2)", old_global_time))
        messages.append(nodeC.create_last_1_multimember_text_message([nodeA.my_member], "should be dropped (2)", old_global_time))
        self._dispersy.on_incoming_packets([(nodeA.socket.getsockname(), message.packet) for message in messages])
        yield 0.11
        entries = list(self._dispersy_database.execute(u"SELECT sync.global_time, sync.user, reference_user_sync.user FROM sync JOIN reference_user_sync ON reference_user_sync.sync = sync.id WHERE sync.community = ? AND sync.user = ? AND sync.name = ?", (community.database_id, nodeA.my_member.database_id, message.database_id)))
        assert len(entries) == 4, entries
        assert (global_time, nodeA.my_member.database_id, nodeA.my_member.database_id) in entries
        assert (global_time, nodeA.my_member.database_id, nodeB.my_member.database_id) in entries
        assert (other_global_time, nodeA.my_member.database_id, nodeA.my_member.database_id) in entries
        assert (other_global_time, nodeA.my_member.database_id, nodeC.my_member.database_id) in entries

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

    def last_1_multimember_sync_bloom_crash_test(self):
        """
        We found a race condition where the sync bloom filter was freed to many times.  This was
        because the select for items that had to be removed was done several times without an actual
        delete.

        This test simulates that condition to ensure this bug doesn't happen again.  It will crash
        on one of the internal asserts in the sync bloom filter free method.

        One key thing here is that multiple last-sync messages must be processed in one batch for it
        to occur.

        It is proving to be somewhat difficult to repreduce though...
        """
        class TestCommunity(DebugCommunity):
            @property
            def dispersy_sync_bloom_filter_bits(self):
                # this results in a capacity off 10
                return 90

        community = TestCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        message = community.get_meta_message(u"last-1-multimember-text")
        assert community._sync_ranges[0].capacity == 10, community._sync_ranges[0].capacity

        # create node and ensure that SELF knows the node address
        nodeA = DebugNode()
        nodeA.init_socket()
        nodeA.set_community(community)
        nodeA.init_my_member()
        yield 0.11

        # create node and ensure that SELF knows the node address
        nodeB = DebugNode()
        nodeB.init_socket()
        nodeB.set_community(community)
        nodeB.init_my_member()
        yield 0.11

        # create node and ensure that SELF knows the node address
        nodeC = DebugNode()
        nodeC.init_socket()
        nodeC.set_community(community)
        nodeC.init_my_member()
        yield 0.11

        for global_time in xrange(10, 150, 3):
            # send two messages
            messages = []
            messages.append(nodeA.create_last_1_multimember_text_message([nodeB.my_member], "should be accepted (1.1)", global_time))
            messages.append(nodeA.create_last_1_multimember_text_message([nodeC.my_member], "should be accepted (1.2)", global_time))
            global_time += 1
            messages.append(nodeA.create_last_1_multimember_text_message([nodeB.my_member], "should be accepted (2.1)", global_time))
            messages.append(nodeA.create_last_1_multimember_text_message([nodeC.my_member], "should be accepted (2.2)", global_time))
            global_time += 1
            messages.append(nodeA.create_last_1_multimember_text_message([nodeB.my_member], "should be accepted (3.1)", global_time))
            messages.append(nodeA.create_last_1_multimember_text_message([nodeC.my_member], "should be accepted (3.2)", global_time))

            # we NEED the messages to be handled in one batch.  using the socket may change this
            self._dispersy.on_incoming_packets([(nodeA.socket.getsockname(), message.packet) for message in messages])

        for global_time in xrange(300, 150, -3):
            # send two messages
            messages = []
            messages.append(nodeA.create_last_1_multimember_text_message([nodeB.my_member], "should be accepted (1.1)", global_time))
            messages.append(nodeA.create_last_1_multimember_text_message([nodeC.my_member], "should be accepted (1.2)", global_time))
            global_time += 1
            messages.append(nodeA.create_last_1_multimember_text_message([nodeB.my_member], "should be accepted (2.1)", global_time))
            messages.append(nodeA.create_last_1_multimember_text_message([nodeC.my_member], "should be accepted (2.2)", global_time))
            global_time += 1
            messages.append(nodeA.create_last_1_multimember_text_message([nodeB.my_member], "should be accepted (3.1)", global_time))
            messages.append(nodeA.create_last_1_multimember_text_message([nodeC.my_member], "should be accepted (3.2)", global_time))

            # we NEED the messages to be handled in one batch.  using the socket may change this
            self._dispersy.on_incoming_packets([(nodeA.socket.getsockname(), message.packet) for message in messages])

        self.assert_sync_ranges(community, [], verbose=True)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

    def last_1_multimember_unique_user_global_time(self):
        """
        Even with multi member messages, the first member is the creator and may only have one
        message for each global time.
        """
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        message = community.get_meta_message(u"last-1-multimember-text")

        # create node and ensure that SELF knows the node address
        nodeA = DebugNode()
        nodeA.init_socket()
        nodeA.set_community(community)
        nodeA.init_my_member()
        yield 0.11

        # create node and ensure that SELF knows the node address
        nodeB = DebugNode()
        nodeB.init_socket()
        nodeB.set_community(community)
        nodeB.init_my_member()
        yield 0.11

        # create node and ensure that SELF knows the node address
        nodeC = DebugNode()
        nodeC.init_socket()
        nodeC.set_community(community)
        nodeC.init_my_member()
        yield 0.11

        # send two messages
        global_time = 10
        messages = []
        messages.append(nodeA.create_last_1_multimember_text_message([nodeB.my_member], "should be accepted (1.1)", global_time))
        messages.append(nodeA.create_last_1_multimember_text_message([nodeC.my_member], "should be accepted (1.2)", global_time))

        # we NEED the messages to be handled in one batch.  using the socket may change this
        self._dispersy.on_incoming_packets([(nodeA.socket.getsockname(), message.packet) for message in messages])

        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, nodeA.my_member.database_id, message.database_id))]
        assert times == [global_time], times

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

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
        yield 0.11

        dprint("SELF requests NODE to double sign")
        def on_response(response):
            assert response is None
            container["timeout"] += 1
        request = community.create_double_signed_text("Accept=<does not reach this point>", Member.get_instance(node.my_member.public_key), on_response, (), 3.0)
        yield 0.11

        dprint("NODE receives dispersy-signature-request message")
        _, message = node.receive_message(addresses=[address], message_names=[u"dispersy-signature-request"])
        # do not send a response

        # should time out
        for counter in range(4):
            dprint("waiting... ", 4 - counter)
            yield 1.0
        yield 0.11

        dprint("SELF must have timed out by now")
        assert container["timeout"] == 1, container["timeout"]

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

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
        yield 0.11

        # SELF requests NODE to double sign
        def on_response(response):
            assert container["response"] == 0, container["response"]
            assert request.authentication.is_signed
            container["response"] += 1
        request = community.create_double_signed_text("Accept=False", Member.get_instance(node.my_member.public_key), on_response, (), 3.0)
        yield 0.11

        # receive dispersy-signature-request message
        address, message = node.receive_message(addresses=[address], message_names=[u"dispersy-signature-request"])
        submsg = message.payload.message
        second_signature_offset = len(submsg.packet) - community.my_member.signature_length
        first_signature_offset = second_signature_offset - node.my_member.signature_length
        assert submsg.packet[second_signature_offset:] == "\x00" * node.my_member.signature_length
        signature = node.my_member.sign(submsg.packet, length=first_signature_offset)

        # send dispersy-signature-response message
        request_id = hashlib.sha1(request.packet).digest()
        global_time = community.global_time
        node.send_message(node.create_dispersy_signature_response_message(request_id, signature, global_time, address), address)

        # should not time out
        for counter in range(4):
            dprint("waiting... ", 4 - counter)
            yield 1.0
        yield 0.11

        assert container["response"] == 1, container["response"]

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

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
        yield 0.11

        # create node and ensure that SELF knows the node address
        node2 = Node()
        node2.init_socket()
        node2.set_community(community)
        node2.init_my_member()
        yield 0.11

        # SELF requests NODE1 and NODE2 to double sign
        def on_response(response):
            assert response is None
            container["timeout"] += 1
        request = community.create_triple_signed_text("Hello World!", Member.get_instance(node1.my_member.public_key), Member.get_instance(node2.my_member.public_key), on_response, (), 3.0)
        yield 0.11

        # receive dispersy-signature-request message
        _, message = node1.receive_message(addresses=[address], message_names=[u"dispersy-signature-request"])
        _, message = node2.receive_message(addresses=[address], message_names=[u"dispersy-signature-request"])
        # do not send a response

        # should time out
        for counter in range(4):
            dprint("waiting... ", 4 - counter)
            yield 1.0
        yield 0.11

        assert container["timeout"] == 1, container["timeout"]

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

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
        global_time = community.global_time
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
        global_time = community.global_time
        node2.send_message(node2.create_dispersy_signature_response_message(request_id, signature2, global_time, address), address)

        # should not time out
        for counter in range(4):
            dprint("waiting... ", 4 - counter)
            yield 1.0
        yield 0.11

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
        yield 0.11

        # node is NOT in self._my_member's subjective set.  the message MUST NOT be stored
        global_time = 10
        node.send_message(node.create_subjective_set_text_message("Must not be stored", global_time), address)
        yield 0.11
        times = [global_time for global_time, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert times == [], times

        # node is in self._my_member's subjective set.  the message MUST be stored
        community.create_dispersy_subjective_set(message.destination.cluster, [node.my_member])
        global_time = 20
        node.send_message(node.create_subjective_set_text_message("Must be stored", global_time), address)
        yield 0.11
        times = [global_time for global_time, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert times == [global_time]

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

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
        yield 0.11

        # make available the subjective set
        subjective_set = BloomFilter(100, 0.1)
        subjective_set.add(node.my_member.public_key)
        node.send_message(node.create_dispersy_subjective_set_message(meta_message.destination.cluster, subjective_set, 10), address)
        yield 0.11

        # SELF will store and forward for NODE
        community.create_dispersy_subjective_set(meta_message.destination.cluster, [node.my_member])
        global_time = 20
        node.send_message(node.create_subjective_set_text_message("Must be synced", global_time), address)
        yield 0.11
        times = [global_time for global_time, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, meta_message.database_id))]
        assert times == [global_time]

        # a dispersy-sync message MUST return the message that was just sent
        node.send_message(node.create_dispersy_sync_message(10, 0, [], 20), address)
        yield 0.11
        _, message = node.receive_message(addresses=[address], message_names=[u"subjective-set-text"])
        assert message.distribution.global_time == global_time

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

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
        yield 0.11

        # SELF will store and forward for NODE
        community.create_dispersy_subjective_set(meta_message.destination.cluster, [node.my_member])
        global_time = 20
        node.send_message(node.create_subjective_set_text_message("Must be stored", global_time), address)
        yield 0.11
        times = [global_time for global_time, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND user = ? AND name = ?", (community.database_id, node.my_member.database_id, meta_message.database_id))]
        assert times == [global_time]

        # a dispersy-sync message MUST return a dispersy-subjective-set-request message
        node.send_message(node.create_dispersy_sync_message(10, 0, [], 20), address)
        yield 0.11
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
        yield 0.11

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
#         yield 0.11

#         ##
#         ## Similar Nodes
#         ##

#         # create similarity for node-01
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b11111111), chr(0b00000000)), 0)
#         node.send_message(node.create_dispersy_similarity_message(1, community.database_id, bf, 20), address)
#         yield 0.11

#         msg = node.create_taste_aware_message(5, 10, 1)
#         msg_blob = node.encode_message(msg)
#         node.send_message(msg, address)
#         yield 0.11

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
#         yield 0.11

#         msg = node.create_taste_aware_message(5, 20, 2)
#         msg_blob = node.encode_message(msg)
#         node.send_message(msg, address)
#         yield 0.11

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
#         yield 0.11

#         # create second node - node-02
#         node2 = DebugNode()
#         node2.init_socket()
#         node2.set_community(community)
#         node2.init_my_member()
#         yield 0.11

#         ##
#         ## Similar Nodes Threshold 12 Similarity 14
#         ##
#         dprint("Testing similar nodes")

#         # create similarity for node-01
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b11110000), chr(0b00000000)), 0)
#         node.send_message(node.create_dispersy_similarity_message(1, community.database_id, bf, 20), address)
#         yield 0.11

#         # create similarity for node-02
#         # node node-02 has 14/16 same bits with node-01
#         # ABOVE threshold
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b10111000), chr(0b00000000)), 0)
#         node2.send_message(node2.create_dispersy_similarity_message(1, community.database_id, bf, 20), address)
#         yield 0.11

#         # node-01 creates and sends a message to 'self'
#         node.send_message(node.create_taste_aware_message(5, 10, 1), address)
#         yield 0.11

#         # node-02 sends an sync message with an empty bloomfilter
#         # to 'self'. It should collect the message
#         node2.send_message(node2.create_dispersy_sync_message(1, 100, [], 3), address)
#         yield 0.11

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
#         yield 0.11

#         # node-02 sends an sync message with an empty bloomfilter
#         # to 'self'. It should collect the message
#         node2.send_message(node2.create_dispersy_sync_message(1, 100, [], 3), address)
#         yield 0.11

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
#         yield 0.11

#         # node-02 sends an sync message with an empty bloomfilter
#         # to 'self'. It should collect the message
#         node2.send_message(node2.create_dispersy_sync_message(1, 100, [], 3), address)
#         yield 0.11

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
#         yield 0.11

#         # node-02 sends an sync message with an empty bloomfilter
#         # to 'self'. It should collect the message
#         node2.send_message(node2.create_dispersy_sync_message(1, 100, [], 3), address)
#         yield 0.11

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
#         yield 0.11

#         # create second node - node-02
#         node2 = DebugNode()
#         node2.init_socket()
#         node2.set_community(community)
#         node2.init_my_member()
#         yield 0.11

#         ##
#         ## Similar Nodes
#         ##
#         dprint("Testing similar nodes")

#         # create similarity for node-01
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b11110000), chr(0b00000000)), 0)
#         node.send_message(node.create_dispersy_similarity_message(2, community.database_id, bf, 20), address)
#         yield 0.11

#         # create similarity for node-02
#         # node node-02 has 15/16 same bits with node-01
#         # ABOVE threshold
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b10111000), chr(0b00000000)), 0)
#         node2.send_message(node2.create_dispersy_similarity_message(2, community.database_id, bf, 20), address)
#         yield 0.11

#         # node-01 creates and sends a message to 'self'
#         node.send_message(node.create_taste_aware_message_last(5, 30, 1), address)

#         # node-02 sends a sync message with an empty bloomfilter
#         # to 'self'. It should collect the message
#         node2.send_message(node2.create_dispersy_sync_message(1, 100, [], 3), address)
#         yield 0.11

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
#         yield 0.11

#         # node-02 sends an sync message with an empty bloomfilter
#         # to 'self'. It should collect the message
#         node2.send_message(node2.create_dispersy_sync_message(1, 100, [], 3), address)
#         yield 0.11

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
#         yield 0.11

#         # create similarity for node-01
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b11110000), chr(0b00000000)), 0)
#         node.send_message(node.create_dispersy_similarity_message(1, community.database_id, bf, 20), address)
#         yield 0.11

#         # create second node - node-02
#         node2 = DebugNode()
#         node2.init_socket()
#         node2.set_community(community)
#         node2.init_my_member()
#         yield 0.11

#         # node-01 creates and sends a message to 'self'
#         node.send_message(node.create_taste_aware_message(5, 10, 1), address)
#         yield 0.11

#         # node-02 sends a sync message with an empty bloomfilter
#         # to 'self'. It should collect the message
#         node2.send_message(node2.create_dispersy_sync_message(1, 100, [], 3), address)
#         yield 0.11

#         # because 'self' does not have our similarity
#         # we should first receive a 'dispersy-similarity-request' message
#         # and 'synchronize' e.g. send our similarity
#         _, message = node2.receive_message(addresses=[address], message_names=[u"dispersy-similarity-request"])

#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b10111000), chr(0b00000000)), 0)
#         node2.send_message(node2.create_dispersy_similarity_message(1, community.database_id, bf, 20), address)
#         yield 0.11

#         # receive the taste message
#         _, message = node2.receive_message(addresses=[address], message_names=[u"taste-aware-record"])
#         assert  message.payload.number == 5

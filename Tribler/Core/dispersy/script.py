# Python 2.5 features
from __future__ import with_statement

"""
Run some python code, usually to test one or more features.

@author: Boudewijn Schoon
@organization: Technical University Delft
@contact: dispersy@frayja.com
"""

from hashlib import sha1
from lencoder import log, make_valid_key
from random import shuffle
from time import time
import gc
import hashlib
import inspect
import socket

from bloomfilter import BloomFilter
from candidate import LoopbackCandidate
from crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin
from debug import Node
from dispersy import Dispersy
from dispersydatabase import DispersyDatabase
from dprint import dprint
# from lencoder import log
from member import Member
from message import BatchConfiguration, Message, DelayMessageByProof
from resolution import PublicResolution, LinearResolution
from singleton import Singleton

from debugcommunity import DebugCommunity, DebugNode

def assert_(value, *args):
    if not value:
        raise AssertionError(*args)

def assert_message_stored(community, member, global_time, undone="done"):
    assert isinstance(undone, str)
    assert undone in ("done", "undone")

    try:
        actual_undone, = community.dispersy.database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?", (community.database_id, member.database_id, global_time)).next()
    except StopIteration:
        self.assert_(False, "Message must be stored in the database (", community.database_id, ", ", member.database_id, ", ", global_time, ")")

    assert_(isinstance(actual_undone, int), type(actual_undone))
    assert_(0 <= actual_undone, actual_undone)
    assert_((undone == "done" and actual_undone == 0) or undone == "undone" and 0 < actual_undone, [undone, actual_undone])

class Script(Singleton):
    def __init__(self, callback):
        self._scripts = {}
        self._callback = callback
        self._testcases = []

    def add(self, name, script, kargs={}, include_with_all=True):
        assert_(isinstance(name, str))
        assert_(not name in self._scripts)
        assert_(issubclass(script, ScriptBase))
        self._scripts[name] = (include_with_all, script, kargs)

    def load(self, name):
        dprint(name)

        if name == "all":
            for name, (include_with_all, script, kargs) in self._scripts.iteritems():
                if include_with_all:
                    dprint(name)
                    script(self, name, **kargs)

        elif name in self._scripts:
            self._scripts[name][1](self, name, **self._scripts[name][2])

        else:
            for available in sorted(self._scripts):
                dprint("available: ", available, force=True)
            raise ValueError("Unknown script '%s'" % name)

    def add_testcase(self, call, args):
        if len(self._testcases) == 0:
            self._callback.register(self._next_testcase, priority=-1024)
        self._testcases.append((call, args))

    def _next_testcase(self, result=None):
        if isinstance(result, Exception):
            dprint("exception! shutdown", box=True, level="error")
            self._callback.stop(wait=False, exception=result)

        elif self._testcases:
            call, args = self._testcases.pop(0)
            dprint("start ", call, line=True, force=True)
            if call.__doc__:
                dprint(call.__doc__, box=True)
            self._callback.register(call, args, callback=self._next_testcase)

        else:
            dprint("shutdown", box=True)
            self._callback.stop(wait=False)

class ScriptBase(object):
    def __init__(self, script, name, **kargs):
        self._script = script
        self._name = name
        self._kargs = kargs
        self._dispersy = Dispersy.get_instance()
        self._dispersy_database = DispersyDatabase.get_instance()
        self._dispersy.callback.register(self.run)

    def caller(self, run, args=()):
        assert callable(run)
        assert isinstance(args, tuple)
        self._script.add_testcase(run, args)

    def run(self):
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
        assert_(isinstance(peername, str))
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
        """ Restore on_socket_endpoint and _send functions of
        dispersy back to normal.

        This simulates a node coming online, since it's able to send
        and receive messages.
        """
        log(self._logfile, "Going online")
        self._dispersy.on_socket_endpoint = self.original_on_socket_endpoint
        self._dispersy._send = self.original_send

    def set_offline(self):
        """ Replace on_socket_endpoint and _sends functions of
        dispersy with dummies

        This simulates a node going offline, since it's not able to
        send or receive any messages
        """
        def dummy_function(*params):
            return
        log(self._logfile, "Going offline")
        self._dispersy.on_socket_endpoint = dummy_function
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
        #when should we start the next step?
        expected_time = self._starting_timestamp + (self._timestep * (self._stepcount + 1))
        diff = expected_time - time()

        delay = max(0.0, diff)
        return delay

    def log_desync(self, desync):
        delay = 1.0 - desync
        log(self._logfile, "sleep", desync=desync, diff=delay, stepcount=self._stepcount)

    def join_community(self, my_member):
        pass

    def execute_scenario_cmds(self, commands):
        pass

    def run(self):
        if __debug__: log(self._logfile, "start-scenario-script")

        #
        # Read our configuration from the peer.conf file
        # name, ip, port, public and private key
        #
        with open('data/peer.conf') as fp:
            my_name, ip, port = fp.readline().split()
            my_address = (ip, int(port))

        if __debug__: log(self._logfile, "read-config-done", my_name = my_name, my_address = my_address)

        # create my member
        ec = ec_generate_key(u"low")
        my_member = Member(ec_to_public_bin(ec), ec_to_private_bin(ec))
        dprint("-my member- ", my_member.database_id, " ", id(my_member), " ", my_member.mid.encode("HEX"), force=1)

        self.original_on_socket_endpoint = self._dispersy.on_socket_endpoint
        self.original_send = self._dispersy._send

        # join the community with the newly created member
        self._community = self.join_community(my_member)
        dprint("Joined community ", self._community._my_member)

        log(self._logfile, "joined-community", name="time", value=time())
        log(self._logfile, "community-property", name="timestep", value=self._timestep)
        log(self._logfile, "community-property", name="sync_response_limit", value=self._community.dispersy_sync_response_limit)
        log(self._logfile, "community-property", name="starting_timestamp", value=self._starting_timestamp)

        self._stepcount = 0

        # wait until we reach the starting time
        self._dispersy.callback.register(self.do_steps, delay=self.sleep())

        # I finished the scenario execution. I should stay online
        # until killed. Note that I can still sync and exchange
        # messages with other peers.
        while True:
            # wait to be killed
            yield 100.0

    def do_steps(self):
        scenario_fp = open('data/bartercast.log')
        availability_fp = open('data/availability.log')

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

            #print statistics
            total_dropped = sum([amount for amount, bytes in self._dispersy._statistics._drop.itervalues()])
            log("dispersy.log", "statistics", total_send = self._dispersy._statistics._total_up, total_received = self._dispersy._statistics._total_down, total_dropped = total_dropped)

            total_received = {}
            for key, values in self._dispersy._statistics._success.iteritems():
                total_received[make_valid_key(key)] = values[0]

            if len(total_received) > 0:
                log("dispersy.log", "statistics-successful-messages", **total_received)

            total_dropped = {}
            for key, values in self._dispersy._statistics._drop.iteritems():
                total_dropped[make_valid_key(key)] = values[0]

            if len(total_dropped) > 0:
                log("dispersy.log", "statistics-dropped-messages", **total_dropped)

#            def callback_cmp(a, b):
#                return cmp(self._dispersy.callback._statistics[a][0], self._dispersy.callback._statistics[b][0])
#            keys = self._dispersy.callback._statistics.keys()
#            keys.sort(reverse = True)
#
#            total_run = {}
#            for key in keys[:10]:
#                total_run[make_valid_key(key)] = self._dispersy.callback._statistics[key]
#            if len(total_run) > 0:
#                log("dispersy.log", "statistics-callback-run", **total_run)

#            stats = Conversion.debug_stats
#            total = stats["encode-message"]
#            nice_total = {'encoded':stats["-encode-count"], 'total':"%.2fs"%total}
#            for key, value in sorted(stats.iteritems()):
#                if key.startswith("encode") and not key == "encode-message" and total:
#                    nice_total[make_valid_key(key)] = "%7.2fs ~%5.1f%%" % (value, 100.0 * value / total)
#            log("dispersy.log", "statistics-encode", **nice_total)
#
#            total = stats["decode-message"]
#            nice_total = {'decoded':stats["-decode-count"], 'total':"%.2fs"%total}
#            for key, value in sorted(stats.iteritems()):
#                if key.startswith("decode") and not key == "decode-message" and total:
#                    nice_total[make_valid_key(key)] = "%7.2fs ~%5.1f%%" % (value, 100.0 * value / total)
#            log("dispersy.log", "statistics-decode", **nice_total)

            desync = yield self._timestep
            self.log_desync(desync)

            self._stepcount += 1

class DispersyClassificationScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = Member(ec_to_public_bin(ec), ec_to_private_bin(ec))

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
        assert_([ClassTestA.load_community(master) for master in ClassTestA.get_master_members()] == [], "Did you remove the database before running this testcase?")
        assert_([ClassTestB.load_community(master) for master in ClassTestB.get_master_members()] == [], "Did you remove the database before running this testcase?")

        # create master member
        ec = ec_generate_key(u"high")
        master = Member(ec_to_public_bin(ec), ec_to_private_bin(ec))

        # create community
        self._dispersy_database.execute(u"INSERT INTO community (master, member, classification) VALUES (?, ?, ?)",
                                        (master.database_id, self._my_member.database_id, ClassTestA.get_classification()))

        # reclassify
        community = self._dispersy.reclassify_community(master, ClassTestB)
        assert_(isinstance(community, ClassTestB))
        assert_(community.cid == master.mid)
        try:
            classification, = self._dispersy_database.execute(u"SELECT classification FROM community WHERE master = ?", (master.database_id,)).next()
        except StopIteration:
            assert_(False)
        assert_(classification == ClassTestB.get_classification())

        # cleanup
        community.unload_community()

    def reclassify_loaded_community(self):
        """
        Load a community, reclassify it, load all communities of that classification to check.
        """
        class ClassTestC(DebugCommunity):
            pass

        class ClassTestD(DebugCommunity):
            pass

        # no communities should exist
        assert_([ClassTestC.load_community(master) for master in ClassTestC.get_master_members()] == [], "Did you remove the database before running this testcase?")
        assert_([ClassTestD.load_community(master) for master in ClassTestD.get_master_members()] == [], "Did you remove the database before running this testcase?")

        # create community
        community_c = ClassTestC.create_community(self._my_member)
        assert_(len(list(self._dispersy_database.execute(u"SELECT * FROM community WHERE classification = ?", (ClassTestC.get_classification(),)))) == 1)

        # reclassify
        community_d = self._dispersy.reclassify_community(community_c, ClassTestD)
        assert_(isinstance(community_d, ClassTestD))
        assert_(community_c.cid == community_d.cid)
        try:
            classification, = self._dispersy_database.execute(u"SELECT classification FROM community WHERE master = ?", (community_c.master_member.database_id,)).next()
        except StopIteration:
            assert_(False)
        assert_(classification == ClassTestD.get_classification())

        # cleanup
        community_d.unload_community()

    def load_no_communities(self):
        """
        Try to load communities of a certain classification while there are no such communities.
        """
        class ClassificationLoadNoCommunities(DebugCommunity):
            pass
        assert_([ClassificationLoadNoCommunities.load_community(master) for master in ClassificationLoadNoCommunities.get_master_members()] == [], "Did you remove the database before running this testcase?")

    def load_one_communities(self):
        """
        Try to load communities of a certain classification while there is exactly one such
        community available.
        """
        class ClassificationLoadOneCommunities(DebugCommunity):
            pass

        # no communities should exist
        assert_([ClassificationLoadOneCommunities.load_community(master) for master in ClassificationLoadOneCommunities.get_master_members()] == [], "Did you remove the database before running this testcase?")

        # create master member
        ec = ec_generate_key(u"high")
        master = Member(ec_to_public_bin(ec), ec_to_private_bin(ec))

        # create one community
        self._dispersy_database.execute(u"INSERT INTO community (master, member, classification) VALUES (?, ?, ?)",
                                        (master.database_id, self._my_member.database_id, ClassificationLoadOneCommunities.get_classification()))

        # load one community
        communities = [ClassificationLoadOneCommunities.load_community(master) for master in ClassificationLoadOneCommunities.get_master_members()]
        assert_(len(communities) == 1)
        assert_(isinstance(communities[0], ClassificationLoadOneCommunities))

        # cleanup
        communities[0].unload_community()

    def load_two_communities(self):
        """
        Try to load communities of a certain classification while there is exactly two such
        community available.
        """
        class LoadTwoCommunities(DebugCommunity):
            pass

        # no communities should exist
        assert_([LoadTwoCommunities.load_community(master) for master in LoadTwoCommunities.get_master_members()] == [])

        masters = []
        # create two communities
        community = LoadTwoCommunities.create_community(self._my_member)
        masters.append(community.master_member.public_key)
        community.unload_community()

        community = LoadTwoCommunities.create_community(self._my_member)
        masters.append(community.master_member.public_key)
        community.unload_community()

        # load two communities
        assert_(sorted(masters) == sorted(master.public_key for master in LoadTwoCommunities.get_master_members()))
        communities = [LoadTwoCommunities.load_community(master) for master in LoadTwoCommunities.get_master_members()]
        assert_(sorted(masters) == sorted(community.master_member.public_key for community in communities))
        assert_(len(communities) == 2, len(communities))
        assert_(isinstance(communities[0], LoadTwoCommunities))
        assert_(isinstance(communities[1], LoadTwoCommunities))

        # cleanup
        communities[0].unload_community()
        communities[1].unload_community()

    def unloading_community(self):
        """
        Test that calling community.unload_community() eventually results in a call to
        community.__del__().
        """
        class ClassificationUnloadingCommunity(DebugCommunity):
            pass

        def check(verbose=False):
            # using a function to ensure all local variables are removed (scoping)

            i = 0
            j = 0
            for x in gc.get_objects():
                if isinstance(x, ClassificationUnloadingCommunity):
                    i += 1
                    for obj in gc.get_referrers(x):
                        j += 1
                        if verbose:
                            dprint(type(obj))
                            try:
                                lines, lineno = inspect.getsourcelines(obj)
                                dprint([line.rstrip() for line in lines], lines=1)
                            except TypeError:
                                dprint("TypeError")
                                pass

            dprint(j, " referrers")
            return i

        community = ClassificationUnloadingCommunity.create_community(self._my_member)
        master = community.master_member
        cid = community.cid
        del community
        assert_(isinstance(self._dispersy.get_community(cid), ClassificationUnloadingCommunity))
        assert_(check() == 1)

        # unload the community
        self._dispersy.get_community(cid).unload_community()
        try:
            self._dispersy.get_community(cid, auto_load=False)
            assert_(False)
        except KeyError:
            pass

        # must be garbage collected
        wait = 10
        for i in range(wait):
            gc.collect()
            dprint("waiting... ", wait - i)
            if check() == 0:
                break
            else:
                yield 1.0
        assert_(check(True) == 0)

        # load the community for cleanup
        community = ClassificationUnloadingCommunity.load_community(master)
        assert_(check() == 1)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def enable_autoload(self):
        """
        - Create community
        - Enable auto-load (should be enabled by default)
        - Define auto load
        - Unload community
        - Send community message
        - Verify that the community got auto-loaded
        - Undefine auto load
        """
        # create community
        community = DebugCommunity.create_community(self._my_member)
        cid = community.cid
        message = community.get_meta_message(u"full-sync-text")

        # create node
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member(candidate=False)
        yield 0.555

        dprint("verify auto-load is enabled (default)")
        assert_(community.dispersy_auto_load == True)
        yield 0.555

        dprint("define auto load")
        self._dispersy.define_auto_load(DebugCommunity)
        yield 0.555

        dprint("create wake-up message")
        global_time = 10
        wakeup = node.encode_message(node.create_full_sync_text_message("Should auto-load", global_time))

        dprint("unload community")
        community.unload_community()
        community = None
        node.set_community(None)
        try:
            self._dispersy.get_community(cid, auto_load=False)
            assert_(False)
        except KeyError:
            pass
        yield 0.555

        dprint("send community message")
        node.give_packet(wakeup)
        yield 0.555

        dprint("verify that the community got auto-loaded")
        try:
            community = self._dispersy.get_community(cid)
        except KeyError:
            assert_(False)
        # verify that the message was received
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert_(global_time in times)
        yield 0.555

        dprint("undefine auto load")
        self._dispersy.undefine_auto_load(DebugCommunity)
        yield 0.555

        dprint("cleanup")
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def enable_disable_autoload(self):
        """
        - Create community
        - Enable auto-load (should be enabled by default)
        - Define auto load
        - Unload community
        - Send community message
        - Verify that the community got auto-loaded
        - Disable auto-load
        - Send community message
        - Verify that the community did NOT get auto-loaded
        - Undefine auto load
        """
        # create community
        community = DebugCommunity.create_community(self._my_member)
        cid = community.cid
        community_database_id = community.database_id
        master_member = community.master_member
        message = community.get_meta_message(u"full-sync-text")

        # create node
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member(candidate=False)

        dprint("verify auto-load is enabled (default)")
        assert_(community.dispersy_auto_load == True)

        dprint("define auto load")
        self._dispersy.define_auto_load(DebugCommunity)

        dprint("create wake-up message")
        global_time = 10
        wakeup = node.encode_message(node.create_full_sync_text_message("Should auto-load", global_time))

        dprint("unload community")
        community.unload_community()
        community = None
        node.set_community(None)
        try:
            self._dispersy.get_community(cid, auto_load=False)
            assert_(False)
        except KeyError:
            pass

        dprint("send community message")
        node.give_packet(wakeup)

        dprint("verify that the community got auto-loaded")
        try:
            community = self._dispersy.get_community(cid)
        except KeyError:
            assert_(False)
        # verify that the message was received
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert_(global_time in times)

        dprint("disable auto-load")
        community.dispersy_auto_load = False
        assert_(community.dispersy_auto_load == False)

        dprint("create wake-up message")
        node.set_community(community)
        global_time = 11
        wakeup = node.encode_message(node.create_full_sync_text_message("Should auto-load", global_time))

        dprint("unload community")
        community.unload_community()
        community = None
        node.set_community(None)
        try:
            self._dispersy.get_community(cid, auto_load=False)
            assert_(False)
        except KeyError:
            pass

        dprint("send community message")
        node.give_packet(wakeup)

        dprint("verify that the community did not get auto-loaded")
        try:
            self._dispersy.get_community(cid, auto_load=False)
            assert_(False)
        except KeyError:
            pass
        # verify that the message was NOT received
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community_database_id, node.my_member.database_id, message.database_id))]
        assert_(not global_time in times)

        dprint("undefine auto load")
        self._dispersy.undefine_auto_load(DebugCommunity)

        dprint("cleanup")
        community = DebugCommunity.load_community(master_member)
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

class DispersyTimelineScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = Member(ec_to_public_bin(ec), ec_to_private_bin(ec))

        self.caller(self.succeed_check)
        self.caller(self.fail_check)
        self.caller(self.loading_community)
        self.caller(self.delay_by_proof)
        self.caller(self.missing_proof)
        self.caller(self.missing_authorize_proof)

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
        yield 0.555

        dprint("master_member: ", community.master_member.database_id, ", ", community.master_member.mid.encode("HEX"))
        dprint("    my_member: ", community.my_member.database_id, ", ", community.my_member.mid.encode("HEX"))

        # check if we are still allowed to send the message
        message = community.create_dispersy_destroy_community(u"hard-kill", store=False, update=False, forward=False)
        assert_(message.authentication.member == self._my_member)
        result = list(message.check_callback([message]))
        assert_(result == [message], "check_... methods should return a generator with the accepted messages")

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

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
        yield 0.555

        dprint("master_member: ", community.master_member.database_id, ", ", community.master_member.mid.encode("HEX"))
        dprint("    my_member: ", community.my_member.database_id, ", ", community.my_member.mid.encode("HEX"))

        # remove the right to hard-kill
        community.create_dispersy_revoke([(community.my_member, community.get_meta_message(u"dispersy-destroy-community"), u"permit")], sign_with_master=True, store=False, forward=False)

        # check if we are still allowed to send the message
        message = community.create_dispersy_destroy_community(u"hard-kill", store=False, update=False, forward=False)
        assert_(message.authentication.member == self._my_member)
        result = list(message.check_callback([message]))
        assert_(len(result) == 1, "check_... methods should return a generator with the accepted messages")
        assert_(isinstance(result[0], DelayMessageByProof), "check_... methods should return a generator with the accepted messages")

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill", sign_with_master=True)
        self._dispersy.get_community(community.cid).unload_community()

    def loading_community(self):
        """
        When a community is loaded it must load all available dispersy-authorize and dispersy-revoke
        message from the database.
        """
        class LoadingCommunityTestCommunity(DebugCommunity):
            pass

        # create a community.  the master member must have given my_member all permissions for
        # dispersy-destroy-community
        community = LoadingCommunityTestCommunity.create_community(self._my_member)
        cid = community.cid

        dprint("master_member: ", community.master_member.database_id, ", ", community.master_member.mid.encode("HEX"))
        dprint("    my_member: ", community.my_member.database_id, ", ", community.my_member.mid.encode("HEX"))

        dprint("unload community")
        community.unload_community()
        community = None
        yield 0.555

        # load the same community and see if the same permissions are loaded
        communities = [LoadingCommunityTestCommunity.load_community(master) for master in LoadingCommunityTestCommunity.get_master_members()]
        assert_(len(communities) == 1)
        assert_(communities[0].cid == cid)
        community = communities[0]

        # check if we are still allowed to send the message
        message = community.create_dispersy_destroy_community(u"hard-kill", store=False, update=False, forward=False)
        assert_(community._timeline.check(message))

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def delay_by_proof(self):
        """
        When SELF receives a message that it has no permission for, it will send a
        dispersy-missing-proof message to try to obtain the dispersy-authorize.
        """
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()

        # create node and ensure that SELF knows the node address
        node1 = DebugNode()
        node1.init_socket()
        node1.set_community(community)
        node1.init_my_member()
        yield 0.555

        # create node and ensure that SELF knows the node address
        node2 = DebugNode()
        node2.init_socket()
        node2.set_community(community)
        node2.init_my_member()
        yield 0.555

        # permit NODE1
        dprint("SELF creates dispersy-authorize for NODE1")
        community.create_dispersy_authorize([(node1.my_member, community.get_meta_message(u"protected-full-sync-text"), u"permit"),
                                             (node1.my_member, community.get_meta_message(u"protected-full-sync-text"), u"authorize")])

        # NODE2 created message @20
        dprint("NODE2 creates protected-full-sync-text, should be delayed for missing proof")
        global_time = 20
        message = node2.create_protected_full_sync_text_message("Protected message", global_time)
        node2.give_message(message)
        yield 0.555

        # may NOT have been stored in the database
        try:
            packet, =  self._dispersy_database.execute(u"SELECT packet FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                       (community.database_id, node2.my_member.database_id, global_time)).next()
        except StopIteration:
            pass

        else:
            assert_(False, "should not have stored, did not have permission")

        # SELF sends dispersy-missing-proof to NODE2
        dprint("NODE2 receives dispersy-missing-proof")
        _, message = node2.receive_message(addresses=[address], message_names=[u"dispersy-missing-proof"])
        assert_(message.payload.member.public_key == node2.my_member.public_key)
        assert_(message.payload.global_time == global_time)

        dprint("=====")
        dprint("node1: ", node1.my_member.database_id)
        dprint("node2: ", node2.my_member.database_id)

        # NODE1 provides proof
        dprint("NODE1 creates and provides missing proof")
        sequence_number = 1
        proof_global_time = 10
        node2.give_message(node1.create_dispersy_authorize([(node2.my_member, community.get_meta_message(u"protected-full-sync-text"), u"permit")], sequence_number, proof_global_time))
        yield 0.555

        dprint("=====")

        # must have been stored in the database
        dprint("SELF must have processed both the proof and the protected-full-sync-text message")
        try:
            packet, =  self._dispersy_database.execute(u"SELECT packet FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                       (community.database_id, node2.my_member.database_id, global_time)).next()
        except StopIteration:
            assert_(False, "should have been stored")

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def missing_proof(self):
        """
        When SELF receives a dispersy-missing-proof message she needs to find and send the proof.
        """
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.555

        # SELF creates a protected message
        message = community.create_protected_full_sync_text("Protected message")

        # flush incoming socket buffer
        node.drop_packets()

        # NODE pretends to receive the protected message and requests the proof
        node.give_message(node.create_dispersy_missing_proof_message(message.authentication.member, message.distribution.global_time))
        yield 0.555

        # SELF sends dispersy-authorize to NODE
        _, authorize = node.receive_message(addresses=[address], message_names=[u"dispersy-authorize"])

        permission_triplet = (community.my_member, community.get_meta_message(u"protected-full-sync-text"), u"permit")
        assert_(permission_triplet in authorize.payload.permission_triplets)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def missing_authorize_proof(self):
        """
             MASTER
               \\        authorize(MASTER, OWNER)
                \\
                OWNER
                  \\        authorize(OWNER, NODE1)
                   \\
                   NODE1

        When SELF receives a dispersy-missing-proof message from NODE2 for authorize(OWNER, NODE1)
        the dispersy-authorize message for authorize(MASTER, OWNER) must be returned.
        """
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()

        # create node and ensure that SELF knows the node address
        node1 = DebugNode()
        node1.init_socket()
        node1.set_community(community)
        node1.init_my_member()
        yield 0.555

        # create node and ensure that SELF knows the node address
        node2 = DebugNode()
        node2.init_socket()
        node2.set_community(community)
        node2.init_my_member()
        yield 0.555

        # permit NODE1
        dprint("SELF creates dispersy-authorize for NODE1")
        message = community.create_dispersy_authorize([(node1.my_member, community.get_meta_message(u"protected-full-sync-text"), u"permit"),
                                                       (node1.my_member, community.get_meta_message(u"protected-full-sync-text"), u"authorize")])

        # flush incoming socket buffer
        node2.drop_packets()

        dprint("===")
        dprint("master: ", community.master_member.database_id)
        dprint("member: ", community.my_member.database_id)
        dprint("node1:  ", node1.my_member.database_id)
        dprint("node2:  ", node2.my_member.database_id)

        # NODE2 wants the proof that OWNER is allowed to grant authorization to NODE1
        dprint("NODE2 asks for proof that NODE1 is allowed to authorize")
        node2.give_message(node2.create_dispersy_missing_proof_message(message.authentication.member, message.distribution.global_time))
        yield 0.555

        dprint("===")

        # SELF sends dispersy-authorize containing authorize(MASTER, OWNER) to NODE
        dprint("NODE2 receives the proof from SELF")
        _, authorize = node2.receive_message(addresses=[address], message_names=[u"dispersy-authorize"])

        permission_triplet = (message.authentication.member, community.get_meta_message(u"protected-full-sync-text"), u"permit")
        dprint((permission_triplet[0].database_id, permission_triplet[1].name, permission_triplet[2]))
        dprint([(x.database_id, y.name, z) for x, y, z in authorize.payload.permission_triplets], lines=1)
        assert_(permission_triplet in authorize.payload.permission_triplets)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

class DispersyDestroyCommunityScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = Member(ec_to_public_bin(ec), ec_to_private_bin(ec))

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

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id)))
        assert_(len(times) == 0, times)

        # send a message
        global_time = 10
        node.give_message(node.create_full_sync_text_message("should be accepted (1)", global_time))
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert_(len(times) == 1)
        assert_(global_time in times)

        # destroy the community
        community.create_dispersy_destroy_community(u"hard-kill")
        yield 0.555

        # node should receive the dispersy-destroy-community message
        _, message = node.receive_message(addresses=[address], message_names=[u"dispersy-destroy-community"])
        assert_(not message.payload.is_soft_kill)
        assert_(message.payload.is_hard_kill)

        # the malicious_proof table must be empty
        assert_(not list(self._dispersy_database.execute(u"SELECT * FROM malicious_proof WHERE community = ?", (community.database_id,))))

        # the database should have been cleaned
        # todo

class DispersyMemberTagScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = Member(ec_to_public_bin(ec), ec_to_private_bin(ec))

        self.caller(self.ignore_test)
        self.caller(self.blacklist_test)

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
        yield 0.555

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id)))
        assert_(len(times) == 0, times)

        # send a message
        global_time = 10
        node.give_message(node.create_full_sync_text_message("should be accepted (1)", global_time))
        yield 0.555
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert_(times == [10], times)

        # we now tag the member as ignore
        Member(node.my_member.public_key).must_ignore = True

        tags, = self._dispersy_database.execute(u"SELECT tags FROM member WHERE id = ?", (node.my_member.database_id,)).next()
        assert_(u"ignore" in tags.split(","))

        # send a message and ensure it is in the database (ignore still means it must be stored in
        # the database)
        global_time = 20
        node.give_message(node.create_full_sync_text_message("should be accepted (2)", global_time))
        yield 0.555
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert_(sorted(times) == [10, 20], times)

        # we now tag the member not to ignore
        Member(node.my_member.public_key).must_ignore = False

        # send a message
        global_time = 30
        node.give_message(node.create_full_sync_text_message("should be accepted (3)", global_time))
        yield 0.555
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert_(sorted(times) == [10, 20, 30], times)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def blacklist_test(self):
        """
        Test the must_blacklist = True feature.

        When we 'blacklist' a specific member we will no longer accept or store messages from that
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
        yield 0.555

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id)))
        assert_(len(times) == 0, times)

        # send a message
        global_time = 10
        node.give_message(node.create_full_sync_text_message("should be accepted (1)", global_time))
        yield 0.555
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert_(len(times) == 1)
        assert_(global_time in times)

        # we now tag the member as blacklist
        Member(node.my_member.public_key).must_blacklist = True

        tags, = self._dispersy_database.execute(u"SELECT tags FROM member WHERE id = ?", (node.my_member.database_id,)).next()
        assert_(u"blacklist" in tags.split(","))

        # send a message and ensure it is not in the database
        global_time = 20
        node.give_message(node.create_full_sync_text_message("should NOT be accepted (2)", global_time))
        yield 0.555
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert_(len(times) == 1)
        assert_(global_time not in times)

        # we now tag the member not to blacklist
        Member(node.my_member.public_key).must_blacklist = False

        # send a message
        global_time = 30
        node.give_message(node.create_full_sync_text_message("should be accepted (3)", global_time))
        yield 0.555
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert_(len(times) == 2)
        assert_(global_time in times)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

class DispersyBatchScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"very-low")
        self._my_member = Member(ec_to_public_bin(ec), ec_to_private_bin(ec))

        # duplicate messages are removed
        self.caller(self.one_batch_binary_duplicate)
        self.caller(self.two_batches_binary_duplicate)
        self.caller(self.one_batch_member_global_time_duplicate)
        self.caller(self.two_batches_member_global_time_duplicate)

        # batches
        length = 1000
        max_size = 25
        self._results = []
        self.caller(self.max_batch_size, (length - 1, max_size))
        self.caller(self.max_batch_size, (length, max_size))
        self.caller(self.max_batch_size, (length + 1, max_size))
        self.caller(self.one_big_batch, (length,))
        self.caller(self.many_small_batches, (length,))

    def one_batch_binary_duplicate(self):
        """
        When multiple binary identical UDP packets are received, the duplicate packets need to be
        reduced to one packet.
        """
        community = DebugCommunity.create_community(self._my_member)

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        global_time = 10
        message = node.create_full_sync_text_message("duplicates", global_time)
        node.give_packets([message.packet for _ in xrange(10)])

        # only one message may be in the database
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert_(times == [global_time], (times, [global_time]))

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def two_batches_binary_duplicate(self):
        """
        When multiple binary identical UDP packets are received, the duplicate packets need to be
        reduced to one packet.

        The second batch needs to be dropped aswell, while the last unique packet of the second
        batch is dropped when the when the database is consulted.
        """
        community = DebugCommunity.create_community(self._my_member)

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        global_time = 10
        # first batch
        message = node.create_full_sync_text_message("duplicates", global_time)
        node.give_packets([message.packet for _ in xrange(10)])

        # only one message may be in the database
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert_(times == [global_time], times, [global_time])

        # second batch
        node.give_packets([message.packet for _ in xrange(10)])

        # only one message may be in the database
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert_(times == [global_time], times, [global_time])

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def one_batch_member_global_time_duplicate(self):
        """
        A member can create invalid duplicate messages that are binary different.

        For instance, two different messages that are created by the same member and have the same
        global_time, will be binary different while they are still duplicates.  Because dispersy
        uses the message creator and the global_time to uniquely identify messages.
        """
        community = DebugCommunity.create_community(self._my_member)
        meta = community.get_meta_message(u"full-sync-text")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        global_time = 10
        node.give_messages([node.create_full_sync_text_message("duplicates (%d)" % index, global_time) for index in xrange(10)])

        # only one message may be in the database
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, meta.database_id))]
        assert_(times == [global_time], times, [global_time])

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def two_batches_member_global_time_duplicate(self):
        """
        A member can create invalid duplicate messages that are binary different.

        For instance, two different messages that are created by the same member and have the same
        global_time, will be binary different while they are still duplicates.  Because dispersy
        uses the message creator and the global_time to uniquely identify messages.

        The second batch needs to be dropped aswell, while the last unique packet of the second
        batch is dropped when the when the database is consulted.
        """
        community = DebugCommunity.create_community(self._my_member)
        meta = community.get_meta_message(u"full-sync-text")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        global_time = 10
        # first batch
        node.give_messages([node.create_full_sync_text_message("duplicates (%d)" % index, global_time) for index in xrange(10)])

        # only one message may be in the database
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, meta.database_id))]
        assert_(times == [global_time])

        # second batch
        node.give_messages([node.create_full_sync_text_message("duplicates (%d)" % index, global_time) for index in xrange(10)])

        # only one message may be in the database
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, meta.database_id))]
        assert_(times == [global_time])

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def max_batch_size(self, length, max_size):
        """
        Gives many messages at once, the system should process them in max-batch-size batches.
        """
        class MaxBatchSizeCommunity(DebugCommunity):
            def _initialize_meta_messages(self):
                super(MaxBatchSizeCommunity, self)._initialize_meta_messages()

                batch = BatchConfiguration(max_window=0.01, max_size=max_size)

                meta = self._meta_messages[u"full-sync-text"]
                meta = Message(meta.community, meta.name, meta.authentication, meta.resolution, meta.distribution, meta.destination, meta.payload, meta.check_callback, meta.handle_callback, meta.undo_callback, batch=batch)
                self._meta_messages[meta.name] = meta

        community = MaxBatchSizeCommunity.create_community(self._my_member)

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        dprint("START BIG BATCH (with max batch size)")
        messages = [node.create_full_sync_text_message("Dprint=False, big batch #%d" % global_time, global_time) for global_time in xrange(10, 10 + length)]

        begin = time()
        node.give_messages(messages, cache=True)

        # wait till the batch is processed
        meta = community.get_meta_message(u"full-sync-text")
        while meta in self._dispersy._batch_cache:
            yield 0.1

        end = time()
        self._results.append("%2.2f seconds for max_batch_size(%d, %d)" % (end - begin, length, max_size))
        dprint(self._results, lines=1)

        count, = self._dispersy_database.execute(u"SELECT COUNT(1) FROM sync WHERE meta_message = ?", (meta.database_id,)).next()
        assert_(count == len(messages))

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def one_big_batch(self, length):
        """
        Each community is handled in its own batch, hence we can measure performace differences when
        we make one large batch (using one community) and many small batches (using many different
        communities).
        """
        community = DebugCommunity.create_community(self._my_member)

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        dprint("START BIG BATCH")
        messages = [node.create_full_sync_text_message("Dprint=False, big batch #%d" % global_time, global_time) for global_time in xrange(10, 10 + length)]

        begin = time()
        node.give_messages(messages)
        end = time()
        self._results.append("%2.2f seconds for one_big_batch(%d)" % (end - begin, length))
        dprint(self._results, lines=1)

        meta = community.get_meta_message(u"full-sync-text")
        count, = self._dispersy_database.execute(u"SELECT COUNT(1) FROM sync WHERE meta_message = ?", (meta.database_id,)).next()
        assert_(count == len(messages))

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def many_small_batches(self, length):
        """
        Each community is handled in its own batch, hence we can measure performace differences when
        we make one large batch (using one community) and many small batches (using many different
        communities).
        """
        community = DebugCommunity.create_community(self._my_member)

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        dprint("START SMALL BATCHES")
        messages = [node.create_full_sync_text_message("Dprint=False, small batch #%d" % global_time, global_time) for global_time in xrange(10, 10 + length)]

        begin = time()
        for message in messages:
            node.give_message(message)
        end = time()
        self._results.append("%2.2f seconds for many_small_batches(%d)" % (end - begin, length))
        dprint(self._results, lines=1)
        # assert_(self._big_batch_took < self._small_batches_took * 1.1, [self._big_batch_took, self._small_batches_took])

        meta = community.get_meta_message(u"full-sync-text")
        count, = self._dispersy_database.execute(u"SELECT COUNT(1) FROM sync WHERE meta_message = ?", (meta.database_id,)).next()
        assert_(count == len(messages))

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

class DispersySyncScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = Member(ec_to_public_bin(ec), ec_to_private_bin(ec))

        # modulo sync handling
        self.caller(self.modulo_test)

        # different sync policies
        self.caller(self.in_order_test)
        self.caller(self.out_order_test)
        self.caller(self.mixed_order_test)
        self.caller(self.last_1_test)
        self.caller(self.last_9_test)

        # multimember authentication and last sync policies
        self.caller(self.last_1_multimember)
        self.caller(self.last_1_multimember_unique_member_global_time)
        # # TODO add more checks for the multimemberauthentication case
        # self.caller(self.last_9_multimember)

    def modulo_test(self):
        """
        SELF creates several messages, NODE asks for specific modulo to sync and only those modulo
        may be sent back.
        """
        community = DebugCommunity.create_community(self._my_member)
        message = community.get_meta_message(u"full-sync-text")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        # SELF creates messages
        messages = [community.create_full_sync_text("foo-bar", forward=False) for _ in xrange(30)]

        for modulo in xrange(0, 10):
            for offset in xrange(0, modulo):
                # global times that we should receive
                global_times = [message.distribution.global_time for message in messages if (message.distribution.global_time + offset) % modulo == 0]

                sync = (1, 0, modulo, offset, [])
                node.drop_packets()
                node.give_message(node.create_dispersy_introduction_request_message(community.my_candidate, node.lan_address, node.wan_address, False, u"unknown", sync, 42, 110))

                received = []
                while True:
                    try:
                        _, message = node.receive_message(message_names=[u"full-sync-text"])
                        received.append(message.distribution.global_time)
                    except socket.error:
                        break

                assert_(sorted(global_times) == sorted(received), sorted(global_times), sorted(received), modulo, offset)
                dprint("%", modulo, "+", offset, ": ", sorted(global_times), " -> OK")

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def in_order_test(self):
        community = DebugCommunity.create_community(self._my_member)
        message = community.get_meta_message(u"ASC-text")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id)))
        assert_(len(times) == 0, times)

        # create some data
        global_times = range(10, 15)
        for global_time in global_times:
            node.give_message(node.create_in_order_text_message("Message #%d" % global_time, global_time))

        # send an empty sync message to obtain all messages ASC
        node.give_message(node.create_dispersy_introduction_request_message(community.my_candidate, node.lan_address, node.wan_address, False, u"unknown", (min(global_times), 0, 1, 0, []), 42, max(global_times)))
        yield 0.1

        for global_time in global_times:
            _, message = node.receive_message(message_names=[u"ASC-text"])
            assert_(message.distribution.global_time == global_time)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def out_order_test(self):
        community = DebugCommunity.create_community(self._my_member)
        message = community.get_meta_message(u"DESC-text")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id)))
        assert_(len(times) == 0, times)

        # create some data
        global_times = range(10, 15)
        for global_time in global_times:
            node.give_message(node.create_out_order_text_message("Message #%d" % global_time, global_time))

        # send an empty sync message to obtain all messages DESC
        node.give_message(node.create_dispersy_introduction_request_message(community.my_candidate, node.lan_address, node.wan_address, False, u"unknown", (min(global_times), 0, 1, 0, []), 42, max(global_times)))
        yield 0.1

        for global_time in reversed(global_times):
            _, message = node.receive_message(message_names=[u"DESC-text"])
            assert_(message.distribution.global_time == global_time)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def mixed_order_test(self):
        community = DebugCommunity.create_community(self._my_member)
        in_order_message = community.get_meta_message(u"ASC-text")
        out_order_message = community.get_meta_message(u"DESC-text")
        # random_order_message = community.get_meta_message(u"random-order-text")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT sync.global_time FROM sync JOIN reference_member_sync ON (reference_member_sync.sync = sync.id) WHERE sync.community = ? AND reference_member_sync.member = ? AND sync.meta_message IN (?, ?)", (community.database_id, node.my_member.database_id, in_order_message.database_id, out_order_message.database_id)))
        #, random_order_message.database_id)))
        assert_(len(times) == 0, times)

        # create some data
        global_times = range(10, 25, 2)
        in_order_times = []
        out_order_times = []
        # random_order_times = []
        for global_time in global_times:
            in_order_times.append(global_time)
            node.give_message(node.create_in_order_text_message("Message #%d" % global_time, global_time))
            global_time += 1
            out_order_times.append(global_time)
            node.give_message(node.create_out_order_text_message("Message #%d" % global_time, global_time))
            # global_time += 1
            # random_order_times.append(global_time)
            # node.give_message(node.create_random_order_text_message("Message #%d" % global_time, global_time))
        out_order_times.sort(reverse=True)
        dprint("Total ASC:", len(in_order_times), "; DESC:", len(out_order_times))#, "; rand:", len(random_order_times))

        def get_messages_back():
            received_times = []
            for _ in range(len(global_times) * 2):
                _, message = node.receive_message(message_names=[u"ASC-text", u"DESC-text"])
                #, u"random-order-text"])
                received_times.append(message.distribution.global_time)

            return received_times

        # lists = []
        for _ in range(5):
            # send an empty sync message to obtain all messages in random-order
            node.give_message(node.create_dispersy_introduction_request_message(community.my_candidate, node.lan_address, node.wan_address, False, u"unknown", (min(global_times), 0, 1, 0, []), 42, max(global_times)))
            yield 0.1

            received_times = get_messages_back()

            # followed by DESC
            received_out_times = received_times[0:len(out_order_times)]
            assert_(out_order_times == received_out_times, (out_order_times, received_out_times))

            # the first items must be ASC
            received_in_times = received_times[len(out_order_times):len(in_order_times) + len(out_order_times)]
            assert_(in_order_times == received_in_times, (in_order_times, received_in_times))

            # # followed by random-order
            # received_random_times = received_times[len(in_order_times) + len(out_order_times):]
            # for global_time in received_random_times:
            #     assert_(global_time in random_order_times)

            # if not received_times in lists:
            #     lists.append(received_times)

        # dprint(lists, lines=True)
        # assert_(len(lists) > 1)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def last_1_test(self):
        community = DebugCommunity.create_community(self._my_member)
        message = community.get_meta_message(u"last-1-test")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id)))
        assert_(len(times) == 0, times)

        # send a message
        global_time = 10
        node.give_message(node.create_last_1_test_message("should be accepted (1)", global_time))
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert_(len(times) == 1)
        assert_(global_time in times)

        # send a message
        global_time = 11
        node.give_message(node.create_last_1_test_message("should be accepted (2)", global_time))
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert_(len(times) == 1, len(times))
        assert_(global_time in times)

        # send a message (older: should be dropped)
        node.give_message(node.create_last_1_test_message("should be dropped (1)", 8))
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert_(len(times) == 1)
        assert_(global_time in times)

        # as proof for the drop, the newest message should be sent back
        yield 0.1
        _, message = node.receive_message(message_names=[u"last-1-test"])
        assert_(message.distribution.global_time == 11)

        # send a message (duplicate: should be dropped)
        node.give_message(node.create_last_1_test_message("should be dropped (2)", global_time))
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert_(len(times) == 1)
        assert_(global_time in times)

        # send a message
        global_time = 12
        node.give_message(node.create_last_1_test_message("should be accepted (3)", global_time))
        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert_(len(times) == 1)
        assert_(global_time in times)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def last_9_test(self):
        community = DebugCommunity.create_community(self._my_member)
        message = community.get_meta_message(u"last-9-test")

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        # should be no messages from NODE yet
        times = list(self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id)))
        assert_(len(times) == 0)

        number_of_messages = 0
        for global_time in [21, 20, 28, 27, 22, 23, 24, 26, 25]:
            # send a message
            message = node.create_last_9_test_message(str(global_time), global_time)
            node.give_message(message)
            number_of_messages += 1
            try:
                packet, = self._dispersy_database.execute(u"SELECT packet FROM sync WHERE community = ? AND member = ? AND global_time = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, global_time, message.database_id)).next()
            except StopIteration:
                assert_(False)
            assert_(str(packet) == message.packet)
            times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id))]
            dprint(sorted(times))
            assert_(len(times) == number_of_messages, (len(times), number_of_messages))
            assert_(global_time in times)
        assert_(number_of_messages == 9, number_of_messages)

        dprint("Older: should be dropped")
        for global_time in [11, 12, 13, 19, 18, 17]:
            # send a message (older: should be dropped)
            node.give_message(node.create_last_9_test_message(str(global_time), global_time))
            times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id))]
            assert_(len(times) == 9, len(times))
            assert_(not global_time in times)

        dprint("Duplicate: should be dropped")
        for global_time in [21, 20, 28, 27, 22, 23, 24, 26, 25]:
            # send a message (duplicate: should be dropped)
            message = node.create_last_9_test_message("wrong content!", global_time)
            node.give_message(message)
            try:
                packet, = self._dispersy_database.execute(u"SELECT packet FROM sync WHERE community = ? AND member = ? AND global_time = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, global_time, message.database_id)).next()
            except StopIteration:
                assert_(False)
            assert_(not str(packet) == message.packet)
            times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id))]
            assert_(sorted(times) == range(20, 29), sorted(times))

        dprint("Should be added and old one removed")
        match_times = sorted(times[:])
        for global_time in [30, 35, 37, 31, 32, 34, 33, 36, 38, 45, 44, 43, 42, 41, 40, 39]:
            # send a message (should be added and old one removed)
            message = node.create_last_9_test_message(str(global_time), global_time)
            node.give_message(message)
            match_times.pop(0)
            match_times.append(global_time)
            match_times.sort()
            try:
                packet, = self._dispersy_database.execute(u"SELECT packet FROM sync WHERE community = ? AND member = ? AND global_time = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, global_time, message.database_id)).next()
            except StopIteration:
                assert_(False)
            assert_(str(packet) == message.packet)
            times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id))]
            dprint(sorted(times))
            assert_(sorted(times) == match_times, sorted(times))

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

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
        message = community.get_meta_message(u"last-1-multimember-text")

        # create node and ensure that SELF knows the node address
        nodeA = DebugNode()
        nodeA.init_socket()
        nodeA.set_community(community)
        nodeA.init_my_member()

        # create node and ensure that SELF knows the node address
        nodeB = DebugNode()
        nodeB.init_socket()
        nodeB.set_community(community)
        nodeB.init_my_member()

        # create node and ensure that SELF knows the node address
        nodeC = DebugNode()
        nodeC.init_socket()
        nodeC.set_community(community)
        nodeC.init_my_member()

        # # dump some junk data, TODO: should not use this btw in actual test...
        # self._dispersy_database.execute(u"INSERT INTO sync (community, meta_message, member, global_time) VALUES (?, ?, 42, 9)", (community.database_id, message.database_id))
        # sync_id = self._dispersy_database.last_insert_rowid
        # self._dispersy_database.execute(u"INSERT INTO reference_member_sync (member, sync) VALUES (42, ?)", (sync_id,))
        # self._dispersy_database.execute(u"INSERT INTO reference_member_sync (member, sync) VALUES (43, ?)", (sync_id,))
        # #
        # self._dispersy_database.execute(u"INSERT INTO sync (community, meta_message, member, global_time) VALUES (?, ?, 4, 9)", (community.database_id, message.database_id))
        # sync_id = self._dispersy_database.last_insert_rowid
        # self._dispersy_database.execute(u"INSERT INTO reference_member_sync (member, sync) VALUES (4, ?)", (sync_id,))
        # self._dispersy_database.execute(u"INSERT INTO reference_member_sync (member, sync) VALUES (43, ?)", (sync_id,))

        # send a message
        global_time = 10
        other_global_time = global_time + 1
        messages = []
        messages.append(nodeA.create_last_1_multimember_text_message([nodeB.my_member], "should be accepted (1)", global_time))
        messages.append(nodeA.create_last_1_multimember_text_message([nodeC.my_member], "should be accepted (1)", other_global_time))
        nodeA.give_messages(messages)
        entries = list(self._dispersy_database.execute(u"SELECT sync.global_time, sync.member, reference_member_sync.member FROM sync JOIN reference_member_sync ON reference_member_sync.sync = sync.id WHERE sync.community = ? AND sync.member = ? AND sync.meta_message = ?", (community.database_id, nodeA.my_member.database_id, message.database_id)))
        assert_(len(entries) == 4, entries)
        assert_((global_time, nodeA.my_member.database_id, nodeA.my_member.database_id) in entries)
        assert_((global_time, nodeA.my_member.database_id, nodeB.my_member.database_id) in entries)
        assert_((other_global_time, nodeA.my_member.database_id, nodeA.my_member.database_id) in entries)
        assert_((other_global_time, nodeA.my_member.database_id, nodeC.my_member.database_id) in entries)

        # send a message
        global_time = 20
        other_global_time = global_time + 1
        messages = []
        messages.append(nodeA.create_last_1_multimember_text_message([nodeB.my_member], "should be accepted (2) @%d" % global_time, global_time))
        messages.append(nodeA.create_last_1_multimember_text_message([nodeC.my_member], "should be accepted (2) @%d" % other_global_time, other_global_time))
        nodeA.give_messages(messages)
        entries = list(self._dispersy_database.execute(u"SELECT sync.global_time, sync.member, reference_member_sync.member FROM sync JOIN reference_member_sync ON reference_member_sync.sync = sync.id WHERE sync.community = ? AND sync.member = ? AND sync.meta_message = ?", (community.database_id, nodeA.my_member.database_id, message.database_id)))
        assert_(len(entries) == 4, entries)
        assert_((global_time, nodeA.my_member.database_id, nodeA.my_member.database_id) in entries)
        assert_((global_time, nodeA.my_member.database_id, nodeB.my_member.database_id) in entries)
        assert_((other_global_time, nodeA.my_member.database_id, nodeA.my_member.database_id) in entries)
        assert_((other_global_time, nodeA.my_member.database_id, nodeC.my_member.database_id) in entries)

        # send a message (older: should be dropped)
        old_global_time = 8
        messages = []
        messages.append(nodeA.create_last_1_multimember_text_message([nodeB.my_member], "should be dropped (1)", old_global_time))
        messages.append(nodeA.create_last_1_multimember_text_message([nodeC.my_member], "should be dropped (1)", old_global_time))
        nodeA.give_messages(messages)
        entries = list(self._dispersy_database.execute(u"SELECT sync.global_time, sync.member, reference_member_sync.member FROM sync JOIN reference_member_sync ON reference_member_sync.sync = sync.id WHERE sync.community = ? AND sync.member = ? AND sync.meta_message = ?", (community.database_id, nodeA.my_member.database_id, message.database_id)))
        assert_(len(entries) == 4, entries)
        assert_((global_time, nodeA.my_member.database_id, nodeA.my_member.database_id) in entries)
        assert_((global_time, nodeA.my_member.database_id, nodeB.my_member.database_id) in entries)
        assert_((other_global_time, nodeA.my_member.database_id, nodeA.my_member.database_id) in entries, entries)
        assert_((other_global_time, nodeA.my_member.database_id, nodeC.my_member.database_id) in entries)

        yield 0.1
        nodeA.drop_packets()

        # send a message (older: should be dropped)
        old_global_time = 8
        messages = []
        messages.append(nodeB.create_last_1_multimember_text_message([nodeA.my_member], "should be dropped (1)", old_global_time))
        messages.append(nodeC.create_last_1_multimember_text_message([nodeA.my_member], "should be dropped (1)", old_global_time))
        nodeA.give_messages(messages)
        entries = list(self._dispersy_database.execute(u"SELECT sync.global_time, sync.member, reference_member_sync.member FROM sync JOIN reference_member_sync ON reference_member_sync.sync = sync.id WHERE sync.community = ? AND sync.member = ? AND sync.meta_message = ?", (community.database_id, nodeA.my_member.database_id, message.database_id)))
        assert_(len(entries) == 4, entries)
        assert_((global_time, nodeA.my_member.database_id, nodeA.my_member.database_id) in entries)
        assert_((global_time, nodeA.my_member.database_id, nodeB.my_member.database_id) in entries)
        assert_((other_global_time, nodeA.my_member.database_id, nodeA.my_member.database_id) in entries)
        assert_((other_global_time, nodeA.my_member.database_id, nodeC.my_member.database_id) in entries)

        # as proof for the drop, the newest message should be sent back
        yield 0.1
        times = []
        _, message = nodeA.receive_message(message_names=[u"last-1-multimember-text"])
        times.append(message.distribution.global_time)
        _, message = nodeA.receive_message(message_names=[u"last-1-multimember-text"])
        times.append(message.distribution.global_time)
        assert_(sorted(times) == [global_time, other_global_time])

        # send a message (older + different member combination: should be dropped)
        old_global_time = 9
        messages = []
        messages.append(nodeB.create_last_1_multimember_text_message([nodeA.my_member], "should be dropped (2)", old_global_time))
        messages.append(nodeC.create_last_1_multimember_text_message([nodeA.my_member], "should be dropped (2)", old_global_time))
        nodeA.give_messages(messages)
        entries = list(self._dispersy_database.execute(u"SELECT sync.global_time, sync.member, reference_member_sync.member FROM sync JOIN reference_member_sync ON reference_member_sync.sync = sync.id WHERE sync.community = ? AND sync.member = ? AND sync.meta_message = ?", (community.database_id, nodeA.my_member.database_id, message.database_id)))
        assert_(len(entries) == 4, entries)
        assert_((global_time, nodeA.my_member.database_id, nodeA.my_member.database_id) in entries)
        assert_((global_time, nodeA.my_member.database_id, nodeB.my_member.database_id) in entries)
        assert_((other_global_time, nodeA.my_member.database_id, nodeA.my_member.database_id) in entries)
        assert_((other_global_time, nodeA.my_member.database_id, nodeC.my_member.database_id) in entries)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def last_1_multimember_unique_member_global_time(self):
        """
        Even with multi member messages, the first member is the creator and may only have one
        message for each global time.
        """
        community = DebugCommunity.create_community(self._my_member)
        message = community.get_meta_message(u"last-1-multimember-text")

        # create node and ensure that SELF knows the node address
        nodeA = DebugNode()
        nodeA.init_socket()
        nodeA.set_community(community)
        nodeA.init_my_member()

        # create node and ensure that SELF knows the node address
        nodeB = DebugNode()
        nodeB.init_socket()
        nodeB.set_community(community)
        nodeB.init_my_member()

        # create node and ensure that SELF knows the node address
        nodeC = DebugNode()
        nodeC.init_socket()
        nodeC.set_community(community)
        nodeC.init_my_member()

        # send two messages
        global_time = 10
        messages = []
        messages.append(nodeA.create_last_1_multimember_text_message([nodeB.my_member], "should be accepted (1.1)", global_time))
        messages.append(nodeA.create_last_1_multimember_text_message([nodeC.my_member], "should be accepted (1.2)", global_time))

        # we NEED the messages to be handled in one batch.  using the socket may change this
        nodeA.give_messages(messages)

        times = [x for x, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, nodeA.my_member.database_id, message.database_id))]
        assert_(times == [global_time], times)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

class DispersyIdenticalPayloadScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = Member(ec_to_public_bin(ec), ec_to_private_bin(ec))

        self.caller(self.incoming__drop_first)
        self.caller(self.incoming__drop_second)

    def incoming__drop_first(self):
        """
        NODE creates two messages with the same community/member/global-time triplets.

        - One of the two should be dropped
        - Both binary signatures should end up in the bloom filter (temporarily) (NO LONGER THE CASE)
        """
        community = DebugCommunity.create_community(self._my_member)

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.555

        # create messages
        global_time = 10
        messages = []
        messages.append(node.create_full_sync_text_message("Identical payload message", global_time))
        messages.append(node.create_full_sync_text_message("Identical payload message", global_time))
        assert_(messages[0].packet != messages[1].packet, "the signature must make the messages unique")

        # sort.  we now know that the first message must be dropped
        messages.sort(key=lambda x: x.packet)

        # give messages in different batches
        node.give_message(messages[0])
        yield 0.555
        node.give_message(messages[1])
        yield 0.555

        # only one message may be in the database
        try:
            packet, =  self._dispersy_database.execute(u"SELECT packet FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                       (community.database_id, node.my_member.database_id, global_time)).next()
        except StopIteration:
            assert_(False, "neither messages is stored")

        packet = str(packet)
        assert_(packet == messages[1].packet)

        # 03/11/11 Boudewijn: we no longer store the ranges in memory, hence only the new packet
        # will be in the bloom filter
        #
        # # both packets must be in the bloom filter
        # assert_(len(community._sync_ranges) == 1)
        # for message in messages:
        #     for bloom_filter in community._sync_ranges[0].bloom_filters:
        #         assert_(message.packet in bloom_filter)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def incoming__drop_second(self):
        """
        NODE creates two messages with the same community/member/global-time triplets.

        - One of the two should be dropped
        - Both binary signatures should end up in the bloom filter (temporarily) (NO LONGER THE CASE)
        """
        community = DebugCommunity.create_community(self._my_member)

        # create node and ensure that SELF knows the node address
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()
        yield 0.555

        # create messages
        global_time = 10
        messages = []
        messages.append(node.create_full_sync_text_message("Identical payload message", global_time))
        messages.append(node.create_full_sync_text_message("Identical payload message", global_time))
        assert_(messages[0].packet != messages[1].packet, "the signature must make the messages unique")

        # sort.  we now know that the first message must be dropped
        messages.sort(key=lambda x: x.packet)

        # give messages in different batches
        node.give_message(messages[1])
        yield 0.555
        node.give_message(messages[0])
        yield 0.555

        # only one message may be in the database
        try:
            packet, =  self._dispersy_database.execute(u"SELECT packet FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                       (community.database_id, node.my_member.database_id, global_time)).next()
        except StopIteration:
            assert_(False, "neither messages is stored")

        packet = str(packet)
        assert_(packet == messages[1].packet)

        # 03/11/11 Boudewijn: we no longer store the ranges in memory, hence only the new packet
        # will be in the bloom filter
        #
        # # both packets must be in the bloom filter
        # assert_(len(community._sync_ranges) == 1)
        # for message in messages:
        #     for bloom_filter in community._sync_ranges[0].bloom_filters:
        #         assert_(message.packet in bloom_filter)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

class DispersySignatureScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = Member(ec_to_public_bin(ec), ec_to_private_bin(ec))

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
        yield 0.555

        dprint("SELF requests NODE to double sign")
        def on_response(response):
            assert_(response is None)
            container["timeout"] += 1
        request = community.create_double_signed_text("Accept=<does not reach this point>", Member(node.my_member.public_key), on_response, (), 3.0)
        yield 0.11

        dprint("NODE receives dispersy-signature-request message")
        _, message = node.receive_message(addresses=[address], message_names=[u"dispersy-signature-request"])
        # do not send a response

        # should timeout
        for counter in range(4):
            dprint("waiting... ", 4 - counter)
            yield 1.0
        yield 0.11

        dprint("SELF must have timed out by now")
        assert_(container["timeout"] == 1, container["timeout"])

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def double_signed_response(self):
        """
        SELF will request a signature from NODE.  SELF will receive the signature and produce a
        double signed message.
        """
        ec = ec_generate_key(u"low")
        my_member = Member(ec_to_public_bin(ec), ec_to_private_bin(ec))
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        container = {"response":0}

        # create node and ensure that SELF knows the node address
        node = Node()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        dprint("SELF requests NODE to double sign")
        def on_response(response):
            assert_(container["response"] == 0, container["response"])
            assert_(request.authentication.is_signed)
            container["response"] += 1
        request = community.create_double_signed_text("Accept=<does not matter>", Member(node.my_member.public_key), on_response, (), 3.0)
        yield 0.11

        dprint("NODE receives dispersy-signature-request message from SELF")
        candidate, message = node.receive_message(addresses=[address], message_names=[u"dispersy-signature-request"])
        submsg = message.payload.message
        second_signature_offset = len(submsg.packet) - community.my_member.signature_length
        first_signature_offset = second_signature_offset - node.my_member.signature_length
        assert_(submsg.packet[second_signature_offset:] == "\x00" * node.my_member.signature_length, "The first signature MUST BE \x00's.  The creator must hold control over the community+member+global_time triplet")
        signature = node.my_member.sign(submsg.packet, length=first_signature_offset)

        dprint("NODE sends dispersy-signature-response message to SELF")
        request_id = hashlib.sha1(request.packet).digest()
        global_time = community.global_time
        node.give_message(node.create_dispersy_signature_response_message(request_id, signature, global_time, candidate))
        yield 1.11
        assert_(container["response"] == 1, container["response"])

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def triple_signed_timeout(self):
        """
        SELF will request a signature from NODE1 and NODE2.  Both NODE1 and NODE2 will ignore this
        request and SELF should get a timeout on the signature request after a few seconds.
        """
        ec = ec_generate_key(u"low")
        my_member = Member(ec_to_public_bin(ec), ec_to_private_bin(ec))
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        container = {"timeout":0}

        # create node and ensure that SELF knows the node address
        node1 = Node()
        node1.init_socket()
        node1.set_community(community)
        node1.init_my_member()

        # create node and ensure that SELF knows the node address
        node2 = Node()
        node2.init_socket()
        node2.set_community(community)
        node2.init_my_member()
        yield 0.555

        # SELF requests NODE1 and NODE2 to double sign
        def on_response(response):
            assert_(response is None)
            container["timeout"] += 1
        request = community.create_triple_signed_text("Hello World!", Member(node1.my_member.public_key), Member(node2.my_member.public_key), on_response, (), 3.0)
        yield 0.11

        # receive dispersy-signature-request message
        _, message = node1.receive_message(addresses=[address], message_names=[u"dispersy-signature-request"])
        _, message = node2.receive_message(addresses=[address], message_names=[u"dispersy-signature-request"])
        # do not send a response

        # should timeout
        for counter in range(4):
            dprint("waiting... ", 4 - counter)
            yield 1.0

        assert_(container["timeout"] == 1, container["timeout"])

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def triple_signed_response(self):
        """
        SELF will request a signature from NODE1 and NODE2.  SELF will receive the two signatures
        and produce a triple signed message.
        """
        ec = ec_generate_key(u"low")
        my_member = Member(ec_to_public_bin(ec), ec_to_private_bin(ec))
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()
        container = {"response":0}

        # create node and ensure that SELF knows the node address
        node1 = Node()
        node1.init_socket()
        node1.set_community(community)
        node1.init_my_member()

        # create node and ensure that SELF knows the node address
        node2 = Node()
        node2.init_socket()
        node2.set_community(community)
        node2.init_my_member()

        # SELF requests NODE1 and NODE2 to add their signature
        def on_response(response):
            assert_(container["response"] == 0 or request.authentication.is_signed)
            container["response"] += 1
        request = community.create_triple_signed_text("Hello World!", Member(node1.my_member.public_key), Member(node2.my_member.public_key), on_response, (), 3.0)
        yield 0.11

        # receive dispersy-signature-request message
        candidate, message = node1.receive_message(addresses=[address], message_names=[u"dispersy-signature-request"])
        submsg = message.payload.message
        third_signature_offset = len(submsg.packet) - node2.my_member.signature_length
        second_signature_offset = third_signature_offset - node1.my_member.signature_length
        first_signature_offset = second_signature_offset - community.my_member.signature_length
        assert_(submsg.packet[second_signature_offset:third_signature_offset] == "\x00" * node1.my_member.signature_length)
        signature1 = node1.my_member.sign(submsg.packet, length=first_signature_offset)

        # send dispersy-signature-response message
        request_id = hashlib.sha1(request.packet).digest()
        global_time = community.global_time
        node1.give_message(node1.create_dispersy_signature_response_message(request_id, signature1, global_time, candidate))

        # receive dispersy-signature-request message
        candidate, message = node2.receive_message(addresses=[address], message_names=[u"dispersy-signature-request"])
        submsg = message.payload.message
        third_signature_offset = len(submsg.packet) - node2.my_member.signature_length
        second_signature_offset = third_signature_offset - node1.my_member.signature_length
        first_signature_offset = second_signature_offset - community.my_member.signature_length
        assert_(submsg.packet[third_signature_offset:] == "\x00" * node2.my_member.signature_length)
        signature2 = node2.my_member.sign(submsg.packet, length=first_signature_offset)

        # send dispersy-signature-response message
        request_id = hashlib.sha1(request.packet).digest()
        global_time = community.global_time
        node2.give_message(node2.create_dispersy_signature_response_message(request_id, signature2, global_time, candidate))
        yield 1.11
        assert_(container["response"] == 2, container["response"])

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

class DispersySubjectiveSetScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = Member(ec_to_public_bin(ec), ec_to_private_bin(ec))

        self.caller(self.storage)
        self.caller(self.full_sync)
        self.caller(self.subjective_set_request)

    def storage(self):
        """
         - a message from a member in the subjective set MUST be stored
         - a message from a member NOT in the subjective set MUST NOT be stored
        """
        community = DebugCommunity.create_community(self._my_member)
        message = community.get_meta_message(u"subjective-set-text")

        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        # node is NOT in self._my_member's subjective set.  the message MUST NOT be stored
        global_time = 10
        node.give_message(node.create_subjective_set_text_message("Must not be stored", global_time))
        times = [global_time for global_time, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert_(times == [], times)

        # node is in self._my_member's subjective set.  the message MUST be stored
        community.create_dispersy_subjective_set(message.destination.cluster, [node.my_member])
        global_time = 20
        node.give_message(node.create_subjective_set_text_message("Must be stored", global_time))
        times = [global_time for global_time, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, message.database_id))]
        assert_(times == [global_time], times)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def full_sync(self):
        """
        Using full sync check that:
         - messages from a member in the subjective set are sent back
         - messages from a member NOT in the set are NOT sent back
        """
        community = DebugCommunity.create_community(self._my_member)
        meta_message = community.get_meta_message(u"subjective-set-text")

        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        # make available the subjective set
        subjective_set = BloomFilter(512 * 8, 0.1)
        subjective_set.add(node.my_member.public_key)
        node.give_message(node.create_dispersy_subjective_set_message(meta_message.destination.cluster, subjective_set, 10))

        # SELF will store and forward for NODE
        community.create_dispersy_subjective_set(meta_message.destination.cluster, [node.my_member])
        global_time = 20
        node.give_message(node.create_subjective_set_text_message("Must be synced", global_time))
        times = [global_time for global_time, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, meta_message.database_id))]
        assert_(times == [global_time])

        # a sync MUST return the message that was just sent
        node.give_message(node.create_dispersy_introduction_request_message(community.my_candidate, node.lan_address, node.wan_address, False, u"unknown", (10, 0, 1, 0, []), 42, 20))
        yield 0.11
        _, message = node.receive_message(message_names=[u"subjective-set-text"])
        assert_(message.distribution.global_time == global_time)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

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
        meta_message = community.get_meta_message(u"subjective-set-text")

        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        # SELF will store and forward for NODE
        community.create_dispersy_subjective_set(meta_message.destination.cluster, [node.my_member])
        global_time = 20
        node.give_message(node.create_subjective_set_text_message("Must be stored", global_time))
        times = [global_time for global_time, in self._dispersy_database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (community.database_id, node.my_member.database_id, meta_message.database_id))]
        assert_(times == [global_time])

        # a dispersy-sync message MUST return a dispersy-subjective-set-request message
        node.give_message(node.create_dispersy_introduction_request_message(community.my_candidate, node.lan_address, node.wan_address, False, u"unknown", (10, 0, 1, 0, []), 42, 20))
        yield 0.11
        _, message = node.receive_message(message_names=[u"dispersy-missing-subjective-set", u"subjective-set-text"])
        assert_(message.name == u"dispersy-missing-subjective-set", ("should NOT sent back anything other than dispersy-missing-subjective-set", message.name))
        assert_(message.payload.cluster == meta_message.destination.cluster)
        try:
            _, message = node.receive_message(message_names=[u"dispersy-missing-subjective-set", u"subjective-set-text"])
        except:
            pass
        else:
            assert_(False, "should be no more messages")

        # make available the subjective set
        subjective_set = BloomFilter(512 * 8, 0.1)
        subjective_set.add(node.my_member.public_key)
        node.give_message(node.create_dispersy_subjective_set_message(meta_message.destination.cluster, subjective_set, 10))
        yield 1.11

        # the dispersy-sync message should now be processed (again) and result in the missing
        # subjective-set-text message
        _, message = node.receive_message(message_names=[u"subjective-set-text"])
        assert_(message.distribution.global_time == global_time)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

# class DispersySimilarityScript(ScriptBase):
#     def run(self):
#         ec = ec_generate_key(u"low")
#         self._my_member = Member.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)

#         # self.caller(self.similarity_check_incoming_packets)
#         self.caller(self.similarity_fullsync)
#         self.caller(self.similarity_lastsync)
#         self.caller(self.similarity_missing_sim)

#     def similarity_check_incoming_packets(self):
#         """
#         Check functionallity of accepting or rejecting
#         incoming packets based on similarity of the member
#         sending the packet
#         """
#         # create community
#         # taste-aware-record  uses SimilarityDestination with the following parameters
#         # 16 Bits Bloom Filter, minimum 6, maximum 10, threshold 12
#         community = DebugCommunity.create_community(self._my_member)
#         address = self._dispersy.socket.get_address()
#         container = {"timeout":0}

#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b11111111), chr(0b00000000)), 0)
#         self._dispersy._database.execute(u"INSERT INTO similarity (community, member, cluster, similarity) VALUES (?, ?, ?, ?)",
#                                          (community.database_id, community._my_member.database_id, 1, buffer(str(bf))))

#         # create first node - node-01
#         node = DebugNode()
#         node.init_socket()
#         node.set_community(community)
#         node.init_my_member()
#         yield 0.555

#         ##
#         ## Similar Nodes
#         ##

#         # create similarity for node-01
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b11111111), chr(0b00000000)), 0)
#         node.send_message(node.create_dispersy_similarity_message(1, community.database_id, bf, 20), address)
#         yield 0.555

#         msg = node.create_taste_aware_message(5, 10, 1)
#         msg_blob = node.encode_message(msg)
#         node.send_message(msg, address)
#         yield 0.555

#         dprint(len(msg_blob), "-", len(msg.packet))
#         dprint(msg_blob.encode("HEX"))
#         dprint(msg.packet.encode("HEX"))
#         assert_(msg_blob == msg.packet)

#         dprint(msg_blob.encode("HEX"))

#         with self._dispersy.database as execute:
#             d, = execute(u"SELECT count(*) FROM sync WHERE packet = ?", (buffer(msg.packet),)).next()
#             assert_(d == 1, d)

#         ##
#         ## Not Similar Nodes
#         ##

#         # create similarity for node-01
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b11111111), chr(0b11111111)), 0)
#         node.send_message(node.create_dispersy_similarity_message(1, community.database_id, bf, 30), address)
#         yield 0.555

#         msg = node.create_taste_aware_message(5, 20, 2)
#         msg_blob = node.encode_message(msg)
#         node.send_message(msg, address)
#         yield 0.555

#         with self._dispersy.database as execute:
#             d,= execute(u"SELECT count(*) FROM sync WHERE packet = ?", (buffer(str(msg_blob)),)).next()
#             assert_(d == 0)

#     def similarity_fullsync(self):
#         # create community
#         # taste-aware-record  uses SimilarityDestination with the following parameters
#         # 16 Bits Bloom Filter, minimum 6, maximum 10, threshold 12
#         ec = ec_generate_key(u"low")
#         my_member = Member.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)
#         community = DebugCommunity.create_community(self._my_member)
#         address = self._dispersy.socket.get_address()

#         # setting similarity for self
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b11110000), chr(0b00000000)), 0)
#         self._dispersy._database.execute(u"INSERT INTO similarity (community, member, cluster, similarity) VALUES (?, ?, ?, ?)",
#                                          (community.database_id, community._my_member.database_id, 1, buffer(str(bf))))

#         # create first node - node-01
#         node = DebugNode()
#         node.init_socket()
#         node.set_community(community)
#         node.init_my_member()
#         yield 0.555

#         # create second node - node-02
#         node2 = DebugNode()
#         node2.init_socket()
#         node2.set_community(community)
#         node2.init_my_member()
#         yield 0.555

#         ##
#         ## Similar Nodes Threshold 12 Similarity 14
#         ##
#         dprint("Testing similar nodes")

#         # create similarity for node-01
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b11110000), chr(0b00000000)), 0)
#         node.send_message(node.create_dispersy_similarity_message(1, community.database_id, bf, 20), address)
#         yield 0.555

#         # create similarity for node-02
#         # node node-02 has 14/16 same bits with node-01
#         # ABOVE threshold
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b10111000), chr(0b00000000)), 0)
#         node2.send_message(node2.create_dispersy_similarity_message(1, community.database_id, bf, 20), address)
#         yield 0.555

#         # node-01 creates and sends a message to 'self'
#         node.send_message(node.create_taste_aware_message(5, 10, 1), address)
#         yield 0.555

#         # node-02 sends an sync message with an empty bloom filter
#         # to 'self'. It should collect the message
#         node2.send_message(node2.create_dispersy_sync_message(1, 100, [], 3), address)
#         yield 0.555

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
#         yield 0.555

#         # node-02 sends an sync message with an empty bloom filter
#         # to 'self'. It should collect the message
#         node2.send_message(node2.create_dispersy_sync_message(1, 100, [], 3), address)
#         yield 0.555

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
#         yield 0.555

#         # node-02 sends an sync message with an empty bloom filter
#         # to 'self'. It should collect the message
#         node2.send_message(node2.create_dispersy_sync_message(1, 100, [], 3), address)
#         yield 0.555

#         # should NOT receive a message
#         try:
#             _, message = node2.receive_message(addresses=[address], message_names=[u"taste-aware-record"])
#             assert_(False)
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
#         yield 0.555

#         # node-02 sends an sync message with an empty bloom filter
#         # to 'self'. It should collect the message
#         node2.send_message(node2.create_dispersy_sync_message(1, 100, [], 3), address)
#         yield 0.555

#         # should NOT receive a message
#         try:
#             _, message = node2.receive_message(addresses=[address], message_names=[u"taste-aware-record"])
#             assert_(False)
#         except:
#             pass

#     def similarity_lastsync(self):
#         # create community
#         # taste-aware-record  uses SimilarityDestination with the following parameters
#         # 16 Bits Bloom Filter, minimum 6, maximum 10, threshold 12
#         ec = ec_generate_key(u"low")
#         my_member = Member.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)
#         community = DebugCommunity.create_community(self._my_member)
#         address = self._dispersy.socket.get_address()
#         container = {"timeout":0}

#         # setting similarity for self
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b11110000), chr(0b00000000)), 0)
#         self._dispersy._database.execute(u"INSERT INTO similarity (community, member, cluster, similarity) VALUES (?, ?, ?, ?)",
#                                          (community.database_id, community._my_member.database_id, 2, buffer(str(bf))))

#         # create first node - node-01
#         node = DebugNode()
#         node.init_socket()
#         node.set_community(community)
#         node.init_my_member()
#         yield 0.555

#         # create second node - node-02
#         node2 = DebugNode()
#         node2.init_socket()
#         node2.set_community(community)
#         node2.init_my_member()
#         yield 0.555

#         ##
#         ## Similar Nodes
#         ##
#         dprint("Testing similar nodes")

#         # create similarity for node-01
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b11110000), chr(0b00000000)), 0)
#         node.send_message(node.create_dispersy_similarity_message(2, community.database_id, bf, 20), address)
#         yield 0.555

#         # create similarity for node-02
#         # node node-02 has 15/16 same bits with node-01
#         # ABOVE threshold
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b10111000), chr(0b00000000)), 0)
#         node2.send_message(node2.create_dispersy_similarity_message(2, community.database_id, bf, 20), address)
#         yield 0.555

#         # node-01 creates and sends a message to 'self'
#         node.send_message(node.create_taste_aware_message_last(5, 30, 1), address)

#         # node-02 sends a sync message with an empty bloom filter
#         # to 'self'. It should collect the message
#         node2.send_message(node2.create_dispersy_sync_message(1, 100, [], 3), address)
#         yield 0.555

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
#         yield 0.555

#         # node-02 sends an sync message with an empty bloom filter
#         # to 'self'. It should collect the message
#         node2.send_message(node2.create_dispersy_sync_message(1, 100, [], 3), address)
#         yield 0.555

#         # receive a message
#         try:
#             _, message = node2.receive_message(addresses=[address], message_names=[u"taste-aware-record-last"])
#             assert_(False)
#         except:
#             pass

#     def similarity_missing_sim(self):
#         # create community
#         # taste-aware-record  uses SimilarityDestination with the following parameters
#         # 16 Bits Bloom Filter, minimum 6, maximum 10, threshold 12
#         ec = ec_generate_key(u"low")
#         my_member = Member.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=True)
#         community = DebugCommunity.create_community(self._my_member)
#         address = self._dispersy.socket.get_address()
#         container = {"timeout":0}

#         # setting similarity for self
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b11110000), chr(0b00000000)), 0)
#         self._dispersy._database.execute(u"INSERT INTO similarity (community, member, cluster, similarity) VALUES (?, ?, ?, ?)",
#                                          (community.database_id, community._my_member.database_id, 1, buffer(str(bf))))

#         # create first node - node-01
#         node = DebugNode()
#         node.init_socket()
#         node.set_community(community)
#         node.init_my_member()
#         yield 0.555

#         # create similarity for node-01
#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b11110000), chr(0b00000000)), 0)
#         node.send_message(node.create_dispersy_similarity_message(1, community.database_id, bf, 20), address)
#         yield 0.555

#         # create second node - node-02
#         node2 = DebugNode()
#         node2.init_socket()
#         node2.set_community(community)
#         node2.init_my_member()
#         yield 0.555

#         # node-01 creates and sends a message to 'self'
#         node.send_message(node.create_taste_aware_message(5, 10, 1), address)
#         yield 0.555

#         # node-02 sends a sync message with an empty bloom filter
#         # to 'self'. It should collect the message
#         node2.send_message(node2.create_dispersy_sync_message(1, 100, [], 3), address)
#         yield 0.555

#         # because 'self' does not have our similarity
#         # we should first receive a 'dispersy-similarity-request' message
#         # and 'synchronize' e.g. send our similarity
#         _, message = node2.receive_message(addresses=[address], message_names=[u"dispersy-similarity-request"])

#         bf = BloomFilter(pack("!LLcc", 1, 16, chr(0b10111000), chr(0b00000000)), 0)
#         node2.send_message(node2.create_dispersy_similarity_message(1, community.database_id, bf, 20), address)
#         yield 0.555

#         # receive the taste message
#         _, message = node2.receive_message(addresses=[address], message_names=[u"taste-aware-record"])
#         assert_( message.payload.number == 5)

class DispersyMissingMessageScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = Member(ec_to_public_bin(ec), ec_to_private_bin(ec))

        self.caller(self.single_request)
        self.caller(self.single_request_out_of_order)
        self.caller(self.triple_request)

    def single_request(self):
        """
        SELF generates a few messages and NODE requests one of them.
        """
        community = DebugCommunity.create_community(self._my_member)

        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        # create messages
        messages = []
        for i in xrange(10):
            messages.append(community.create_full_sync_text("Message #%d" % i))

        # ensure we don't obtain the messages from the socket cache
        node.drop_packets()

        for message in messages:
            # request messages
            node.give_message(node.create_dispersy_missing_message_message(community.my_member, [message.distribution.global_time], 25, community.my_candidate))
            yield 0.11

            # receive response
            _, response = node.receive_message(message_names=[message.name])
            assert_(response.distribution.global_time == message.distribution.global_time)
            assert_(response.payload.text == message.payload.text)
            dprint("ok @", response.distribution.global_time)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def single_request_out_of_order(self):
        """
        SELF generates a few messages and NODE requests one of them.
        """
        community = DebugCommunity.create_community(self._my_member)

        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        # create messages
        messages = []
        for i in xrange(10):
            messages.append(community.create_full_sync_text("Message #%d" % i))

        # ensure we don't obtain the messages from the socket cache
        node.drop_packets()

        shuffle(messages)
        for message in messages:
            # request messages
            node.give_message(node.create_dispersy_missing_message_message(community.my_member, [message.distribution.global_time], 25, community.my_candidate))
            yield 0.11

            # receive response
            _, response = node.receive_message(message_names=[message.name])
            assert_(response.distribution.global_time == message.distribution.global_time)
            assert_(response.payload.text == message.payload.text)
            dprint("ok @", response.distribution.global_time)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def triple_request(self):
        """
        SELF generates a few messages and NODE requests three of them.
        """
        community = DebugCommunity.create_community(self._my_member)

        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        # create messages
        messages = []
        for i in xrange(10):
            messages.append(community.create_full_sync_text("Message #%d" % i))
        meta = messages[0].meta

        # ensure we don't obtain the messages from the socket cache
        node.drop_packets()

        # request messages
        global_times = [messages[index].distribution.global_time for index in [2, 4, 6]]
        node.give_message(node.create_dispersy_missing_message_message(community.my_member, global_times, 25, community.my_candidate))
        yield 0.11

        # receive response
        responses = []
        _, response = node.receive_message(message_names=[meta.name])
        responses.append(response)
        _, response = node.receive_message(message_names=[meta.name])
        responses.append(response)
        _, response = node.receive_message(message_names=[meta.name])
        responses.append(response)

        assert_(sorted(response.distribution.global_time for response in responses) == global_times)
        dprint("ok @", global_times)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

class DispersyUndoScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = Member(ec_to_public_bin(ec), ec_to_private_bin(ec))

        # self.caller(self.self_undo_own)
        # self.caller(self.self_undo_other)
        # self.caller(self.node_undo_own)
        # self.caller(self.node_undo_other)
        # self.caller(self.self_malicious_undo)
        # self.caller(self.node_malicious_undo)
        self.caller(self.node_non_malicious_undo)
        self.caller(self.missing_message)
        self.caller(self.revoke_simple)
        self.caller(self.revoke_causing_undo)

    def self_undo_own(self):
        """
        SELF generates a few messages and then undoes them.

        This is always allowed.  In fact, no check is made since only externally received packets
        will be checked.
        """
        community = DebugCommunity.create_community(self._my_member)

        # create messages
        messages = [community.create_full_sync_text("Should undo #%d" % i, forward=False) for i in xrange(10)]

        # check that they are in the database and are NOT undone
        for message in messages:
            undone = list(self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                          (community.database_id, community.my_member.database_id, message.distribution.global_time)))
            assert_(undone == [(0,)], undone)

        # undo all messages
        undoes = [community.create_dispersy_undo(message, forward=False) for message in messages]

        # check that they are in the database and ARE undone
        for undo, message in zip(undoes, messages):
            undone = list(self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                          (community.database_id, community.my_member.database_id, message.distribution.global_time)))
            assert_(undone == [(undo.packet_id,)], [undone, "-", undo.packet_id])

        # check that all the undo messages are in the database and are NOT undone
        for message in undoes:
            undone = list(self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                          (community.database_id, community.my_member.database_id, message.distribution.global_time)))
            assert_(undone == [(0,)], undone)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill", forward=False)
        self._dispersy.get_community(community.cid).unload_community()

    def self_undo_other(self):
        """
        NODE generates a few messages and then SELF undoes them.

        This is always allowed.  In fact, no check is made since only externally received packets
        will be checked.
        """
        community = DebugCommunity.create_community(self._my_member)

        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        # NODE creates messages
        messages = [node.create_full_sync_text_message("Should undo #%d" % global_time, global_time) for global_time in xrange(10, 20)]
        node.give_messages(messages)

        # check that they are in the database and are NOT undone
        for message in messages:
            undone = list(self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                          (community.database_id, node.my_member.database_id, message.distribution.global_time)))
            assert_(undone == [(0,)], undone)

        # SELF undoes all messages
        undoes = [community.create_dispersy_undo(message, forward=False) for message in messages]

        # check that they are in the database and ARE undone
        for undo, message in zip(undoes, messages):
            undone = list(self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                          (community.database_id, node.my_member.database_id, message.distribution.global_time)))
            assert_(undone == [(undo.packet_id,)], [undone, "-", undo.packet_id])

        # check that all the undo messages are in the database and are NOT undone
        for message in undoes:
            undone = list(self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                          (community.database_id, community.my_member.database_id, message.distribution.global_time)))
            assert_(undone == [(0,)], undone)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill", forward=False)
        self._dispersy.get_community(community.cid).unload_community()

    def node_undo_own(self):
        """
        SELF gives NODE permission to undo, NODE generates a few messages and then undoes them.
        """
        community = DebugCommunity.create_community(self._my_member)

        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        # SELF grants undo permission to NODE
        community.create_dispersy_authorize([(node.my_member, community.get_meta_message(u"full-sync-text"), u"undo")])

        # create messages
        messages = [node.create_full_sync_text_message("Should undo @%d" % global_time, global_time) for global_time in xrange(10, 20)]
        node.give_messages(messages)

        # check that they are in the database and are NOT undone
        for message in messages:
            undone = list(self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                          (community.database_id, node.my_member.database_id, message.distribution.global_time)))
            assert_(undone == [(0,)], undone)

        # undo all messages
        sequence_number = 1
        undoes = [node.create_dispersy_undo_own_message(message, message.distribution.global_time + 100, sequence_number + i) for i, message in enumerate(messages)]
        node.give_messages(undoes)

        # check that they are in the database and ARE undone
        for undo, message in zip(undoes, messages):
            undone = list(self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                          (community.database_id, node.my_member.database_id, message.distribution.global_time)))
            assert_(len(undone) == 1)
            undone_packet, = self._dispersy_database.execute(u"SELECT packet FROM sync WHERE id = ?", (undone[0][0],)).next()
            undone_packet = str(undone_packet)
            assert_(undo.packet == undone_packet, undone)

        # check that all the undo messages are in the database and are NOT undone
        for message in undoes:
            undone = list(self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                          (community.database_id, node.my_member.database_id, message.distribution.global_time)))
            assert_(undone == [(0,)], undone)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def node_undo_other(self):
        """
        SELF gives NODE1 permission to undo, NODE2 generates a few messages and then NODE1 undoes
        them.
        """
        community = DebugCommunity.create_community(self._my_member)

        node1 = DebugNode()
        node1.init_socket()
        node1.set_community(community)
        node1.init_my_member()

        node2 = DebugNode()
        node2.init_socket()
        node2.set_community(community)
        node2.init_my_member()

        # SELF grants undo permission to NODE1
        community.create_dispersy_authorize([(node1.my_member, community.get_meta_message(u"full-sync-text"), u"undo")])

        # NODE2 creates messages
        messages = [node2.create_full_sync_text_message("Should undo @%d" % global_time, global_time) for global_time in xrange(10, 20)]
        node2.give_messages(messages)

        # check that they are in the database and are NOT undone
        for message in messages:
            undone = list(self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                          (community.database_id, node2.my_member.database_id, message.distribution.global_time)))
            assert_(undone == [(0,)], undone)

        # NODE1 undoes all messages
        sequence_number = 1
        undoes = [node1.create_dispersy_undo_other_message(message, message.distribution.global_time + 100, sequence_number + i) for i, message in enumerate(messages)]
        node1.give_messages(undoes)

        # check that they are in the database and ARE undone
        for undo, message in zip(undoes, messages):
            undone = list(self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                          (community.database_id, node2.my_member.database_id, message.distribution.global_time)))
            assert_(len(undone) == 1)
            undone_packet, = self._dispersy_database.execute(u"SELECT packet FROM sync WHERE id = ?", (undone[0][0],)).next()
            undone_packet = str(undone_packet)
            assert_(undo.packet == undone_packet)

        # check that all the undo messages are in the database and are NOT undone
        for message in undoes:
            undone = list(self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                          (community.database_id, node1.my_member.database_id, message.distribution.global_time)))
            assert_(undone == [(0,)], undone)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def self_malicious_undo(self):
        """
        SELF generated a message and then undoes it twice.  The dispersy core should ensure that
        (given that the message was processed, hence update=True) that the second undo is refused
        and the first undo should be returned instead.
        """
        community = DebugCommunity.create_community(self._my_member)

        # create message
        message = community.create_full_sync_text("Should undo")

        # undo once
        undo1 = community.create_dispersy_undo(message)
        assert_(isinstance(undo1, Message.Implementation))

        # undo twice.  instead of a new dispersy-undo, a new instance of the previous UNDO1 must be
        # returned
        undo2 = community.create_dispersy_undo(message)
        assert_(undo1.packet == undo2.packet)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def node_malicious_undo(self):
        """
        SELF gives NODE permission to undo, NODE generates a message and then undoes it twice.  The
        second undo can cause nodes to keep syncing packets that other nodes will keep dropping
        (because you can only drop a message once, but the two messages are binary unique).

        Sending two undoes for the same message is considered malicious behavior, resulting in:
         1. the offending node must be put on the blacklist
         2. the proof of malicious behaviour must be forwarded to other nodes
        """
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()

        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        # SELF grants undo permission to NODE
        community.create_dispersy_authorize([(node.my_member, community.get_meta_message(u"full-sync-text"), u"undo")])

        # create message
        global_time = 10
        message = node.create_full_sync_text_message("Should undo @%d" % global_time, global_time)
        node.give_message(message)

        # undo once
        global_time = 30
        sequence_number = 1
        undo1 = node.create_dispersy_undo_own_message(message, global_time, sequence_number)
        node.give_message(undo1)

        # undo twice
        global_time = 20
        sequence_number = 2
        undo2 = node.create_dispersy_undo_own_message(message, global_time, sequence_number)
        node.give_message(undo2)

        # check that the member is declared malicious
        assert_(Member(node.my_member.public_key).must_blacklist)

        # all messages for the malicious member must be removed
        packets = list(self._dispersy_database.execute(u"SELECT packet FROM sync WHERE community = ? AND member = ?",
                                                       (community.database_id, node.my_member.database_id)))
        assert_(packets == [])

        node2 = DebugNode()
        node2.init_socket()
        node2.set_community(community)
        node2.init_my_member()

        # ensure we don't obtain the messages from the socket cache
        yield 0.1
        node2.drop_packets()

        # propagate a message from the malicious member
        dprint("giving faulty message ", message)
        node2.give_message(message)

        # we should receive proof that NODE is malicious
        malicious_packets = []
        try:
            while True:
                _, response = node2.receive_packet(addresses=[address])
                malicious_packets.append(response)
        finally:
            assert_(sorted(malicious_packets) == sorted([undo1.packet, undo2.packet]), [len(malicious_packets), [packet.encode("HEX") for packet in malicious_packets], undo1.packet.encode("HEX"), undo2.packet.encode("HEX")])

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def node_non_malicious_undo(self):
        """
        SELF gives NODE permission to undo, NODE generates a message, SELF generates an undo, NODE
        generates an undo.  The second undo should NOT cause NODE of SELF to be marked as malicious.
        """
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()

        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        # SELF grants undo permission to NODE
        community.create_dispersy_authorize([(node.my_member, community.get_meta_message(u"full-sync-text"), u"undo")])

        # create message
        global_time = 10
        message = node.create_full_sync_text_message("Should undo @%d" % global_time, global_time)
        node.give_message(message)

        # SELF undoes
        community.create_dispersy_undo(message)

        # NODE undoes
        global_time = 30
        sequence_number = 1
        undo = node.create_dispersy_undo_own_message(message, global_time, sequence_number)
        node.give_message(undo)

        # check that they are in the database and ARE undone
        undone = list(self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                      (community.database_id, message.authentication.member.database_id, message.distribution.global_time)))
        assert_(len(undone) == 1)
        undone_packet, = self._dispersy_database.execute(u"SELECT packet FROM sync WHERE id = ?", (undone[0][0],)).next()
        undone_packet = str(undone_packet)
        assert_(undo.packet == undone_packet)

        # check that the member is not declared malicious
        assert_(not Member(node.my_member.public_key).must_blacklist)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def missing_message(self):
        """
        SELF gives NODE permission to undo, NODE generates a few messages without sending them to
        SELF.  Following, NODE undoes the messages and sends the undo messages to SELF.  SELF must
        now use a dispersy-missing-message to request the messages that are about to be undone.  The
        messages need to be processed and subsequently undone.
        """
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()

        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        # SELF grants undo permission to NODE
        community.create_dispersy_authorize([(node.my_member, community.get_meta_message(u"full-sync-text"), u"undo")])

        # create messages
        messages = [node.create_full_sync_text_message("Should undo @%d" % global_time, global_time) for global_time in xrange(10, 20)]

        # undo all messages
        sequence_number = 1
        undoes = [node.create_dispersy_undo_own_message(message, message.distribution.global_time + 100, i + sequence_number) for i, message in enumerate(messages)]
        node.give_messages(undoes)

        # receive the dispersy-missing-message messages
        global_times = [message.distribution.global_time for message in messages]
        for _ in xrange(len(messages)):
            _, message = node.receive_message(addresses=[address], message_names=[u"dispersy-missing-message"])
            assert_(len(message.payload.global_times) == 1, "we currently only support one global time in an undo message")
            assert_(message.payload.member.public_key == node.my_member.public_key)
            assert_(message.payload.global_times[0] in global_times)
            global_times.remove(message.payload.global_times[0])
        assert_(global_times == [])

        # give all 'delayed' messages
        node.give_messages(messages)

        yield sum(community.get_meta_message(name).batch.max_window for name in [u"full-sync-text", u"dispersy-undo-own", u"dispersy-undo-other"])
        yield 2.0

        # check that they are in the database and ARE undone
        for undo, message in zip(undoes, messages):
            undone = list(self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                          (community.database_id, node.my_member.database_id, message.distribution.global_time)))
            assert_(len(undone) == 1)
            undone_packet, = self._dispersy_database.execute(u"SELECT packet FROM sync WHERE id = ?", (undone[0][0],)).next()
            undone_packet = str(undone_packet)
            assert_(undo.packet == undone_packet)

        # check that all the undo messages are in the database and are NOT undone
        for message in undoes:
            undone = list(self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                          (community.database_id, node.my_member.database_id, message.distribution.global_time)))
            assert_(undone == [(0,)], undone)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def revoke_simple(self):
        """
        SELF gives NODE1 permission to undo, SELF revokes this permission.
        """
        community = DebugCommunity.create_community(self._my_member)

        node1 = DebugNode()
        node1.init_socket()
        node1.set_community(community)
        node1.init_my_member()

        # SELF grants undo permission to NODE1
        community.create_dispersy_authorize([(node1.my_member, community.get_meta_message(u"full-sync-text"), u"undo")])

        # SELF revoke undo permission from NODE1
        community.create_dispersy_revoke([(node1.my_member, community.get_meta_message(u"full-sync-text"), u"undo")])

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def revoke_causing_undo(self):
        """
        SELF gives NODE1 permission to undo, SELF created a message, NODE1 undoes the message, SELF
        revokes the undo permission AFTER the message was undone -> the message is not re-done.
        """
        community = DebugCommunity.create_community(self._my_member)

        node1 = DebugNode()
        node1.init_socket()
        node1.set_community(community)
        node1.init_my_member()

        # SELF grants undo permission to NODE1
        community.create_dispersy_authorize([(node1.my_member, community.get_meta_message(u"full-sync-text"), u"undo")])

        # SELF creates a message
        message = community.create_full_sync_text("will be undone")
        assert_message_stored(community, community.my_member, message.distribution.global_time)

        # NODE1 undoes the message
        sequence_number = 1
        node1.give_message(node1.create_dispersy_undo_other_message(message, message.distribution.global_time + 1, sequence_number))
        assert_message_stored(community, community.my_member, message.distribution.global_time, undone="undone")

        # SELF revoke undo permission from NODE1
        community.create_dispersy_revoke([(node1.my_member, community.get_meta_message(u"full-sync-text"), u"undo")])
        assert_message_stored(community, community.my_member, message.distribution.global_time, undone="undone")

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

class DispersyCryptoScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = Member(ec_to_public_bin(ec), ec_to_private_bin(ec))

        self.caller(self.invalid_public_key)

    def invalid_public_key(self):
        """
        SELF receives a dispersy-identity message containing an invalid public-key.
        """
        community = DebugCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()

        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member(candidate=False, identity=False)

        # create dispersy-identity message
        global_time = 10
        message = node.create_dispersy_identity_message(global_time)

        # replace the valid public-key with an invalid one
        public_key = node.my_member.public_key
        assert_(public_key in message.packet)
        invalid_packet = message.packet.replace(public_key, "I" * len(public_key))
        assert_(message.packet != invalid_packet)

        # give invalid message to SELF
        node.give_packet(invalid_packet)

        # ensure that the message was not stored in the database
        ids = list(self._dispersy_database.execute(u"SELECT id FROM sync WHERE community = ? AND packet = ?",
                                                   (community.database_id, buffer(invalid_packet))))
        assert_(ids == [], ids)

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

class DispersyDynamicSettings(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = Member(ec_to_public_bin(ec), ec_to_private_bin(ec))

        self.caller(self.default_resolution)
        self.caller(self.change_resolution)
        self.caller(self.change_resolution_undo)
        self.caller(self.wrong_resolution)

    def default_resolution(self):
        """
        Ensure that the default resolution policy is used first.
        """
        community = DebugCommunity.create_community(self._my_member)
        meta = community.get_meta_message(u"dynamic-resolution-text")

        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        # check default policy
        policy, proof = community._timeline.get_resolution_policy(meta, community.global_time)
        assert_(isinstance(policy, PublicResolution))
        assert_(proof == [])

        # NODE creates a message (should allow, because the default policy is PublicResolution)
        global_time = 10
        message = node.give_message(node.create_dynamic_resolution_text_message("Dprint=True", global_time, policy.implement()))

        try:
            undone, = self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                     (community.database_id, node.my_member.database_id, message.distribution.global_time)).next()
        except StopIteration:
            assert_(False, "must accept the message")
        assert_(not undone, "must accept the message")

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def change_resolution(self):
        """
        Change the resolution policy from default to linear and to public again.
        """
        community = DebugCommunity.create_community(self._my_member)
        meta = community.get_meta_message(u"dynamic-resolution-text")
        public = meta.resolution.policies[0]
        linear = meta.resolution.policies[1]

        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        # check default policy
        public_policy, proof = community._timeline.get_resolution_policy(meta, community.global_time + 1)
        assert_(isinstance(public_policy, PublicResolution))
        assert_(proof == [])

        # change and check policy
        message = community.create_dispersy_dynamic_settings([(meta, linear)])
        linear_policy, proof = community._timeline.get_resolution_policy(meta, community.global_time + 1)
        assert_(isinstance(linear_policy, LinearResolution))
        assert_(proof == [message])

        # NODE creates a message (should allow)
        global_time = message.distribution.global_time
        message = node.give_message(node.create_dynamic_resolution_text_message("Dprint=True", global_time, public_policy.implement()))
        try:
            undone, = self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                     (community.database_id, node.my_member.database_id, message.distribution.global_time)).next()
        except StopIteration:
            assert_(False, "must accept the message")
        assert_(not undone, "must accept the message")

        # NODE creates a message (should drop)
        global_time += 1
        message = node.give_message(node.create_dynamic_resolution_text_message("Dprint=True", global_time, linear_policy.implement()))
        try:
            undone, = self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                     (community.database_id, node.my_member.database_id, message.distribution.global_time)).next()
        except StopIteration:
            pass
        else:
            assert_(False, "must not accept the message")

        # change and check policy
        message = community.create_dispersy_dynamic_settings([(meta, public)])
        public_policy, proof = community._timeline.get_resolution_policy(meta, community.global_time + 1)
        assert_(isinstance(public_policy, PublicResolution))
        assert_(proof == [message])

        # NODE creates a message (should drop)
        global_time = message.distribution.global_time
        message = node.give_message(node.create_dynamic_resolution_text_message("Dprint=True", global_time, public_policy.implement()))
        try:
            undone, = self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                     (community.database_id, node.my_member.database_id, message.distribution.global_time)).next()
        except StopIteration:
            pass
        else:
            assert_(False, "must not accept the message")

        # NODE creates a message (should allow)
        global_time += 1
        message = node.give_message(node.create_dynamic_resolution_text_message("Dprint=True", global_time, public_policy.implement()))
        try:
            undone, = self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                     (community.database_id, node.my_member.database_id, message.distribution.global_time)).next()
        except StopIteration:
            assert_(False, "must accept the message")
        assert_(not undone, "must accept the message")

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def change_resolution_undo(self):
        """
        Change the resolution policy from default to linear, the messages already accepted should be
        undone
        """
        community = DebugCommunity.create_community(self._my_member)
        meta = community.get_meta_message(u"dynamic-resolution-text")
        public = meta.resolution.policies[0]
        linear = meta.resolution.policies[1]

        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        # create policy change, but do not yet process
        global_time = community._global_time
        community._global_time = 10
        policy_linear = community.create_dispersy_dynamic_settings([(meta, linear)], store=False, update=False, forward=False)
        assert_(policy_linear.distribution.global_time == 11) # hence the policy starts at 12
        community._global_time = 20
        policy_public = community.create_dispersy_dynamic_settings([(meta, public)], store=False, update=False, forward=False)
        assert_(policy_public.distribution.global_time == 21) # hence the policy starts at 22
        community._global_time = global_time

        for global_time in range(1, 32):
            policy, proof = community._timeline.get_resolution_policy(meta, global_time)
            assert_(isinstance(policy, PublicResolution))
            assert_(proof == [])

        # NODE creates a message (should allow)
        global_time = 25
        text_message = node.give_message(node.create_dynamic_resolution_text_message("Dprint=True", global_time, public.implement()))
        try:
            undone, = self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                     (community.database_id, node.my_member.database_id, text_message.distribution.global_time)).next()
        except StopIteration:
            assert_(False, "must accept the message")
        assert_(not undone, "must accept the message")

        dprint("-- apply linear")

        # process the policy change
        node.give_message(policy_linear)

        for global_time in range(1, 12):
            policy, proof = community._timeline.get_resolution_policy(meta, global_time)
            assert_(isinstance(policy, PublicResolution))
            assert_(proof == [])
        for global_time in range(12, 32):
            policy, proof = community._timeline.get_resolution_policy(meta, global_time)
            assert_(isinstance(policy, LinearResolution))
            assert_([message.packet for message in proof] == [policy_linear.packet])

        try:
            undone, = self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                     (community.database_id, node.my_member.database_id, text_message.distribution.global_time)).next()
        except StopIteration:
            assert_(False, "the message must be in the database with undone = 1")
        assert_(undone, "must have undone the message")

        dprint("-- apply public")

        # process the policy change
        node.give_message(policy_public)

        for global_time in range(1, 12):
            policy, proof = community._timeline.get_resolution_policy(meta, global_time)
            assert_(isinstance(policy, PublicResolution))
            assert_(proof == [])
        for global_time in range(12, 22):
            policy, proof = community._timeline.get_resolution_policy(meta, global_time)
            assert_(isinstance(policy, LinearResolution))
            assert_([message.packet for message in proof] == [policy_linear.packet])
        for global_time in range(22, 32):
            policy, proof = community._timeline.get_resolution_policy(meta, global_time)
            assert_(isinstance(policy, PublicResolution))
            assert_([message.packet for message in proof] == [policy_public.packet])

        try:
            undone, = self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                     (community.database_id, node.my_member.database_id, text_message.distribution.global_time)).next()
        except StopIteration:
            assert_(False, "must accept the message")
        assert_(not undone, "must accept the message")

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

    def wrong_resolution(self):
        """
        For consistency we should not accept messages that have the wrong policy.

        Hence, when a message is created by a member with linear permission, but the community is
        set to public resolution, the message should NOT be accepted.
        """
        community = DebugCommunity.create_community(self._my_member)
        meta = community.get_meta_message(u"dynamic-resolution-text")
        public = meta.resolution.policies[0]
        linear = meta.resolution.policies[1]

        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member()

        # set linear policy
        policy_linear = community.create_dispersy_dynamic_settings([(meta, linear)])

        # give permission to node
        community.create_dispersy_authorize([(Member(node.my_member.public_key), meta, u"permit")])

        # NODE creates a message (should allow, linear resolution and we have permission)
        global_time = community.global_time + 1
        message = node.give_message(node.create_dynamic_resolution_text_message("Dprint=True", global_time, linear.implement()))

        try:
            undone, = self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                     (community.database_id, node.my_member.database_id, message.distribution.global_time)).next()
        except StopIteration:
            assert_(False, "must accept the message")
        assert_(not undone, "must accept the message")

        # NODE creates a message (should drop because we use public resolution while linear is
        # currently configured)
        global_time = community.global_time + 1
        message = node.give_message(node.create_dynamic_resolution_text_message("Dprint=True", global_time, public.implement()))

        try:
            undone, = self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                     (community.database_id, node.my_member.database_id, message.distribution.global_time)).next()
        except StopIteration:
            pass
        else:
            assert_(False, "must NOT accept the message")

        # set public policy
        policy_public = community.create_dispersy_dynamic_settings([(meta, public)])

        # NODE creates a message (should allow, we use public resolution and that is the active policy)
        global_time = community.global_time + 1
        message = node.give_message(node.create_dynamic_resolution_text_message("Dprint=True", global_time, public.implement()))

        try:
            undone, = self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                     (community.database_id, node.my_member.database_id, message.distribution.global_time)).next()
        except StopIteration:
            assert_(False, "must accept the message")
        assert_(not undone, "must accept the message")

        # NODE creates a message (should drop because we use linear resolution while public is
        # currently configured)
        global_time = community.global_time + 1
        message = node.give_message(node.create_dynamic_resolution_text_message("Dprint=True", global_time, linear.implement()))

        try:
            undone, = self._dispersy_database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                     (community.database_id, node.my_member.database_id, message.distribution.global_time)).next()
        except StopIteration:
            pass
        else:
            assert_(False, "must NOT accept the message")

        # cleanup
        community.create_dispersy_destroy_community(u"hard-kill")
        self._dispersy.get_community(community.cid).unload_community()

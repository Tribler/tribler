from twisted.internet import reactor
from twisted.internet.defer import Deferred, inlineCallbacks

# Isolate SubProcess
import Tribler.community.tunnel.processes
Tribler.community.tunnel.processes.CHILDFDS_ENABLED = False

# Isolate ChildProcess
from Tribler.community.tunnel.processes.childprocess import ChildProcess


def cp_init_overwrite(x):
    super(ChildProcess, x).__init__()
    x.input_callbacks = {1: x.on_generic,
                         4: x.on_ctrl,
                         6: x.on_data,
                         8: x.on_exit}
ChildProcess.__init__ = cp_init_overwrite

from Tribler.community.tunnel.processes.rpcprocess import RPCProcess
from Tribler.community.tunnel.processes.tunnel_childprocess import TunnelProcess
from Tribler.community.tunnel.processes.tunnel_subprocess import TunnelSubprocess
from Tribler.community.tunnel.processes.rpc_defs import (RPC_CREATE,
                                                         RPC_NOTIFY,
                                                         RPC_SYNC,
                                                         RPC_MONITOR,
                                                         RPC_CIRCUIT,
                                                         RPC_CIRDEAD)
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.Test.test_as_server import AbstractServer


class MockInternet(RPCProcess):

    def __init__(self):
        RPCProcess.__init__(self)
        self.linked_internet = None

    def set_internet_link(self, other):
        self.linked_internet = other

    def write_ctrl(self, msg):
        reactor.callInThread(self.linked_internet.on_ctrl, msg)

    def write_data(self, msg):
        reactor.callInThread(self.linked_internet.on_data, msg)

    def write_exit(self, msg):
        reactor.callInThread(self.linked_internet.on_exit, msg)


class MockCommunity(object):

    def __init__(self):
        self.monitor_input = []
        self.create_input = ()
        self.data_input = ()
        self.updated = Deferred()

        self.circuits = {42: None}

    def monitor_infohashes(self, infohashes):
        self.monitor_input.extend(infohashes)
        self.updated.callback(None)

    def create_circuit(self, goal_hops, type, callback, required_endpoint, info_hash):
        self.create_input = (goal_hops, type, callback, required_endpoint, info_hash)
        self.updated.callback(42)
        return 42

    def send_data(self, candidates, circuit_id, dest_address, source_address, data):
        self.data_input = (candidates, circuit_id, dest_address, source_address, data)
        self.updated.callback(None)


class MockTunnelProcess(TunnelProcess, MockInternet):

    def __init__(self):
        MockInternet.__init__(self)

        self.community = None

        self.register_rpc(RPC_CREATE)
        self.register_rpc(RPC_CIRCUIT)
        self.register_rpc(RPC_MONITOR)
        self.register_rpc(RPC_CIRDEAD, self.on_rpc_circuit_dead)
        self.register_rpc(RPC_NOTIFY, self.on_rpc_notify)
        self.register_rpc(RPC_SYNC, self.on_rpc_sync, False)

        self.exit_deferred = None


class MockTunnelSubprocess(TunnelSubprocess, MockInternet):

    def __init__(self):
        MockInternet.__init__(self)
        self.session_started = True
        self.session = None
        self.community = MockCommunity()

        self.register_rpc(RPC_CIRDEAD)
        self.register_rpc(RPC_NOTIFY)
        self.register_rpc(RPC_SYNC, auto_serialize=False)
        self.register_rpc(RPC_CIRCUIT, self.on_rpc_circuit)
        self.register_rpc(RPC_CREATE, self.on_rpc_create)
        self.register_rpc(RPC_MONITOR, self.on_rpc_monitor_infohashes)


class TestTunnelProcesses(AbstractServer):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestTunnelProcesses, self).setUp(annotate=annotate)
        self.process = MockTunnelProcess()
        self.subprocess = MockTunnelSubprocess()

        self.process.set_internet_link(self.subprocess)
        self.subprocess.set_internet_link(self.process)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_send_data(self):
        """
        Check if the TunnelSubprocess receives the send_data() call as it was
        called on the main TunnelProcess.
        """
        cd_list = [Candidate(("1.2.3.4", 1234), False),
                   Candidate(("5.6.7.8", 5678), False),
                   Candidate(("1.1.2.3", 1123), False)]
        socket_list = [(c.sock_addr[0], c.sock_addr[1]) for c in cd_list]
        circuit_id = 42
        dest_address = ("3.5.7.9", 3579)
        source_address = ("2.4.6.8", 2468)
        data = "".join([chr(i) for i in range(256)])

        self.process.send_data(socket_list, circuit_id, dest_address, source_address, data)

        yield self.subprocess.community.updated

        self.assertEqual(self.subprocess.community.data_input,
                         (cd_list, circuit_id, dest_address, source_address, data))

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_monitor_infohashes(self):
        """
        Check if the TunnelSubprocess receives the monitor_infohashes() call as it was
        called on the main TunnelProcess.

        Includes all possible characters in 13 20-char infohashes
        """
        infohashes = [("".join([chr(i) for i in range(0, 20)]), 1, 2),
                      ("".join([chr(i) for i in range(20, 40)]), 2, 3),
                      ("".join([chr(i) for i in range(40, 60)]), 3, 4),
                      ("".join([chr(i) for i in range(60, 80)]), 4, 5),
                      ("".join([chr(i) for i in range(80, 100)]), 5, 6),
                      ("".join([chr(i) for i in range(100, 120)]), 6, 7),
                      ("".join([chr(i) for i in range(120, 140)]), 7, 8),
                      ("".join([chr(i) for i in range(140, 160)]), 8, 9),
                      ("".join([chr(i) for i in range(160, 180)]), 9, 10),
                      ("".join([chr(i) for i in range(180, 200)]), 10, 11),
                      ("".join([chr(i) for i in range(200, 220)]), 11, 12),
                      ("".join([chr(i) for i in range(220, 240)]), 12, 13),
                      ("".join([chr(i) for i in range(236, 256)]), 13, 14)]

        self.process.monitor_infohashes(infohashes)

        yield self.subprocess.community.updated

        self.assertEqual(self.subprocess.community.monitor_input,
                         infohashes)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_create_circuit(self):
        """
        Check if the TunnelSubprocess receives the create_circuit() call as it was
        called on the main TunnelProcess.
        """
        goal_hops = 1337
        type = "DATA"
        callback = None # Cross-process callback should ALWAYS be None
        required_endpoint = ("1.1.1.1", 1, "My First LibNacl Key")
        info_hash = "".join([chr(i) for i in range(256)])

        rval = yield self.process.create_circuit(goal_hops, type, required_endpoint, info_hash)

        self.assertEqual(rval, 42)
        self.assertEqual(self.subprocess.community.create_input,
                         (goal_hops, type, callback, required_endpoint, info_hash))

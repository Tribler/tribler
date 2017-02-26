import logging
from binascii import hexlify

from twisted.internet import reactor, task
from twisted.internet.defer import AlreadyCalledError, Deferred, inlineCallbacks, returnValue

from Tribler.community.tunnel.processes.childprocess import ChildProcess
from Tribler.community.tunnel.processes.line_util import fix_split
from Tribler.community.tunnel.processes.rpc_defs import (RPC_RESPONSE_OK,
                                                         RPC_CREATE,
                                                         RPC_NOTIFY,
                                                         RPC_SYNC,
                                                         RPC_MONITOR,
                                                         RPC_CIRCUIT,
                                                         RPC_CIRDEAD)
from Tribler.community.tunnel.processes.rpcprocess import RPCProcess
from Tribler.community.tunnel.remotes.remote_object import RemoteObject


class TunnelProcess(RPCProcess, ChildProcess):

    """
    The TunnelProcess is the main process's view of a child
    process running a TunnelCommunity.
    """

    def __init__(self, community=None):
        """
        Initialize a new TunnelProcess. This is the main
        process's view of a child process.

        :param community: the Community to report back to
        :type community: Tribler.dispersy.community.Community
        :returns: None
        """
        super(TunnelProcess, self).__init__()

        self.community = community

        self.register_rpc(RPC_CREATE)
        self.register_rpc(RPC_CIRCUIT)
        self.register_rpc(RPC_MONITOR)
        self.register_rpc(RPC_CIRDEAD, self.on_rpc_circuit_dead)
        self.register_rpc(RPC_NOTIFY, self.on_rpc_notify)
        self.register_rpc(RPC_SYNC, self.on_rpc_sync, False)

        self.exit_deferred = None

    def set_community(self, community):
        """
        Switch the community to report to

        :param community: the new community to use
        :type community: Tribler.dispersy.community.Community
        """
        self.community = community

    def end(self):
        """
        End the child process

        :return: the deferred signalling the exit
        :rtype: twisted.internet.defer.Deferred
        """
        self.exit_deferred = Deferred()
        self.write_exit(RPC_RESPONSE_OK)
        def checkExited():
            if not self.exit_deferred.called:
                logging.error("Force killing " + str(self.pid))
                self.terminate()
                self._signal_exit_deferred()
        reactor.callLater(4.0, checkExited)
        return self.exit_deferred

    @inlineCallbacks
    def on_exit(self, msg):
        """
        Callback for when the process signals correct termination

        :param msg: the exit flag
        :type msg: str
        :returns: None
        """
        if not self.exit_deferred.called:
            # The child has assured us it has exited correctly
            # If it lied to us, the checkExited() callback will
            # force terminate it anyway.
            while not self.broken:
                yield task.deferLater(reactor, .05, lambda: None)
            self._signal_exit_deferred()

    def _signal_exit_deferred(self):
        """
        Make sure the exit_deferred has been called

        :returns: None
        """
        try:
            self.exit_deferred.callback(True)
        except AlreadyCalledError:
            # This is fine, our job is done
            pass

    @inlineCallbacks
    def create(self, keypair, is_exit_node):
        """
        Create the child process's community

        :param keypair: the multichain key-pair to use
        :type keypair: str
        :param is_exit_node: is this to be an exit node
        :type is_exit_node: bool
        :param test_mode: is this to run in test mode
        :type test_mode: bool
        :returns: None
        """
        yield self.send_rpc(RPC_CREATE, (keypair, is_exit_node))

    @inlineCallbacks
    def monitor_infohashes(self, infohashes):
        """
        Call monitor_infohashes on the child process's community

        :param infohashes: the infohash tuples to monitor
        :type infohashes: [(str, int, int)]
        :returns: None
        """
        json_fixed = [(hexlify(infohash[0]), infohash[1], infohash[2])
                      for infohash in infohashes]
        yield self.send_rpc(RPC_MONITOR, (json_fixed, ))

    @inlineCallbacks
    def create_circuit(self, goal_hops, ctype, required_endpoint,
                       info_hash):
        """
        Call create_circuit on the child process's community

        :param goal_hops: the hop count in the circuit
        :type goal_hops: int
        :param ctype: type of circuit to create
        :type ctype: str
        :param required_endpoint: the endpoint to use
        :type required_endpoint: (str, int ,str)
        :param info_hash: the infohash to assign to this circuit
        :type info_hash: str
        :return: False or the circuit id
        :rtype: bool or long
        """
        enc_required_endpoint = None
        if required_endpoint:
            enc_required_endpoint = (required_endpoint[0],
                                     required_endpoint[1],
                                     required_endpoint[2].encode("HEX"))
        val = yield self.send_rpc(RPC_CIRCUIT, (goal_hops,
                                                ctype,
                                                enc_required_endpoint,
                                                hexlify(info_hash) if info_hash else None))
        returnValue(val)

    def send_data(self, cd_list, circuit_id, dest_address,
                  source_address, data):
        """
        Send data over a circuit_id

        This uses custom serialization for speed.

        :param cd_list: the list of the candidates to send to
        :type cd_list: [(str, int)]
        :param circuit_id: the circuit_id to use
        :type circuit_id: long
        :param dest_address: the destination address
        :type dest_address: (str, int)
        :param source_address: our address
        :type source_address: (str, int)
        :param data: the raw data to send
        :type data: str
        :returns: None
        """
        serialized_cd_list = ','.join([cd[0] + ':' + str(cd[1])
                                       for cd in cd_list])
        self.write_data(';'.join([serialized_cd_list,
                                  str(circuit_id),
                                  dest_address[0] + ':'
                                  + str(dest_address[1]),
                                  source_address[0] + ':'
                                  + str(source_address[1]),
                                  data]))

    def on_data(self, msg):
        """
        Callback for incoming data

        :param msg: the serialized data
        :type msgs: str
        :returns: None
        """
        s_circuit_id, s_origin_host,\
            s_origin_port, s_anon_seed,\
            data = fix_split(5, ';', msg.split(';'))
        i_circuit_id = int(s_circuit_id)
        if i_circuit_id not in self.community.circuits:
            logging.error("Attempted to send data over unknown circuit id " + s_circuit_id)
            return
        circuit = self.community.circuits[i_circuit_id]
        origin = (s_origin_host, int(s_origin_port))
        anon_seed = s_anon_seed == "1"
        self.community.socks_server.on_incoming_from_tunnel(self.community, circuit, origin, data, anon_seed)

    def on_rpc_circuit_dead(self, circuit_id):
        """
        Callback for when the child process signals a dead circuit

        :param circuit_id: the dead circuit's id
        :type circuit_id: long
        :return: RPC response code
        :rtype: str
        """
        self.community.remove_circuit(circuit_id)
        return RPC_RESPONSE_OK

    def on_rpc_notify(self, subject, changeType, obj_id, *args):
        """
        Callback for the child process's notifications

        :param subject: the subject
        :type subject: str
        :param changeType: the change type
        :type changeType: str
        :param obj_id: the object
        :type obj_id: object
        :param args: optional arguments
        :type args: [object]
        :return: RPC response code
        :rtype: str
        """
        if self.community and self.community.notifier:
            self.community.notifier.notify(subject, changeType,
                                           obj_id, *args)
        return RPC_RESPONSE_OK

    def on_rpc_sync(self, serialized):
        """
        RPC callback SyncDict synchronization frames

        :param serialized: the sync frame
        :type serialized: str
        :return: RPC response code
        :rtype: str
        """
        if self.community:
            cls_name = RemoteObject.__extract_class_name__(serialized)
            if self.community.circuits.is_same_type(cls_name):
                self.community.circuits.on_synchronize(serialized)
            elif self.community.hops.is_same_type(cls_name):
                self.community.hops.on_synchronize(serialized)
            else:
                logging.error(
                    "Child process tried to synchronize unknown class "
                    + cls_name)
        return RPC_RESPONSE_OK

import logging
import os
import sys
from binascii import unhexlify

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import blockingCallFromThread

from Tribler.community.tunnel.processes.line_util import fix_split
from Tribler.community.tunnel.processes.rpc_defs import (RPC_RESPONSE_OK,
                                                         RPC_RESPONSE_ERR,
                                                         RPC_CREATE,
                                                         RPC_NOTIFY,
                                                         RPC_SYNC,
                                                         RPC_MONITOR,
                                                         RPC_CIRCUIT,
                                                         RPC_CIRDEAD)
from Tribler.community.tunnel.processes.rpcprocess import RPCProcess
from Tribler.community.tunnel.processes.subprocess import Subprocess
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.simpledefs import NTFY_STARTED, NTFY_TRIBLER
from Tribler.dispersy.candidate import Candidate


class TunnelSubprocess(RPCProcess, Subprocess):

    """
    The child process's view of the parent process

    In other words, this controls all of the constructs
    required by the parent process. Most importantly it
    manages a TunnelCommunity.

    TODO/Future work in this file:
     - Forward notifications
     - Forward bartercast statistics
    """

    def __init__(self):
        """
        Initialize a new TunnelSubprocess

        :returns: None
        """
        super(TunnelSubprocess, self).__init__()

        self.session_started = False
        self.session = None
        self.community = None

        self.register_rpc(RPC_CIRDEAD)
        self.register_rpc(RPC_NOTIFY)
        self.register_rpc(RPC_SYNC, auto_serialize=False)
        self.register_rpc(RPC_CIRCUIT, self.on_rpc_circuit)
        self.register_rpc(RPC_CREATE, self.on_rpc_create)
        self.register_rpc(RPC_MONITOR, self.on_rpc_monitor_infohashes)

    @inlineCallbacks
    def sync(self, data):
        """
        Callback for when any SyncDict wants to sync data

        :param data: the data to synchronize
        :type data: str
        :returns: None
        """
        yield self.send_rpc(RPC_SYNC, data)

    @inlineCallbacks
    def circuit_dead(self, circuit_id):
        """
        Callback for when a circuit is dead

        :param circuit_id: the dead circuit id
        :type circuit_id: long
        :returns: None
        """
        yield self.send_rpc(RPC_CIRDEAD, (circuit_id,))

    def on_session_started(self, subject, changetype, objectID, *args):
        """
        Callback for when the local Session has started

        :returns: None
        """
        self.community = self.session.lm.tunnel_community
        self.community.set_process(self)
        self.session_started = True

    @inlineCallbacks
    def start_session(self, session):
        """
        Attempt to start the local Session

        This can go wrong, in this case we attempt to soft-exit.
        """
        session.add_observer(self.on_session_started,
                             NTFY_TRIBLER,
                             [NTFY_STARTED])
        try:
            yield session.start()
        except:
            logging.error("Session reported error when starting up: "
                          + str(sys.exc_info()[0]))
            try:
                self.write_exit(RPC_RESPONSE_ERR)
                logging.info(
                    "Soft-exit after session startup crash, succeeded")
            except:
                logging.error("Attempt to soft-exit failed: "
                              + str(sys.exc_info()[0]))

    def on_rpc_create(self, keypair_filename, is_exit_node):
        """
        Initialize the local TunnelCommunity

        :param keypair_filename: the path of the multichain ec file
        :type keypair_filename: str
        :param is_exit_node: is exit node enabled
        :type is_exit_node: bool
        :return: RPC response code
        :rtype: str
        """
        # Set up a MiniSession
        config = SessionStartupConfig()
        working_dir = os.path.join(config.get_state_dir(),
                                   "tunnel_subprocess" + str(os.getpid()))
        if not os.path.exists(working_dir):
            os.makedirs(working_dir)

        # Configure MiniSession
        config.set_state_dir(working_dir)
        config.set_torrent_checking(False)
        config.set_http_api_enabled(False)
        config.set_torrent_store(False)
        config.set_enable_torrent_search(False)
        config.set_enable_channel_search(False)
        config.set_torrent_collecting(False)
        config.set_dht_torrent_collecting(False)
        config.set_enable_metadata(False)
        config.set_upgrader_enabled(False)
        config.set_preview_channel_community_enabled(False)
        config.set_channel_community_enabled(False)
        config.set_tunnel_community_pooled(False)
        config.set_libtorrent(False)
        config.set_enable_multichain(False)
        config.sessconfig.set(u'general', u'minport', -1)

        config.set_tunnel_community_exitnode_enabled(is_exit_node)
        if keypair_filename:
            config.set_multichain_permid_keypair_filename(
                keypair_filename)

        # Create the actual session
        self.session = Session(config)

        # Join the community
        reactor.callInThread(self.start_session, self.session)

        return RPC_RESPONSE_OK

    def on_rpc_monitor_infohashes(self, infohashes):
        """
        Call monitor_infohashes

        :param infohashes: the infohash tuples to monitor
        :type infohashes: [(str, int, int)]
        :return: RPC response code
        :rtype: str
        """
        if not self.session_started:
            logging.error("Attempted monitor_infohashes without Session")
            return RPC_RESPONSE_ERR
        self.community.monitor_infohashes([(unhexlify(infohash[0]),
                                            infohash[1],
                                            infohash[2])
                                           for infohash in infohashes])
        return RPC_RESPONSE_OK

    def on_rpc_circuit(self, goal_hops, ctype, required_endpoint,
                       info_hash):
        """
        Call create_circuit

        :param goal_hops: the hop count in the circuit
        :type goal_hops: int
        :param ctype: type of circuit to create
        :type ctype: str
        :param required_endpoint: the endpoint to use
        :type required_endpoint: (str, int ,str)
        :param info_hash: the infohash to assign to this circuit
        :type info_hash: str
        :return: RPC response code
        :rtype: str
        """
        if not self.session_started:
            logging.error("Attempted create_circuit without Session")
            return False
        dec_required_endpoint = None
        if required_endpoint:
            dec_required_endpoint = (required_endpoint[0],
                                     required_endpoint[1],
                                     required_endpoint[2].decode("HEX"))
        return blockingCallFromThread(reactor,
                                      self.community.create_circuit,
                                      goal_hops,
                                      ctype,
                                      None,
                                      dec_required_endpoint,
                                      unhexlify(info_hash) if info_hash else None)

    def on_data(self, msg):
        """
        Callback for when the main process wants us to send_data

        :param msg: the serialized data
        :type msg: str
        :returns: None
        """
        s_cd_list, s_circuit_id,\
            s_d_addr, s_s_addr,\
            data = fix_split(5, ';', msg.split(';'))
        candidates = [Candidate((s_cd[0], int(s_cd[1])), False)
                      for s_cd in [s_cd.split(':')
                                   for s_cd in s_cd_list.split(',')]]
        circuit_id = int(s_circuit_id)
        dest_address = s_d_addr.split(':')
        dest_address = (dest_address[0], int(dest_address[1]))
        source_address = s_s_addr.split(':')
        source_address = (source_address[0], int(source_address[1]))
        if circuit_id in self.community.circuits:
            self.community.send_data(candidates, circuit_id,
                                     dest_address, source_address,
                                     data)

    def on_incoming_from_tunnel(self, circuit, origin, data,
                                anon_seed):
        """
        Callback for when data should be delivered

        :param circuit: the originating circuits
        :type circuit: Tribler.community.tunnel.remotes.circuit.Circuit
        :param origin: the originator's address
        :type origin: (str, int)
        :param data: the data to deliver
        :type data: str
        :param anon_seed: is an anonymous seed
        :type anon_seed: bool
        :returns: None
        """
        self.write_data(";".join([str(circuit.circuit_id),
                                  origin[0],
                                  str(origin[1]),
                                  "1" if anon_seed else "0",
                                  data]))

    def on_exit(self, msg):
        """
        Callback for when the main process wants us to exit

        :param msg: the exit flag
        :type msg: str
        :returns: None
        """
        @inlineCallbacks
        def session_shutdown():
            yield self.session.shutdown()

        if self.session:
            session_shutdown()
        self.write_exit(RPC_RESPONSE_OK)
        self.end()

import logging
from collections import defaultdict

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.task import LoopingCall

from Tribler.community.tunnel import CIRCUIT_TYPE_DATA, CIRCUIT_STATE_READY
from Tribler.community.tunnel.hidden_community import HiddenTunnelCommunity
from Tribler.community.tunnel.tunnel_community import RoundRobin, TunnelSettings
from Tribler.community.tunnel.Socks5.server import Socks5Server
from Tribler.community.tunnel.remotes.sync_dict import SyncDict
from Tribler.community.tunnel.remotes.circuit import Circuit
from Tribler.community.tunnel.remotes.hop import Hop
from Tribler.community.tunnel.processes.processmanager import ProcessManager
from Tribler.Core.simpledefs import NTFY_TUNNEL, NTFY_REMOVE
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class PooledTunnelCommunity(Community):

    """
    A TunnelCommunity using a pool of processes

    This delegates ot multiple child processes running their own
    TunnelCommunity (and Session) instance.

    This is designed such that it can be freely interchanged for
    a normal TunnelCommunity.
    """

    def __init__(self, *args, **kwargs):
        """
        Create a new PooledTunnelCommunity

        :param args: additional arguments
        :type args: list
        :param kwargs: additional keyword-arguments
        :type kwargs: dict
        """
        super(PooledTunnelCommunity, self).__init__(*args, **kwargs)
        self.pool = None
        self.tunnel_logger = logging.getLogger('TunnelLogger')
        self.circuits = SyncDict(Circuit, self,
                                 init_callback=self.init_circuit,
                                 sync_interval=0)
        self.hops = SyncDict(Hop, self, sync_interval=0)
        self.notifier = None
        self.trsession = None
        self.settings = None
        self.socks_server = None
        self.circuits_needed = defaultdict(int)
        self.num_hops_by_downloads = defaultdict(int)  # Keeps track of the number of hops required by downloads
        self.download_states = {}
        self.bittorrent_peers = {}
        self.selection_strategy = RoundRobin(self)

    def initialize(self, tribler_session=None, settings=None):
        """
        Initialize the PooledTunnelCommunity

        :param tribler_session: the Tribler Session to use
        :type tribler_session: Tribler.Core.Session.Session
        :param settings: the TunnelSetting to use
        :type settings: Tribler.community.tunnel.tunnel_community.TunnelSettings
        :return:
        """
        self.trsession = tribler_session
        self.settings = settings if settings\
            else TunnelSettings(tribler_session=tribler_session)

        super(PooledTunnelCommunity, self).initialize()

        self.socks_server = Socks5Server(self,
                                         tribler_session.get_tunnel_community_socks5_listen_ports()
                                         if tribler_session else self.settings.socks_listen_ports)
        self.socks_server.start()

        if self.trsession:
            self.notifier = self.trsession.notifier

        # Multiply the single TunnelSettings by the amount of
        # workers we can handle.
        self.pool = ProcessManager(tribler_session, self)
        suggested_workers = self.pool.get_suggested_workers()
        self.pool.set_worker_count(suggested_workers)
        self.settings.max_circuits *= suggested_workers

        self.register_task("do_circuits",
                           LoopingCall(self.do_circuits)).start(5, now=True)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def unload_community(self):
        """
        Callback for when this community should be unloaded

        :returns: None
        """
        yield self.pool.set_worker_count(0)
        yield super(PooledTunnelCommunity, self).unload_community
        yield self.socks_server.stop()

    @classmethod
    def get_master_members(cls, dispersy):
        """
        Return the normal HiddenTunnelCommunity master member

        :param dispersy: the dispersy instance to use
        :type dispersy: Tribler.dispersy.dispersy.Dispersy
        :return: the master member
        :rtype: Tribler.dispersy.member.Member
        """
        return HiddenTunnelCommunity.get_master_members(dispersy)

    def initiate_conversions(self):
        """
        Create the conversions for this community

        Since it doesn't communicate, we need none.

        :return: the list of our conversions
        :rtype: [Tribler.dispersy.conversion.Conversion]
        """
        return [DefaultConversion(self)]

    @property
    def dispersy_enable_candidate_walker(self):
        """
        Disable sending introduction-requests

        :return: whether we should enable introduction-requests
        :rtype: bool
        """
        return False

    @property
    def dispersy_enable_candidate_walker_responses(self):
        """
        Disable sending introduction-responses

        :return: whether we should enable introduction-responses
        :rtype: bool
        """
        return False

    def init_circuit(self, circuit_id, circuit):
        """
        Callback for when a synced circuit is localized

        :param circuit_id: the circuit's id
        :type circuit_id: long
        :param circuit: the circuit
        :type circuit: Tribler.community.tunnel.remotes.circuit.Circuit
        :returns: None
        """
        setattr(circuit, 'proxy', self)
        setattr(circuit, '_logger', logging.getLogger(circuit.__class__.__name__))

    def ip_to_circuit_id(self, ip_str):
        """
        Compatibility method, see HiddenTunnelCommunity
        This is to provide the same interface

        TODO: Refactor to shared abstract class
        """
        return HiddenTunnelCommunity.ip_to_circuit_id(ip_str)

    def tunnels_ready(self, hops):
        """
        Compatibility method, see TunnelCommunity
        This is to provide the same interface

        TODO: This is duplicate code, refactor to shared abstract class
        """
        if hops > 0:
            if self.settings.min_circuits:
                return min(1, len(self.active_data_circuits(hops)) / float(self.settings.min_circuits))
            else:
                return 1 if self.active_data_circuits(hops) else 0
        return 1

    def build_tunnels(self, hops):
        """
        Compatibility method, see TunnelCommunity
        This is to provide the same interface

        TODO: This is duplicate code, refactor to shared abstract class
        """
        if hops > 0:
            self.num_hops_by_downloads[hops] += 1
            self.circuits_needed[hops] = max(1, self.settings.max_circuits, self.circuits_needed[hops])
            self.do_circuits()

    def on_download_removed(self, download):
        """
        Compatibility method, see TunnelCommunity
        This is to provide the same interface

        TODO: This is duplicate code, refactor to shared abstract class
        """
        if download.get_hops() > 0:
            self.num_hops_by_downloads[download.get_hops()] -= 1
            if self.num_hops_by_downloads[download.get_hops()] == 0:
                self.circuits_needed[download.get_hops()] = 0

    @inlineCallbacks
    def do_circuits(self):
        """
        Callback for when we need to try and reach our required
        amount of circuits

        TODO: This is partially duplicate code, try to refactor part of it to a shared class?
        """
        for circuit_length, num_circuits in self.circuits_needed.items():
            num_to_build = num_circuits - len(self.data_circuits(circuit_length))
            self.tunnel_logger.info("want %d data circuits of length %d", num_to_build, circuit_length)
            success = 0
            for _ in xrange(num_to_build):
                rval = yield self.create_circuit(circuit_length)
                if rval:
                    success += 1
            if success < num_to_build:
                self.tunnel_logger.info("circuit creation of %d circuits failed, no need to continue",
                                        num_to_build)

    def data_circuits(self, hops=None):
        """
        Compatibility method, see TunnelCommunity
        This is to provide the same interface

        TODO: This is duplicate code, refactor to shared abstract class
        """
        return {cid: c for cid, c in self.circuits.items()
                if c.ctype == CIRCUIT_TYPE_DATA and (hops is None or hops == len(c.hops))}

    def active_data_circuits(self, hops=None):
        """
        Compatibility method, see TunnelCommunity
        This is to provide the same interface

        TODO: This is duplicate code, refactor to shared abstract class
        """
        return {cid: c for cid, c in self.circuits.items()
                if c.state == CIRCUIT_STATE_READY and c.ctype == CIRCUIT_TYPE_DATA and
                (hops is None or hops == len(c.hops))}

    def readd_bittorrent_peers(self):
        """
        Compatibility method, see TunnelCommunity
        This is to provide the same interface

        TODO: This is duplicate code, refactor to shared abstract class
        """
        for torrent, peers in self.bittorrent_peers.items():
            infohash = torrent.tdef.get_infohash()
            for peer in peers:
                self.tunnel_logger.info("Re-adding peer %s to torrent %s", peer, infohash.encode("hex"))
                torrent.add_peer(peer)
            if not self.trsession.has_download(infohash):
                del self.bittorrent_peers[torrent]

    def remove_circuit(self, circuit_id):
        """
        Compatibility method, see TunnelCommunity
        This is to provide the same interface

        TODO: This is partially duplicate code, refactor to shared abstract class
        """
        if circuit_id in self.circuits:
            circuit = self.circuits.pop(circuit_id)

            if circuit.hops:
                hop = self.hops[circuit.hops[0]]
                candidate = Candidate((circuit.first_hop[0], circuit.first_hop[1]), False)
                candidate.associate(self.dispersy.get_member(public_key=hop.node_public_key))
                self.notifier.notify(NTFY_TUNNEL, NTFY_REMOVE, circuit, candidate)

            affected_peers = self.socks_server.circuit_dead(circuit)
            ltmgr = self.trsession.lm.ltmgr if self.trsession and self.trsession.get_libtorrent() else None
            if ltmgr:
                affected_torrents = {d: affected_peers.intersection(peer.ip for peer in d.handle.get_peer_info())
                                     for d, s in ltmgr.torrents.values() if s == ltmgr.get_session(d.get_hops())}

                for download, peers in affected_torrents.iteritems():
                    infohash = download.tdef.get_infohash()
                    if peers and self.trsession.has_download(infohash):
                        if download not in self.bittorrent_peers:
                            self.bittorrent_peers[download] = peers
                        else:
                            self.bittorrent_peers[download] = peers | self.bittorrent_peers[download]

                # If there are active circuits, add peers immediately. Otherwise postpone.
                if self.active_data_circuits():
                    self.readd_bittorrent_peers()

    def monitor_downloads(self, dslist):
        """
        Monitor a list of downloads

        :param dslist: the list of downloads to monitor
        :type dslist: [Tribler.Core.DownloadState.DownloadState]
        :returns: None
        """
        infohashes = HiddenTunnelCommunity.downloads_to_infohash_tuples(dslist)
        self.download_states = {HiddenTunnelCommunity.get_lookup_info_hash(infohash_t[0]): infohash_t[2]
                                for infohash_t in infohashes}
        self.pool.monitor_infohashes(infohashes)

    def send_data(self, candidates, circuit_id, dest_address, source_address, data):
        """
        Send data over a circuit

        :param candidates: the candidates to use
        :type candidates: Tribler.dispersy.candidate.Candidate
        :param circuit_id: the circuit id to send over
        :type circuit_id: long
        :param dest_address: the destination address to send to
        :type dest_address: (str, int)
        :param source_address: the source address to send from
        :type source_address: (str, int)
        :param data: the data to send
        :type data: str
        :return: the length of the data sent
        :rtype: int
        """
        if circuit_id not in self.circuits.keys():
            self.tunnel_logger.error("Tried to send data over a removed circuit")
            if len(self.circuits.keys()) > 0:
                self.pool.send_data(candidates, self.circuits.keys()[0], dest_address, source_address, data)
                return len(data)
            else:
                return 0
        self.pool.send_data(candidates, circuit_id, dest_address, source_address, data)
        return len(data)

    @inlineCallbacks
    def create_circuit(self, goal_hops, ctype=CIRCUIT_TYPE_DATA,
                       callback=None, required_endpoint=None,
                       info_hash=None):
        """
        Try to create a circuit

        :param goal_hops: the hop count in the circuit
        :type goal_hops: int
        :param ctype: type of circuit to create
        :type ctype: str
        :param callback: the callback for when it is created
        :type callback: func
        :param required_endpoint: the endpoint to use
        :type required_endpoint: (str, int ,str)
        :param info_hash: the infohash to assign to this circuit
        :type info_hash: str
        :return: the newly created circuit id or False
        :rtype: long or False
        """
        circuit_id = yield self.pool.create_circuit(goal_hops, ctype, required_endpoint, info_hash)
        if circuit_id:
            self.readd_bittorrent_peers()
        returnValue(circuit_id)

    def increase_bytes_sent(self, obj, num_bytes):
        """
        Compatibility method, see TunnelCommunity

        This is disabled because we don't own the circuits.
        """
        pass

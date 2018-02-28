import time

from twisted.internet.defer import inlineCallbacks

from Tribler.community.triblertunnel.dispatcher import TunnelDispatcher
from Tribler.Core.simpledefs import NTFY_TUNNEL, NTFY_IP_RECREATE, NTFY_REMOVE, NTFY_EXTENDED, NTFY_CREATED,\
    NTFY_JOINED, DLSTATUS_SEEDING, DLSTATUS_DOWNLOADING, DLSTATUS_STOPPED
from Tribler.Core.Socks5.server import Socks5Server
from Tribler.dispersy.util import call_on_reactor_thread
from Tribler.pyipv8.ipv8.messaging.anonymization.community import CreatePayload
from Tribler.pyipv8.ipv8.messaging.anonymization.hidden_services import HiddenTunnelCommunity
from Tribler.pyipv8.ipv8.messaging.anonymization.payload import LinkedE2EPayload
from Tribler.pyipv8.ipv8.messaging.anonymization.tunnel import CIRCUIT_STATE_READY, CIRCUIT_TYPE_RP
from Tribler.pyipv8.ipv8.peer import Peer


class TriblerTunnelCommunity(HiddenTunnelCommunity):
    master_peer = Peer("3081a7301006072a8648ce3d020106052b81040027038192000402e1cd2a8158c078f5a048dd2caa4a868852e1758"
                       "71c819947b2aabe414a6b1b6c35e89f554dd94b475c612a692a3132bbe4a30813702acd7647eb8023700dcda5b47d"
                       "fe15f94a88049c2bb05f83f37d2cd85cce5efb8a9da6ac97dcdf97f83ae8696ffd1fab783ed28d004a99942fba756"
                       "8a3edc2052ce379db4b3f40411d55c28e16466e9750038c677bb561eab325".decode('hex'))

    def __init__(self, *args, **kwargs):
        self.tribler_session = kwargs.pop('tribler_session', None)
        super(TriblerTunnelCommunity, self).__init__(*args, **kwargs)
        self._use_main_thread = True

        if self.tribler_session:
            self.settings.become_exitnode = self.tribler_session.config.get_tunnel_community_exitnode_enabled()
            socks_listen_ports = self.tribler_session.config.get_tunnel_community_socks5_listen_ports()
            self.tribler_session.lm.tunnel_community = self
        else:
            socks_listen_ports = range(1080, 1085)

        self.bittorrent_peers = {}
        self.dispatcher = TunnelDispatcher(self)
        self.download_states = {}

        # Start the SOCKS5 servers
        self.socks_servers = []
        for port in socks_listen_ports:
            socks_server = Socks5Server(port, self.dispatcher)
            socks_server.start()
            self.socks_servers.append(socks_server)

        self.dispatcher.set_socks_servers(self.socks_servers)

    def on_download_removed(self, download):
        """
        This method is called when a download is removed. We check here whether we can stop building circuits for a
        specific number of hops in case it hasn't been finished yet.
        """
        if download.get_hops() > 0:
            self.num_hops_by_downloads[download.get_hops()] -= 1
            if self.num_hops_by_downloads[download.get_hops()] == 0:
                self.circuits_needed[download.get_hops()] = 0

    def readd_bittorrent_peers(self):
        for torrent, peers in self.bittorrent_peers.items():
            infohash = torrent.tdef.get_infohash().encode("hex")
            for peer in peers:
                self.logger.info("Re-adding peer %s to torrent %s", peer, infohash)
                torrent.add_peer(peer)
            del self.bittorrent_peers[torrent]

    def update_torrent(self, peers, handle, download):
        peers = peers.intersection(handle.get_peer_info())
        if peers:
            if download not in self.bittorrent_peers:
                self.bittorrent_peers[download] = peers
            else:
                self.bittorrent_peers[download] = peers | self.bittorrent_peers[download]

            # If there are active circuits, add peers immediately. Otherwise postpone.
            if self.active_data_circuits():
                self.readd_bittorrent_peers()

    def remove_circuit(self, circuit_id, additional_info='', destroy=False):
        if circuit_id not in self.circuits:
            self.logger.warning("Circuit %d not found when trying to remove it", circuit_id)
            return

        circuit = self.circuits[circuit_id]

        # Send the notification
        if self.tribler_session:
            self.tribler_session.notifier.notify(NTFY_TUNNEL, NTFY_REMOVE, circuit, circuit.sock_addr)

        affected_peers = self.dispatcher.circuit_dead(circuit)
        ltmgr = self.tribler_session.lm.ltmgr \
            if self.tribler_session and self.tribler_session.config.get_libtorrent_enabled() else None
        if ltmgr:
            for d, s in ltmgr.torrents.values():
                if s == ltmgr.get_session(d.get_hops()):
                    d.get_handle().addCallback(lambda handle: self.update_torrent(affected_peers, handle, d))

        # Now we actually remove the circuit
        super(TriblerTunnelCommunity, self).remove_circuit(circuit_id, additional_info=additional_info, destroy=destroy)

    def remove_relay(self, circuit_id, additional_info='', destroy=False, got_destroy_from=None, both_sides=True):
        removed_relays = super(TriblerTunnelCommunity, self).remove_relay(circuit_id,
                                                                          additional_info=additional_info,
                                                                          destroy=destroy,
                                                                          got_destroy_from=got_destroy_from,
                                                                          both_sides=both_sides)

        if self.tribler_session:
            for removed_relay in removed_relays:
                self.tribler_session.notifier.notify(NTFY_TUNNEL, NTFY_REMOVE, removed_relay, removed_relay.sock_addr)

    def remove_exit_socket(self, circuit_id, additional_info='', destroy=False):
        if circuit_id in self.exit_sockets and self.tribler_session:
            exit_socket = self.exit_sockets[circuit_id]
            self.tribler_session.notifier.notify(NTFY_TUNNEL, NTFY_REMOVE, exit_socket, exit_socket.sock_addr)

        super(TriblerTunnelCommunity, self).remove_exit_socket(circuit_id, additional_info=additional_info,
                                                               destroy=destroy)

    def _ours_on_created_extended(self, circuit, payload):
        super(TriblerTunnelCommunity, self)._ours_on_created_extended(circuit, payload)

        if circuit.state == CIRCUIT_STATE_READY:
            # Re-add BitTorrent peers, if needed.
            self.readd_bittorrent_peers()

        if self.tribler_session:
            self.tribler_session.notifier.notify(
                NTFY_TUNNEL, NTFY_CREATED if len(circuit.hops) == 1 else NTFY_EXTENDED, circuit)

    def on_create(self, source_address, data, _):
        _, payload = self._ez_unpack_noauth(CreatePayload, data)

        if not self.check_create(payload):
            return

        circuit_id = payload.circuit_id

        if self.tribler_session:
            self.tribler_session.notifier.notify(NTFY_TUNNEL, NTFY_JOINED, source_address, circuit_id)

        super(TriblerTunnelCommunity, self).on_create(source_address, data, _)

    def on_raw_data(self, circuit, origin, data):
        anon_seed = circuit.ctype == CIRCUIT_TYPE_RP
        self.dispatcher.on_incoming_from_tunnel(self, circuit, origin, data, anon_seed)

    @call_on_reactor_thread
    def monitor_downloads(self, dslist):
        # Monitor downloads with anonymous flag set, and build rendezvous/introduction points when needed.
        new_states = {}
        hops = {}

        for ds in dslist:
            download = ds.get_download()
            if download.get_hops() > 0:
                # Convert the real infohash to the infohash used for looking up introduction points
                real_info_hash = download.get_def().get_infohash()
                info_hash = self.get_lookup_info_hash(real_info_hash)
                hops[info_hash] = download.get_hops()
                self.service_callbacks[info_hash] = download.add_peer
                new_states[info_hash] = ds.get_status()

        self.hops = hops

        for info_hash in set(new_states.keys() + self.download_states.keys()):
            new_state = new_states.get(info_hash, None)
            old_state = self.download_states.get(info_hash, None)
            state_changed = new_state != old_state

            # Stop creating introduction points if the download doesn't exist anymore
            if info_hash in self.infohash_ip_circuits and new_state is None:
                del self.infohash_ip_circuits[info_hash]

            # If the introducing circuit does not exist anymore or timed out: Build a new circuit
            if info_hash in self.infohash_ip_circuits:
                for (circuit_id, time_created) in self.infohash_ip_circuits[info_hash]:
                    if circuit_id not in self.my_intro_points and time_created < time.time() - 30:
                        self.infohash_ip_circuits[info_hash].remove((circuit_id, time_created))
                        if self.tribler_session.notifier:
                            self.tribler_session.notifier.notify(
                                NTFY_TUNNEL, NTFY_IP_RECREATE, circuit_id, info_hash.encode('hex')[:6])
                        self.logger.info('Recreate the introducing circuit for %s', info_hash.encode('hex'))
                        self.create_introduction_point(info_hash)

            time_elapsed = (time.time() - self.last_dht_lookup.get(info_hash, 0))
            force_dht_lookup = time_elapsed >= self.settings.dht_lookup_interval
            if (state_changed or force_dht_lookup) and \
                    (new_state == DLSTATUS_SEEDING or new_state == DLSTATUS_DOWNLOADING):
                self.logger.info('Do dht lookup to find hidden services peers for %s', info_hash.encode('hex'))
                self.do_raw_dht_lookup(info_hash)

            if state_changed and new_state == DLSTATUS_SEEDING:
                self.create_introduction_point(info_hash)

            elif state_changed and new_state in [DLSTATUS_STOPPED, None]:
                if info_hash in self.infohash_pex:
                    self.infohash_pex.pop(info_hash)

                for cid, info_hash_hops in self.my_download_points.items():
                    if info_hash_hops[0] == info_hash:
                        self.remove_circuit(cid, 'download stopped', destroy=True)

                for cid, info_hash_list in self.my_intro_points.items():
                    for i in xrange(len(info_hash_list) - 1, -1, -1):
                        if info_hash_list[i] == info_hash:
                            info_hash_list.pop(i)

                    if len(info_hash_list) == 0:
                        self.remove_circuit(cid, 'all downloads stopped', destroy=True)

        self.download_states = new_states

    def get_download(self, lookup_info_hash):
        for download in self.tribler_session.get_downloads():
            if lookup_info_hash == self.get_lookup_info_hash(download.get_def().get_infohash()):
                return download

    def create_introduction_point(self, info_hash, amount=1):
        download = self.get_download(info_hash)
        if download:
            download.add_peer(('1.1.1.1', 1024))
        super(TriblerTunnelCommunity, self).create_introduction_point(info_hash, amount)

    def on_linked_e2e(self, source_address, data, circuit_id):
        _, payload = self._ez_unpack_noauth(LinkedE2EPayload, data)
        cache = self.request_cache.get(u"link-request", payload.identifier)
        if cache:
            download = self.get_download(cache.info_hash)
            if download:
                download.add_peer((self.circuit_id_to_ip(cache.circuit.circuit_id), 1024))
            else:
                self.logger.error('On linked e2e: could not find download!')
        super(TriblerTunnelCommunity, self).on_linked_e2e(source_address, data, circuit_id)

    @inlineCallbacks
    def unload(self):
        for socks_server in self.socks_servers:
            yield socks_server.stop()

        super(TriblerTunnelCommunity, self).unload()

from __future__ import absolute_import

import os
import sys
import time
from binascii import hexlify, unhexlify

from six.moves import xrange

from twisted.internet.defer import Deferred, inlineCallbacks, succeed

from Tribler.Core.Modules.wallet.bandwidth_block import TriblerBandwidthBlock
from Tribler.Core.Socks5.server import Socks5Server
from Tribler.Core.simpledefs import (DLSTATUS_DOWNLOADING, DLSTATUS_METADATA, DLSTATUS_SEEDING, DLSTATUS_STOPPED,
                                     NTFY_CREATED, NTFY_EXTENDED, NTFY_IP_RECREATE, NTFY_JOINED, NTFY_REMOVE,
                                     NTFY_TUNNEL)
from Tribler.community.triblertunnel.caches import BalanceRequestCache
from Tribler.community.triblertunnel.discovery import GoldenRatioStrategy
from Tribler.community.triblertunnel.dispatcher import TunnelDispatcher
from Tribler.community.triblertunnel.payload import BalanceRequestPayload, BalanceResponsePayload, PayoutPayload
from Tribler.pyipv8.ipv8.attestation.trustchain.block import EMPTY_PK
from Tribler.pyipv8.ipv8.messaging.anonymization.caches import ExtendRequestCache
from Tribler.pyipv8.ipv8.messaging.anonymization.community import message_to_payload
from Tribler.pyipv8.ipv8.messaging.anonymization.hidden_services import HiddenTunnelCommunity
from Tribler.pyipv8.ipv8.messaging.anonymization.payload import LinkedE2EPayload, NO_CRYPTO_PACKETS
from Tribler.pyipv8.ipv8.messaging.anonymization.tunnel import (CIRCUIT_STATE_READY, CIRCUIT_TYPE_DATA,
                                                                CIRCUIT_TYPE_RENDEZVOUS, CIRCUIT_TYPE_RP, EXIT_NODE,
                                                                RelayRoute)
from Tribler.pyipv8.ipv8.peer import Peer
from Tribler.pyipv8.ipv8.peerdiscovery.network import Network


class TriblerTunnelCommunity(HiddenTunnelCommunity):
    """
    This community is built upon the anonymous messaging layer in IPv8.
    It adds support for libtorrent anonymous downloads and bandwidth token payout when closing circuits.
    """
    master_peer = ("3081a7301006072a8648ce3d020106052b81040027038192000400965194026c987edad7c5c0364a95dfa4e961e"
                   "ec6d1711678be182a31824363db3a54caa11e9b6f1d6051c2f33578b51c12eff3833b7c74c5a243b8705e4e032b"
                   "14904f4d8855e2044c0408a5729cd4e5b286fec66866811d5439049448e5b8b818d8c29a84a074a13f5e7e414d4"
                   "e5b1b115a221fe697b89bd3e63c7aecd7617f789a203a4eacf680279224b390e836")
    master_peer = Peer(unhexlify(master_peer))

    def __init__(self, *args, **kwargs):
        self.tribler_session = kwargs.pop('tribler_session', None)
        num_competing_slots = kwargs.pop('competing_slots', 15)
        num_random_slots = kwargs.pop('random_slots', 5)
        self.bandwidth_wallet = kwargs.pop('bandwidth_wallet', None)
        socks_listen_ports = kwargs.pop('socks_listen_ports', None)
        state_path = self.tribler_session.config.get_state_dir() if self.tribler_session else ''
        self.exitnode_cache = kwargs.pop('exitnode_cache', os.path.join(state_path, 'exitnode_cache.dat'))
        super(TriblerTunnelCommunity, self).__init__(*args, **kwargs)
        self._use_main_thread = True

        if self.tribler_session:
            self.settings.become_exitnode = self.tribler_session.config.get_tunnel_community_exitnode_enabled()
            self.tribler_session.lm.tunnel_community = self

            if not socks_listen_ports:
                socks_listen_ports = self.tribler_session.config.get_tunnel_community_socks5_listen_ports()
        elif socks_listen_ports is None:
            socks_listen_ports = range(1080, 1085)

        self.bittorrent_peers = {}
        self.dispatcher = TunnelDispatcher(self)
        self.download_states = {}
        self.competing_slots = [(0, None)] * num_competing_slots  # 1st tuple item = token balance, 2nd = circuit id
        self.random_slots = [None] * num_random_slots
        self.reject_callback = None  # This callback is invoked with a tuple (time, balance) when we reject a circuit

        # Start the SOCKS5 servers
        self.socks_servers = []
        for port in socks_listen_ports:
            socks_server = Socks5Server(port, self.dispatcher)
            socks_server.start()
            self.socks_servers.append(socks_server)

        self.dispatcher.set_socks_servers(self.socks_servers)

        self.decode_map.update({
            chr(23): self.on_payout_block,
        })

        self.decode_map_private.update({
            chr(24): self.on_balance_request_cell,
            chr(25): self.on_relay_balance_request_cell,
            chr(26): self.on_balance_response_cell,
            chr(27): self.on_relay_balance_response_cell,
        })

        message_to_payload[u"balance-request"] = (24, BalanceRequestPayload)
        message_to_payload[u"relay-balance-request"] = (25, BalanceRequestPayload)
        message_to_payload[u"balance-response"] = (26, BalanceResponsePayload)
        message_to_payload[u"relay-balance-response"] = (27, BalanceResponsePayload)

        NO_CRYPTO_PACKETS.extend([24, 26])

        if self.exitnode_cache:
            self.restore_exitnodes_from_disk()

    def get_available_strategies(self):
        return super(TriblerTunnelCommunity, self).get_available_strategies().update({'GoldenRatioStrategy':
                                                                                          GoldenRatioStrategy})

    def cache_exitnodes_to_disk(self):
        """
        Wite a copy of self.exit_candidates to the file self.exitnode_cache.

        :returns: None
        """
        exit_nodes = Network()
        for peer in self.exit_candidates.values():
            exit_nodes.add_verified_peer(peer)
        self.logger.debug('Writing exit nodes to cache: %s', self.exitnode_cache)
        with open(self.exitnode_cache, 'w') as cache:
            cache.write(exit_nodes.snapshot())

    def restore_exitnodes_from_disk(self):
        """
        Send introduction requests to peers stored in the file self.exitnode_cache.

        :returns: None
        """
        if os.path.isfile(self.exitnode_cache):
            self.logger.debug('Loading exit nodes from cache: %s', self.exitnode_cache)
            exit_nodes = Network()
            with open(self.exitnode_cache, 'r') as cache:
                exit_nodes.load_snapshot(cache.read())
            for exit_node in exit_nodes.get_walkable_addresses():
                self.endpoint.send(exit_node, self.create_introduction_request(exit_node))
        else:
            self.logger.error('Could not retrieve backup exitnode cache, file does not exist!')

    def on_token_balance(self, circuit_id, balance):
        """
        We received the token balance of a circuit initiator. Check whether we can allocate a slot to this user.
        """
        if not self.request_cache.has(u"balance-request", circuit_id):
            self.logger.warning("Received token balance without associated request cache!")
            return

        cache = self.request_cache.pop(u"balance-request", circuit_id)

        lowest_balance = sys.maxsize
        lowest_index = -1
        for ind, tup in enumerate(self.competing_slots):
            if not tup[1]:
                # The slot is empty, take it
                self.competing_slots[ind] = (balance, circuit_id)
                cache.balance_deferred.callback(True)
                return

            if tup[0] < lowest_balance:
                lowest_balance = tup[0]
                lowest_index = ind

        if balance > lowest_balance:
            # We kick this user out
            old_circuit_id = self.competing_slots[lowest_index][1]
            self.logger.info("Kicked out circuit %s (balance: %s) in favor of %s (balance: %s)",
                             old_circuit_id, lowest_balance, circuit_id, balance)
            self.competing_slots[lowest_index] = (balance, circuit_id)

            self.remove_relay(old_circuit_id, destroy=True)
            self.remove_exit_socket(old_circuit_id, destroy=True)

            cache.balance_deferred.callback(True)
        else:
            # We can't compete with the balances in the existing slots
            if self.reject_callback:
                self.reject_callback(time.time(), balance)
            cache.balance_deferred.callback(False)

    def should_join_circuit(self, create_payload, previous_node_address):
        """
        Check whether we should join a circuit. Returns a deferred that fires with a boolean.
        """
        if self.settings.max_joined_circuits <= len(self.relay_from_to) + len(self.exit_sockets):
            self.logger.warning("too many relays (%d)", (len(self.relay_from_to) + len(self.exit_sockets)))
            return succeed(False)

        # Check whether we have a random open slot, if so, allocate this to this request.
        circuit_id = create_payload.circuit_id
        for index, slot in enumerate(self.random_slots):
            if not slot:
                self.random_slots[index] = circuit_id
                return succeed(True)

        # No random slots but this user might be allocated a competing slot.
        # Next, we request the token balance of the circuit initiator.
        balance_deferred = Deferred()
        self.request_cache.add(BalanceRequestCache(self, circuit_id, balance_deferred))

        # Temporarily add these values, otherwise we are unable to communicate with the previous hop.
        self.directions[circuit_id] = EXIT_NODE
        shared_secret, _, _ = self.crypto.generate_diffie_shared_secret(create_payload.key)
        self.relay_session_keys[circuit_id] = self.crypto.generate_session_keys(shared_secret)

        self.send_cell([Peer(create_payload.node_public_key, previous_node_address)], u"balance-request",
                       BalanceRequestPayload(circuit_id))

        self.directions.pop(circuit_id, None)
        self.relay_session_keys.pop(circuit_id, None)

        return balance_deferred

    def on_payout_block(self, source_address, data):
        if not self.bandwidth_wallet:
            self.logger.warning("Got payout while not having a TrustChain community running!")
            return

        payload = self._ez_unpack_noauth(PayoutPayload, data, global_time=False)
        peer = Peer(payload.public_key, source_address)

        def on_transaction_completed(blocks):
            # Send the next payout
            if blocks and payload.circuit_id in self.relay_from_to and block.transaction['down'] > payload.base_amount:
                relay = self.relay_from_to[payload.circuit_id]
                self._logger.info("Sending next payout to peer %s", relay.peer)
                self.do_payout(relay.peer, relay.circuit_id, block.transaction['down'] - payload.base_amount * 2,
                               payload.base_amount)

        block = TriblerBandwidthBlock.from_payload(payload, self.serializer)
        self.bandwidth_wallet.trustchain.process_half_block(block, peer)\
            .addCallbacks(on_transaction_completed, lambda _: None)

        # Check whether the block has been added to the database and has been verified
        if not self.bandwidth_wallet.trustchain.persistence.contains(block):
            self.logger.warning("Not proceeding with payout - received payout block is not valid")
            return

    def on_balance_request_cell(self, source_address, data, _):
        payload = self._ez_unpack_noauth(BalanceRequestPayload, data, global_time=False)

        circuit_id = payload.circuit_id
        request = self.request_cache.get(u"anon-circuit", circuit_id)
        if not request:
            self.logger.warning("Circuit creation cache for id %s not found!", circuit_id)
            return

        if request.should_forward:
            forwarding_relay = RelayRoute(request.from_circuit_id, request.peer)
            self.send_cell([forwarding_relay.peer.address], u"relay-balance-request",
                           BalanceRequestPayload(forwarding_relay.circuit_id))
        else:
            self.on_balance_request(payload)

    def on_relay_balance_request_cell(self, source_address, data, _):
        payload = self._ez_unpack_noauth(BalanceRequestPayload, data, global_time=False)
        self.on_balance_request(payload)

    def on_balance_request(self, payload):
        """
        We received a balance request from a relay or exit node. Respond with the latest block in our chain.
        """
        if not self.bandwidth_wallet:
            self.logger.warn("Bandwidth wallet is not available, not sending balance response!")
            return

        # Get the latest block
        latest_block = self.bandwidth_wallet.trustchain.persistence.get_latest(self.my_peer.public_key.key_to_bin(),
                                                                               block_type='tribler_bandwidth')
        if not latest_block:
            latest_block = TriblerBandwidthBlock()
        latest_block.public_key = EMPTY_PK  # We hide the public key

        # We either send the response directly or relay the response to the last verified hop
        circuit = self.circuits[payload.circuit_id]
        if not circuit.hops:
            self.increase_bytes_sent(circuit, self.send_cell([circuit.peer.address],
                                                             u"balance-response",
                                                             BalanceResponsePayload.from_half_block(
                                                                 latest_block, circuit.circuit_id)))
        else:
            self.increase_bytes_sent(circuit, self.send_cell([circuit.peer.address],
                                                             u"relay-balance-response",
                                                             BalanceResponsePayload.from_half_block(
                                                                 latest_block, circuit.circuit_id)))

    def on_balance_response_cell(self, source_address, data, _):
        payload = self._ez_unpack_noauth(BalanceResponsePayload, data, global_time=False)
        block = TriblerBandwidthBlock.from_payload(payload, self.serializer)
        if not block.transaction:
            self.on_token_balance(payload.circuit_id, 0)
        else:
            self.on_token_balance(payload.circuit_id,
                                  block.transaction["total_up"] - block.transaction["total_down"])

    def on_relay_balance_response_cell(self, source_address, data, _):
        payload = self._ez_unpack_noauth(BalanceResponsePayload, data, global_time=False)
        block = TriblerBandwidthBlock.from_payload(payload, self.serializer)

        # At this point, we don't have the circuit ID of the follow-up hop. We have to iterate over the items in the
        # request cache and find the link to the next hop.
        for cache in self.request_cache._identifiers.values():
            if isinstance(cache, ExtendRequestCache) and cache.from_circuit_id == payload.circuit_id:
                self.send_cell([cache.to_peer.address],
                               u"balance-response",
                               BalanceResponsePayload.from_half_block(block, cache.to_circuit_id))

    def readd_bittorrent_peers(self):
        for torrent, peers in self.bittorrent_peers.items():
            infohash = hexlify(torrent.tdef.get_infohash())
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

    def do_payout(self, peer, circuit_id, amount, base_amount):
        """
        Perform a payout to a specific peer.
        :param peer: The peer to perform the payout to, usually the next node in the circuit.
        :param circuit_id: The circuit id of the payout, used by the subsequent node.
        :param amount: The amount to put in the transaction, multiplier of base_amount.
        :param base_amount: The base amount for the payouts.
        """
        self.logger.info("Sending payout of %d (base: %d) to %s (cid: %s)", amount, base_amount, peer, circuit_id)

        block = TriblerBandwidthBlock.create(
            'tribler_bandwidth',
            {'up': 0, 'down': amount},
            self.bandwidth_wallet.trustchain.persistence,
            self.my_peer.public_key.key_to_bin(),
            link_pk=peer.public_key.key_to_bin())
        block.sign(self.my_peer.key)
        self.bandwidth_wallet.trustchain.persistence.add_block(block)

        payload = PayoutPayload.from_half_block(block, circuit_id, base_amount).to_pack_list()
        packet = self._ez_pack(self._prefix, 23, [payload], False)
        self.send_packet([peer], packet)

    def clean_from_slots(self, circuit_id):
        """
        Clean a specific circuit from the allocated slots.
        """
        for ind, slot in enumerate(self.random_slots):
            if slot == circuit_id:
                self.random_slots[ind] = None

        for ind, tup in enumerate(self.competing_slots):
            if tup[1] == circuit_id:
                self.competing_slots[ind] = (0, None)

    def remove_circuit(self, circuit_id, additional_info='', remove_now=False, destroy=False):
        if circuit_id not in self.circuits:
            self.logger.warning("Circuit %d not found when trying to remove it", circuit_id)
            return

        circuit = self.circuits[circuit_id]

        # Send the notification
        if self.tribler_session:
            self.tribler_session.notifier.notify(NTFY_TUNNEL, NTFY_REMOVE, circuit, additional_info)

        if circuit.bytes_down >= 1024 * 1024 and self.bandwidth_wallet:
            # We should perform a payout of the removed circuit.
            if circuit.ctype == CIRCUIT_TYPE_RENDEZVOUS:
                # We remove an e2e circuit as downloader. We pay the subsequent nodes in the downloader part of the e2e
                # circuit. In addition, we pay for one hop seeder anonymity since we don't know the circuit length at
                # the seeder side.
                self.do_payout(circuit.peer, circuit_id, circuit.bytes_down * ((circuit.goal_hops * 2) + 1),
                               circuit.bytes_down)

            if circuit.ctype == CIRCUIT_TYPE_DATA:
                # We remove a regular data circuit as downloader. Pay the relay nodes and the exit nodes.
                self.do_payout(circuit.peer, circuit_id, circuit.bytes_down * (circuit.goal_hops * 2 - 1),
                               circuit.bytes_down)

            # Reset the circuit byte counters so we do not payout again if we receive a destroy message.
            circuit.bytes_up = circuit.bytes_down = 0

        # Now we actually remove the circuit
        remove_deferred = super(TriblerTunnelCommunity, self)\
            .remove_circuit(circuit_id, additional_info=additional_info, remove_now=remove_now, destroy=destroy)

        affected_peers = self.dispatcher.circuit_dead(circuit)

        def update_torrents(_):
            ltmgr = self.tribler_session.lm.ltmgr \
                if self.tribler_session and self.tribler_session.config.get_libtorrent_enabled() else None
            if ltmgr:
                for d, s in ltmgr.torrents.values():
                    if s == ltmgr.get_session(d.get_hops()):
                        d.get_handle().addCallback(lambda handle, download=d:
                                                   self.update_torrent(affected_peers, handle, download))

        remove_deferred.addCallback(update_torrents)

        return remove_deferred

    def remove_relay(self, circuit_id, additional_info='', remove_now=False, destroy=False, got_destroy_from=None,
                     both_sides=True):
        removed_relays = super(TriblerTunnelCommunity, self).remove_relay(circuit_id,
                                                                          additional_info=additional_info,
                                                                          remove_now=remove_now,
                                                                          destroy=destroy,
                                                                          got_destroy_from=got_destroy_from,
                                                                          both_sides=both_sides)

        self.clean_from_slots(circuit_id)

        if self.tribler_session:
            for removed_relay in removed_relays:
                self.tribler_session.notifier.notify(NTFY_TUNNEL, NTFY_REMOVE, removed_relay, additional_info)

    def remove_exit_socket(self, circuit_id, additional_info='', remove_now=False, destroy=False):
        if circuit_id in self.exit_sockets and self.tribler_session:
            exit_socket = self.exit_sockets[circuit_id]
            self.tribler_session.notifier.notify(NTFY_TUNNEL, NTFY_REMOVE, exit_socket, additional_info)

        self.clean_from_slots(circuit_id)

        super(TriblerTunnelCommunity, self).remove_exit_socket(circuit_id, additional_info=additional_info,
                                                               remove_now=remove_now, destroy=destroy)

    def _ours_on_created_extended(self, circuit, payload):
        super(TriblerTunnelCommunity, self)._ours_on_created_extended(circuit, payload)

        if circuit.state == CIRCUIT_STATE_READY:
            # Re-add BitTorrent peers, if needed.
            self.readd_bittorrent_peers()

        if self.tribler_session:
            self.tribler_session.notifier.notify(
                NTFY_TUNNEL, NTFY_CREATED if len(circuit.hops) == 1 else NTFY_EXTENDED, circuit)

    def join_circuit(self, create_payload, previous_node_address):
        super(TriblerTunnelCommunity, self).join_circuit(create_payload, previous_node_address)

        if self.tribler_session:
            circuit_id = create_payload.circuit_id
            self.tribler_session.notifier.notify(NTFY_TUNNEL, NTFY_JOINED, previous_node_address, circuit_id)

    def on_raw_data(self, circuit, origin, data):
        anon_seed = circuit.ctype == CIRCUIT_TYPE_RP
        self.dispatcher.on_incoming_from_tunnel(self, circuit, origin, data, anon_seed)

    def monitor_downloads(self, dslist):
        # Monitor downloads with anonymous flag set, and build rendezvous/introduction points when needed.
        new_states = {}
        hops = {}
        active_downloads_per_hop = {}

        for ds in dslist:
            download = ds.get_download()
            hop_count = download.get_hops()
            if hop_count > 0:
                # Convert the real infohash to the infohash used for looking up introduction points
                real_info_hash = download.get_def().get_infohash()
                info_hash = self.get_lookup_info_hash(real_info_hash)
                hops[info_hash] = hop_count
                if download.get_state().get_status() in [DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING, DLSTATUS_METADATA]:
                    active_downloads_per_hop[hop_count] = active_downloads_per_hop.get(hop_count, 0) + 1
                self.service_callbacks[info_hash] = download.add_peer
                new_states[info_hash] = ds.get_status()

        self.hops = hops
        # Request 1 circuit per download while ensuring that the total number of circuits requested per hop count
        # stays within min_circuits and max_circuits.
        self.circuits_needed = {hop_count: min(max(download_count, self.settings.min_circuits),
                                               self.settings.max_circuits)
                                for hop_count, download_count in active_downloads_per_hop.items()}

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
                                NTFY_TUNNEL, NTFY_IP_RECREATE, circuit_id, hexlify(info_hash)[:6])
                        self.logger.info('Recreate the introducing circuit for %s', hexlify(info_hash))
                        self.create_introduction_point(info_hash)

            time_elapsed = (time.time() - self.last_dht_lookup.get(info_hash, 0))
            force_dht_lookup = time_elapsed >= self.settings.dht_lookup_interval
            if (state_changed or force_dht_lookup) and (new_state == DLSTATUS_DOWNLOADING):
                self.logger.info('Do dht lookup to find hidden services peers for %s', hexlify(info_hash))
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
        if not self.tribler_session:
            return None

        for download in self.tribler_session.get_downloads():
            if lookup_info_hash == self.get_lookup_info_hash(download.get_def().get_infohash()):
                return download

    def create_introduction_point(self, info_hash, amount=1):
        download = self.get_download(info_hash)
        if download:
            download.add_peer(('1.1.1.1', 1024))
        super(TriblerTunnelCommunity, self).create_introduction_point(info_hash, amount)

    def on_linked_e2e(self, source_address, data, circuit_id):
        payload = self._ez_unpack_noauth(LinkedE2EPayload, data, global_time=False)
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
        if self.bandwidth_wallet:
            self.bandwidth_wallet.shutdown_task_manager()
        for socks_server in self.socks_servers:
            yield socks_server.stop()

        if self.exitnode_cache:
            self.cache_exitnodes_to_disk()

        super(TriblerTunnelCommunity, self).unload()


class TriblerTunnelTestnetCommunity(TriblerTunnelCommunity):
    """
    This community defines a testnet for the anonymous tunnels.
    """
    master_peer = ("3081a7301006072a8648ce3d020106052b81040027038192000401325e6f0a67a92a890344013914fcf9da9b0326"
                   "bf6c845815ec8b537e356a56b2a8c27ac4918078202f60eb29ebf081436136c280316ac461daee2d04cf073d1200"
                   "80d15628af1002b0c0273d9d94fdab08e718f568d83b9c4298117261b5647ca8295f1ba4b880a50fd2ef7041fef7"
                   "edfbef5f02fc03827a2c09c5f9c701f87abacd022c780d76733c133363a5c46c")
    master_peer = Peer(unhexlify(master_peer))

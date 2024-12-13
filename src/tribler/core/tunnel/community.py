from __future__ import annotations

import hashlib
import math
import time
from asyncio import Future, open_connection
from asyncio import TimeoutError as AsyncTimeoutError
from binascii import hexlify, unhexlify
from collections import Counter
from typing import TYPE_CHECKING, Awaitable

import async_timeout
from ipv8.messaging.anonymization.community import unpack_cell
from ipv8.messaging.anonymization.hidden_services import HiddenTunnelCommunity, HiddenTunnelSettings
from ipv8.messaging.anonymization.tunnel import (
    CIRCUIT_STATE_READY,
    CIRCUIT_TYPE_IP_SEEDER,
    CIRCUIT_TYPE_RP_SEEDER,
    PEER_FLAG_EXIT_BT,
    PEER_FLAG_EXIT_IPV8,
    Circuit,
)
from ipv8.peerdiscovery.network import Network
from ipv8.taskmanager import task
from ipv8.util import succeed
from libtorrent import bdecode

from tribler.core.libtorrent.download_manager.download_state import DownloadState, DownloadStatus
from tribler.core.notifier import Notification, Notifier
from tribler.core.tunnel.caches import HTTPRequestCache
from tribler.core.tunnel.dispatcher import TunnelDispatcher
from tribler.core.tunnel.payload import HTTPRequestPayload, HTTPResponsePayload

if TYPE_CHECKING:
    from pathlib import Path

    from ipv8.messaging.anonymization.exit_socket import TunnelExitSocket
    from ipv8.messaging.anonymization.payload import CreatedPayload, CreatePayload, ExtendedPayload
    from ipv8.types import Address

    from tribler.core.libtorrent.download_manager.download import Download
    from tribler.core.libtorrent.download_manager.download_manager import DownloadManager
    from tribler.core.socks5.server import Socks5Server

DESTROY_REASON_BALANCE = 65535
PEER_FLAG_EXIT_HTTP = 32768
MAX_HTTP_PACKET_SIZE = 1400


def is_bencoded(x: bytes) -> bool:
    """
    Returns True is x appears to be valid bencoded byte string.
    """
    if not isinstance(x, bytes):
        msg = f'Expected bytes, got {type(x).__name__}'
        raise TypeError(msg)
    try:
        decoded = bdecode(x)
    except RuntimeError:
        decoded = None
    return decoded is not None


class TriblerTunnelSettings(HiddenTunnelSettings):
    """
    Settings for Tribler's tunnel community.
    """

    exitnode_cache: Path | None = None
    notifier: Notifier
    download_manager: DownloadManager
    socks_servers: list[Socks5Server]
    exitnode_enabled: bool = False
    default_hops: int = 0


class TriblerTunnelCommunity(HiddenTunnelCommunity):
    """
    This community is built upon the anonymous messaging layer in IPv8.
    It adds support for libtorrent anonymous downloads.
    """

    community_id = unhexlify("a3591a6bd89bbaca0974062a1287afcfbc6fd6bc")
    settings_class = TriblerTunnelSettings

    def __init__(self, settings: TriblerTunnelSettings) -> None:
        """
        Create a new tunnel community.
        """
        super().__init__(settings)
        self.settings.endpoint = self.crypto_endpoint

        if settings.exitnode_enabled:
            self.settings.peer_flags |= {PEER_FLAG_EXIT_BT, PEER_FLAG_EXIT_IPV8, PEER_FLAG_EXIT_HTTP}

        self.logger.info("Using %s with flags %s", self.endpoint.__class__.__name__, self.settings.peer_flags)

        self.bittorrent_peers: dict[Download, set[tuple[str, int]]] = {}
        self.dispatcher = TunnelDispatcher(self)
        self.download_states: dict[bytes, DownloadStatus] = {}
        self.last_forced_announce: dict[bytes, float] = {}

        if settings.socks_servers:
            self.dispatcher.set_socks_servers(settings.socks_servers)
            for server in settings.socks_servers:
                server.output_stream = self.dispatcher

        self.add_cell_handler(HTTPRequestPayload, self.on_http_request)
        self.add_cell_handler(HTTPResponsePayload, self.on_http_response)

        if settings.exitnode_cache is not None:
            self.register_task("Load cached exitnodes", self.restore_exitnodes_from_disk, delay=0.5)

        self.register_task('Poll download manager for new or changed downloads', self._poll_download_manager,
                           interval=1.0)

    async def _poll_download_manager(self) -> None:
        """
        Get the latest download states from the download manager.
        """
        # This must run in all circumstances, so catch all exceptions
        try:
            dl_states = self.settings.download_manager.get_last_download_states()
            self.monitor_downloads(dl_states)
        except Exception as e:
            self.logger.exception("Error on polling Download Manager: %s", e)

    def cache_exitnodes_to_disk(self) -> None:
        """
        Write a copy of the exit_candidates to the file self.settings.exitnode_cache.
        """
        exit_nodes = Network()
        for peer in self.get_candidates(PEER_FLAG_EXIT_BT):
            exit_nodes.add_verified_peer(peer)
        snapshot = exit_nodes.snapshot()
        self.logger.info("Writing exit nodes to cache file: %s", str(self.settings.exitnode_cache))
        try:
            self.settings.exitnode_cache.write_bytes(snapshot)
        except OSError as e:
            self.logger.warning("%s: %s", e.__class__.__name__, str(e))

    def restore_exitnodes_from_disk(self) -> None:
        """
        Send introduction requests to peers stored in the file self.settings.exitnode_cache.
        """
        if self.settings.exitnode_cache.is_file():
            self.logger.debug('Loading exit nodes from cache: %s', self.settings.exitnode_cache)
            exit_nodes = Network()
            with self.settings.exitnode_cache.open('rb') as cache:
                exit_nodes.load_snapshot(cache.read())
            for exit_node in exit_nodes.get_walkable_addresses():
                self.endpoint.send(exit_node, self.create_introduction_request(exit_node))
        else:
            self.logger.warning("Could not retrieve backup exitnode cache, file does not exist!")

    def should_join_circuit(self, create_payload: CreatePayload, previous_node_address: Address) -> Future[bool]:
        """
        Check whether we should join a circuit. Returns a future that fires with a boolean.
        """
        joined_circuits = len(self.relay_from_to) + len(self.exit_sockets)
        if self.settings.max_joined_circuits <= joined_circuits:
            self.logger.warning("too many relays (%d)", joined_circuits)
            return succeed(False)
        return succeed(True)

    def readd_bittorrent_peers(self) -> None:
        """
        Add the special IPs that belong to circuits to a download.
        """
        for torrent, peers in list(self.bittorrent_peers.items()):
            infohash = hexlify(torrent.tdef.get_infohash())
            for peer in peers:
                self.logger.info("Re-adding peer %s to torrent %s", peer, infohash)
                torrent.add_peer(peer)
            del self.bittorrent_peers[torrent]

    def update_torrent(self, peers: set[tuple[str, int]], download: Download) -> None:
        """
        Ensure that the given peers are registered in the given download.
        """
        if not download.handle or not download.handle.is_valid():
            return

        peers = peers.intersection({pi.ip for pi in download.handle.get_peer_info()})
        if peers:
            if download not in self.bittorrent_peers:
                self.bittorrent_peers[download] = peers
            else:
                self.bittorrent_peers[download] = peers | self.bittorrent_peers[download]

            # If there are active circuits, add peers immediately. Otherwise postpone.
            if self.find_circuits():
                self.readd_bittorrent_peers()

    def remove_circuit(self, circuit_id: int, additional_info: str = "", remove_now: bool = False,
                       destroy: bool = False) -> Awaitable[None]:
        """
        Remove the circuit that belongs to the given circuit id.
        """
        if circuit_id not in self.circuits:
            self.logger.warning("Circuit %d not found when trying to remove it", circuit_id)
            return succeed(None)

        circuit = self.circuits[circuit_id]

        # Send the notification
        if self.settings.notifier:
            self.settings.notifier.notify(Notification.circuit_removed,
                                          circuit=circuit, additional_info=additional_info)

        affected_peers = self.dispatcher.circuit_dead(circuit)

        # Make sure the circuit is marked as closing, otherwise we may end up reusing it
        circuit.close()

        if self.settings.download_manager:
            for download in self.settings.download_manager.get_downloads():
                self.update_torrent(affected_peers, download)

        # Now we actually remove the circuit
        return super().remove_circuit(circuit_id, additional_info=additional_info,
                                      remove_now=remove_now, destroy=destroy)

    @task
    async def remove_relay(self, circuit_id: int, additional_info: str = "", remove_now: bool = False,
                           destroy: bool =False) -> None:
        """
        Callback for when a relay is removed.
        """
        removed_relay = await super().remove_relay(circuit_id,
                                                   additional_info=additional_info,
                                                   remove_now=remove_now,
                                                   destroy=destroy)

        if self.settings.notifier and removed_relay is not None:
            self.settings.notifier.notify(Notification.circuit_removed, circuit=removed_relay,
                                          additional_info=additional_info)

    def remove_exit_socket(self, circuit_id: int, additional_info:str = "", remove_now: bool = False,
                           destroy: bool = False) -> TunnelExitSocket | None:
        """
        Remove the exit socket that belongs to the given circuit id.
        """
        if circuit_id in self.exit_sockets and self.settings.notifier:
            exit_socket = self.exit_sockets[circuit_id]
            self.settings.notifier.notify(Notification.circuit_removed, circuit=exit_socket,
                                          additional_info=additional_info)

        return super().remove_exit_socket(circuit_id, additional_info=additional_info,
                                          remove_now=remove_now, destroy=destroy)

    def _ours_on_created_extended(self, circuit_id: int, payload: CreatedPayload | ExtendedPayload) -> None:
        """
        Callback for when we receive either a Created or and Extended payload.
        """
        super()._ours_on_created_extended(circuit_id, payload)

        circuit = self.circuits.get(circuit_id)
        if circuit and circuit.state == CIRCUIT_STATE_READY:
            # Re-add BitTorrent peers, if needed.
            self.readd_bittorrent_peers()

    def on_raw_data(self, circuit: Circuit, origin: tuple[str, int], data: bytes) -> None:
        """
        Let our dispatcher know that we have incoming data.
        """
        self.dispatcher.on_incoming_from_tunnel(self, circuit, origin, data)

    def monitor_downloads(self, dslist: list[DownloadState]) -> None:
        """
        Periodically check the Tribler downloads for state changes.
        """
        # Monitor downloads with anonymous flag set, and build rendezvous/introduction points when needed.
        new_states = {}
        hops = {}
        active_downloads_per_hop = {}
        #  Ensure that we stay within the allowed number of circuits for the default hop count.
        default_hops = self.settings.default_hops
        if default_hops > 0:
            active_downloads_per_hop[default_hops] = 0

        for ds in dslist:
            download = ds.get_download()
            # Metainfo downloads are alive for a short period, and don't warrant additional (e2e) circuit creation
            if download.hidden is True:
                continue
            hop_count = download.config.get_hops()
            if hop_count > 0:
                # Convert the real infohash to the infohash used for looking up introduction points
                real_info_hash = download.get_def().get_infohash()
                info_hash = self.get_lookup_info_hash(real_info_hash)
                hops[info_hash] = hop_count
                new_states[info_hash] = ds.get_status()

                active = [DownloadStatus.DOWNLOADING, DownloadStatus.SEEDING, DownloadStatus.METADATA]
                if download.get_state().get_status() in active:
                    active_downloads_per_hop[hop_count] = active_downloads_per_hop.get(hop_count, 0) + 1

                    # Ugly work-around for the libtorrent DHT not making any requests
                    # after a period of having no circuits
                    if self.last_forced_announce.get(real_info_hash, 0) + 60 <= time.time() \
                            and self.find_circuits(hops=hop_count) \
                            and not ds.get_peer_list() \
                            and self.settings.download_manager.has_session(hop_count):
                        download.force_dht_announce()
                        self.last_forced_announce[real_info_hash] = time.time()

        # Request 1 circuit per download while ensuring that the total number of circuits requested per hop count
        # stays within min_circuits and max_circuits.
        self.circuits_needed = {hop_count: min(max(download_count, self.settings.min_circuits),
                                               self.settings.max_circuits)
                                for hop_count, download_count in active_downloads_per_hop.items()}

        self.monitor_hidden_swarms(new_states, hops)
        self.download_states = new_states

    def monitor_hidden_swarms(self, new_states: dict[bytes, DownloadStatus], hops: dict[bytes, int]) -> None:
        """
        Update the known swarms based on the changed states.
        """
        ip_counter = Counter([c.info_hash for c in list(self.circuits.values()) if c.ctype == CIRCUIT_TYPE_IP_SEEDER])
        for info_hash in set(list(new_states) + list(self.download_states)):
            new_state = new_states.get(info_hash)
            old_state = self.download_states.get(info_hash, None)
            state_changed = new_state != old_state

            # Join/leave hidden swarm as needed.
            active = [DownloadStatus.DOWNLOADING, DownloadStatus.SEEDING, DownloadStatus.METADATA]
            if state_changed and new_state in active:
                if old_state != DownloadStatus.METADATA or new_state != DownloadStatus.DOWNLOADING:
                    self.join_swarm(info_hash, hops[info_hash], seeding=new_state == DownloadStatus.SEEDING,
                                    callback=lambda addr, ih=info_hash: self.on_e2e_finished(addr, ih))
            elif state_changed and new_state in [DownloadStatus.STOPPED, None]:
                self.leave_swarm(info_hash)

            # Ensure we have enough introduction points for this infohash. Currently, we only create 1.
            if new_state == DownloadStatus.SEEDING:
                for _ in range(1 - ip_counter.get(info_hash, 0)):
                    self.logger.info("Create introducing circuit for %s", hexlify(info_hash))
                    self.create_introduction_point(info_hash)

    def on_e2e_finished(self, address: Address, info_hash: bytes) -> None:
        """
        Callback for when an end-to-end connection has been established.
        """
        dl = self.get_download(info_hash)
        if dl:
            dl.add_peer(address)
        else:
            self.logger.error("Could not find download for adding hidden services peer %s:%d!", *address)

    def on_rendezvous_established(self, source_address: Address, data: bytes, circuit_id: int) -> None:
        """
        Callback for when a rendezvous node has been established.
        """
        super().on_rendezvous_established(source_address, data, circuit_id)

        circuit = self.circuits.get(circuit_id)
        if circuit and self.settings.download_manager:
            self.update_ip_filter(circuit.info_hash)

    def update_ip_filter(self, info_hash: bytes) -> None:
        """
        Set the IP filter setting for the given infohash.
        """
        download = self.get_download(info_hash)
        if download is not None:
            lt_session = self.settings.download_manager.get_session(download.config.get_hops())
            ip_addresses = [self.circuit_id_to_ip(c.circuit_id)
                            for c in self.find_circuits(ctype=CIRCUIT_TYPE_RP_SEEDER)]
            self.settings.download_manager.update_ip_filter(lt_session, ip_addresses)

    def get_download(self, lookup_info_hash: bytes) -> Download | None:
        """
        Match the given infohash to a download (or None if it cannot be found).
        """
        if not self.settings.download_manager:
            return None

        for download in self.settings.download_manager.get_downloads():
            if lookup_info_hash == self.get_lookup_info_hash(download.get_def().get_infohash()):
                return download
        return None

    @task
    async def create_introduction_point(self, info_hash: bytes, required_ip: Address | None = None) -> None:
        """
        Start creating an introduction point.
        """
        download = self.get_download(info_hash)
        if download and self.settings.socks_servers:
            # We now have to associate the SOCKS5 UDP connection with the libtorrent listen port ourselves.
            # The reason for this is that libtorrent does not include the source IP/port in an SOCKS5 ASSOCIATE message.
            # Starting from libtorrent 1.2.4 on Windows, listen_port() returns 0 if used in combination with a
            # SOCKS5 proxy. Therefore on Windows, we resort to using ports received through listen_succeeded_alert.
            hops = download.config.get_hops()
            lt_listen_interfaces = [k for k in self.settings.download_manager.listen_ports.get(hops)
                                    if k != "127.0.0.1"]
            lt_listen_port = (self.settings.download_manager.listen_ports.get(hops)[lt_listen_interfaces[0]]
                              if lt_listen_interfaces else None)
            lt_listen_port = lt_listen_port or self.settings.download_manager.get_session(hops).listen_port()
            for session in self.settings.socks_servers[hops - 1].sessions:
                connection = session.udp_connection
                if connection and lt_listen_port and connection.remote_udp_address is None:
                    connection.remote_udp_address = ("127.0.0.1", lt_listen_port)
        await super().create_introduction_point(info_hash, required_ip=required_ip)

    async def unload(self) -> None:
        """
        Shut down our dispatcher and cache the known exit nodes.
        """
        await self.dispatcher.shutdown_task_manager()

        if self.settings.exitnode_cache is not None:
            self.cache_exitnodes_to_disk()

        await super().unload()

    def get_lookup_info_hash(self, info_hash: bytes) -> bytes:
        """
        Get the SHA-1 hash to lookup for a given torrent info hash.
        """
        return hashlib.sha1(b"tribler anonymous download" + hexlify(info_hash)).digest()

    @unpack_cell(HTTPRequestPayload)
    async def on_http_request(self, source_address: Address, payload: HTTPRequestPayload,  # noqa: C901
                              circuit_id: int) -> None:
        """
        Callback for when an HTTP request is received.
        """
        if circuit_id not in self.exit_sockets:
            self.logger.warning("Received unexpected http-request")
            return
        if len([cache for cache in self.request_cache._identifiers.values()  # noqa: SLF001
                if isinstance(cache, HTTPRequestCache) and cache.circuit_id == circuit_id]) > 5:
            self.logger.warning("Too many HTTP requests coming from circuit %s")
            return

        self.logger.debug("Got http-request from %s", source_address)

        writer = None
        try:
            async with async_timeout.timeout(10):
                self.logger.debug("Opening TCP connection to %s", payload.target)
                reader, writer = await open_connection(*payload.target)
                writer.write(payload.request)
                response = b""
                while True:
                    line = await reader.readline()
                    response += line
                    if not line.strip():
                        # Read HTTP response body (1MB max)
                        response += await reader.read(1024 ** 2)
                        break
        except OSError:
            self.logger.warning("Tunnel HTTP request failed")
            return
        except AsyncTimeoutError:
            self.logger.warning("Tunnel HTTP request timed out")
            return
        finally:
            if writer:
                writer.close()

        if not response.startswith(b"HTTP/1.1 307"):
            _, _, bencoded_data = response.partition(b'\r\n\r\n')

            if not is_bencoded(bencoded_data):
                self.logger.warning("Tunnel HTTP request not allowed")
                return

        num_cells = math.ceil(len(response) / MAX_HTTP_PACKET_SIZE)
        for i in range(num_cells):
            self.send_cell(source_address,
                           HTTPResponsePayload(circuit_id, payload.identifier, i, num_cells,
                                               response[i * MAX_HTTP_PACKET_SIZE:(i + 1) * MAX_HTTP_PACKET_SIZE]))

    @unpack_cell(HTTPResponsePayload)
    def on_http_response(self, source_address: Address, payload: HTTPResponsePayload, circuit_id: int) -> None:
        """
        Callback for when an HTTP response is received.
        """
        if not self.request_cache.has("http-request", payload.identifier):
            self.logger.warning("Received unexpected http-response")
            return
        cache = self.request_cache.get("http-request", payload.identifier)
        if cache.circuit_id != payload.circuit_id:
            self.logger.warning("Received http-response from wrong circuit %s != %s", cache.circuit_id, circuit_id)
            return

        self.logger.debug("Got http-response from %s", source_address)
        if cache.add_response(payload):
            self.request_cache.pop("http-request", payload.identifier)

    async def perform_http_request(self, destination: Address, request: bytes, hops: int = 1) -> bytes:
        """
        Perform the actual HTTP request to service the given request.
        """
        # We need a circuit that supports HTTP requests, meaning that the circuit will have to end
        # with a node that has the PEER_FLAG_EXIT_HTTP flag set.
        circuit = None
        circuits = self.find_circuits(exit_flags=[PEER_FLAG_EXIT_HTTP])
        if circuits:
            circuit = circuits[0]
        else:
            # Try to create a circuit. Attempt at most 3 times.
            for _ in range(3):
                circuit = self.create_circuit(hops, exit_flags=[PEER_FLAG_EXIT_HTTP])
                if circuit and await circuit.ready:
                    break

        if not circuit or circuit.state != CIRCUIT_STATE_READY:
            msg = "No HTTP circuit available"
            raise RuntimeError(msg)

        cache = self.request_cache.add(HTTPRequestCache(self, circuit.circuit_id))
        self.send_cell(circuit.hop.address, HTTPRequestPayload(circuit.circuit_id, cache.number, destination, request))
        return await cache.response_future

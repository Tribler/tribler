from __future__ import annotations

import asyncio
import hashlib
import time
from binascii import hexlify, unhexlify
from typing import TYPE_CHECKING, cast

import ipv8_rust_tunnels

from ipv8.messaging.anonymization.community import TunnelCommunity, TunnelSettings
from ipv8.peerdiscovery.network import Network

from tribler.core.libtorrent.download_manager.download_state import DownloadState, DownloadStatus
from tribler.core.notifier import Notification, Notifier

if TYPE_CHECKING:
    from pathlib import Path

    from ipv8.messaging.interfaces.udp.endpoint import Address
    from ipv8.messaging.payload import IntroductionResponsePayload, NewIntroductionResponsePayload
    from ipv8.messaging.payload_headers import GlobalTimeDistributionPayload
    from ipv8.peer import Peer
    from ipv8_rust_tunnels import Endpoint as RustEndpoint

    from tribler.core.libtorrent.download_manager.download import Download
    from tribler.core.libtorrent.download_manager.download_manager import DownloadManager

DESTROY_REASON_BALANCE = 65535
PEER_FLAG_EXIT_HTTP = 32768
PEER_FLAG_EXIT_BACKUP = 16384
MAX_HTTP_PACKET_SIZE = 1400


class TriblerTunnelSettings(TunnelSettings):
    """
    Settings for Tribler's tunnel community.
    """

    exitnode_cache: Path | None = None
    notifier: Notifier
    download_manager: DownloadManager
    exitnode_enabled: bool = False
    default_hops: int = 0
    max_intro_points: int = 10


class TriblerTunnelCommunity(TunnelCommunity):
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

        if settings.exitnode_enabled:
            self.settings.peer_flags |= {ipv8_rust_tunnels.PEER_FLAG_EXIT_BT, ipv8_rust_tunnels.PEER_FLAG_EXIT_IPV8, ipv8_rust_tunnels.PEER_FLAG_EXIT_HTTP}

        self.logger.info("Using %s with flags %s", self.endpoint.__class__.__name__, self.settings.peer_flags)

        self.bittorrent_peers: dict[Download, set[tuple[str, int]]] = {}
        self.download_states: dict[bytes, DownloadStatus] = {}
        self.last_forced_announce: dict[bytes, float] = {}

        try:
            self.settings.download_manager.socks_listen_ports = [
                self.engine.create_socks5_server(port, index+1)
                for index, port in enumerate(self.settings.download_manager.socks_listen_ports)
            ]
        except ipv8_rust_tunnels.NotOpenError:
            self.logger.warning("Failed to start SOCKS5 servers")

        loop = asyncio.get_running_loop()
        self.engine.set_circuit_state_callback(
            lambda cid, state: loop.call_soon_threadsafe(self.on_circuit_state_changed, cid, state)
        )

        if settings.exitnode_cache is not None:
            self.register_task("Load cached exitnodes", self.restore_exitnodes_from_disk, delay=0.5)

        self.register_task("Poll download manager for new or changed downloads", self._poll_download_manager,
                           interval=1.0)

    def on_circuit_state_changed(self, circuit_id: int, state: str) -> None:
        self.logger.info(f"Circuit {circuit_id} state changed to {state}"),
        if state == "Ready":
            self.readd_bittorrent_peers()
        elif state == "Closing":
            if self.engine and self.settings.download_manager:
                affected_peers = set(self.engine.get_peers_for_circuit(circuit_id))
                if affected_peers:
                    for download in self.settings.download_manager.get_downloads():
                        self.update_torrent(affected_peers, download)

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
        for peer in self.get_candidates(ipv8_rust_tunnels.PEER_FLAG_EXIT_BT):
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
            self.logger.debug("Loading exit nodes from cache: %s", self.settings.exitnode_cache)
            exit_nodes = Network()
            with self.settings.exitnode_cache.open("rb") as cache:
                exit_nodes.load_snapshot(cache.read())
            for exit_node in exit_nodes.get_walkable_addresses():
                self.endpoint.send(exit_node, self.create_introduction_request(exit_node))
        else:
            self.logger.warning("Could not retrieve backup exitnode cache, file does not exist!")

    def readd_bittorrent_peers(self) -> None:
        """
        Add the special IPs that belong to circuits to a download.
        """
        for torrent, peers in list(self.bittorrent_peers.items()):
            infohash = hexlify(torrent.tdef.infohash)
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
            if self.count_circuits():
                self.readd_bittorrent_peers()

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
                real_info_hash = download.get_def().infohash
                info_hash = self.get_lookup_info_hash(real_info_hash)
                hops[info_hash] = hop_count
                new_states[info_hash] = ds.get_status()

                active = [DownloadStatus.DOWNLOADING, DownloadStatus.SEEDING, DownloadStatus.METADATA]
                if download.get_state().get_status() in active:
                    active_downloads_per_hop[hop_count] = active_downloads_per_hop.get(hop_count, 0) + 1

                    # Ugly work-around for the libtorrent DHT not making any requests
                    # after a period of having no circuits
                    if self.last_forced_announce.get(real_info_hash, 0) + 60 <= time.time() \
                            and self.count_circuits(hops=hop_count) \
                            and not ds.get_peer_list() \
                            and self.settings.download_manager.has_session(hop_count):
                        download.force_dht_announce()
                        self.last_forced_announce[real_info_hash] = time.time()

        self.monitor_hidden_swarms(new_states, hops)
        self.download_states = new_states

    def count_circuits(self, hops=None):
        if self.engine:
            return self.engine.count_circuits(hops=hops)
        return 0

    def monitor_hidden_swarms(self, new_states: dict[bytes, DownloadStatus], hops: dict[bytes, int]) -> None:
        """
        Update the known swarms based on the changed states.
        """
        if (engine := self.engine) is None:
            return None

        intro_points_todo = self.settings.max_intro_points - engine.count_circuits(ctype="IP_SEEDER", state=None)
        active = {DownloadStatus.DOWNLOADING, DownloadStatus.SEEDING, DownloadStatus.METADATA}

        for info_hash in set(new_states) | set(self.download_states):
            new_state = new_states.get(info_hash)
            old_state = self.download_states.get(info_hash)
            state_changed = new_state != old_state

            # Join/leave hidden swarm as needed.
            if state_changed and new_state in active:
                if new_state == DownloadStatus.SEEDING and intro_points_todo <= 0 and not engine.has_intro_point(info_hash):
                    engine.leave_swarm(info_hash)
                elif old_state != DownloadStatus.METADATA or new_state != DownloadStatus.DOWNLOADING:
                    engine.join_swarm(
                        info_hash,
                        hops[info_hash],
                        seeding=(new_state == DownloadStatus.SEEDING),
                    )
            elif state_changed and new_state in {DownloadStatus.STOPPED, None}:
                engine.leave_swarm(info_hash)

            # Ensure we have enough introduction points for this infohash. Currently, we only create 1.
            if new_state == DownloadStatus.SEEDING and intro_points_todo > 0 and not engine.has_intro_point(info_hash):
                self.logger.info("Create introducing circuit for %s", hexlify(info_hash))
                self.create_introduction_point(info_hash)
                intro_points_todo -= 1
                if intro_points_todo <= 0:
                    return

    def on_e2e_finished(self, address: Address, info_hash: bytes) -> None:
        """
        Callback for when an end-to-end connection has been established.
        """
        dl = self.get_download(info_hash)
        if dl:
            dl.add_peer(address)
        else:
            self.logger.error("Could not find download for adding hidden services peer %s:%d!", *address)

    def get_download(self, lookup_info_hash: bytes) -> Download | None:
        """
        Match the given infohash to a download (or None if it cannot be found).
        """
        if not self.settings.download_manager:
            return None

        for download in self.settings.download_manager.get_downloads():
            if lookup_info_hash == self.get_lookup_info_hash(download.get_def().infohash):
                return download
        return None

    def introduction_response_callback(self, peer: Peer, dist: GlobalTimeDistributionPayload,
                                       payload: IntroductionResponsePayload | NewIntroductionResponsePayload) -> None:
        """
        Try to discover peers that are behind a different port.
        """
        if (payload.wan_introduction_address != ("0.0.0.0", 0)
                and payload.lan_introduction_address != ("0.0.0.0", 0)
                and payload.wan_introduction_address[0] != self.my_estimated_wan[0]):
            addr = (payload.wan_introduction_address[0], payload.lan_introduction_address[1])
            self.network.discover_address(peer, addr, self.community_id, payload.intro_supports_new_style)

        return super().introduction_response_callback(peer, dist, payload)

    def create_introduction_point(self, info_hash: bytes) -> None:
        """
        Start creating an introduction point.
        """
        if self.engine and (download := self.get_download(info_hash)):
            # We now have to associate the SOCKS5 UDP connection with the libtorrent listen port ourselves.
            # The reason for this is that libtorrent does not include the source IP/port in an SOCKS5 ASSOCIATE message.
            # Starting from libtorrent 1.2.4 on Windows, listen_port() returns 0 if used in combination with a
            # SOCKS5 proxy. Therefore, on Windows, we resort to using ports received through listen_succeeded_alert.
            hops = download.config.get_hops()
            lt_listen_interfaces = [k for k in self.settings.download_manager.listen_ports.get(hops)
                                    if k != "127.0.0.1"]
            lt_listen_port = (self.settings.download_manager.listen_ports.get(hops)[lt_listen_interfaces[0]]
                              if lt_listen_interfaces else None)
            lt_listen_port = lt_listen_port or self.settings.download_manager.get_session(hops).listen_port()
            self.engine.set_udp_associate_default_remote(("127.0.0.1", lt_listen_port), hops)
            self.engine.create_introduction_point(info_hash)

    async def unload(self) -> None:
        """
        Cache known exit nodes.
        """
        if self.settings.exitnode_cache is not None:
            self.cache_exitnodes_to_disk()

        await super().unload()

    def get_lookup_info_hash(self, info_hash: bytes) -> bytes:
        """
        Get the SHA-1 hash to lookup for a given torrent info hash.
        """
        return hashlib.sha1(b"tribler anonymous download" + hexlify(info_hash)).digest()

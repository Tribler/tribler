from __future__ import annotations

from asyncio import sleep
from typing import TYPE_CHECKING, cast
from unittest.mock import Mock

import libtorrent
from ipv8.community import CommunitySettings
from ipv8.keyvault.crypto import default_eccrypto
from ipv8.messaging.anonymization.tunnel import PEER_FLAG_EXIT_BT
from ipv8.peer import Peer
from ipv8.test.base import TestBase
from ipv8.test.messaging.anonymization.mock import MockDHTProvider
from ipv8.test.mocking.ipv8 import MockIPv8

from tribler.core.libtorrent.download_manager.download_config import DownloadConfig
from tribler.core.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.libtorrent.download_manager.download_state import DownloadStatus
from tribler.core.libtorrent.torrentdef import TorrentDef, TorrentDefNoMetainfo
from tribler.core.libtorrent.torrents import create_torrent_file
from tribler.core.notifier import Notifier
from tribler.core.socks5.server import Socks5Server
from tribler.core.tunnel.community import TriblerTunnelCommunity, TriblerTunnelSettings
from tribler.test_unit.mocks import MockTriblerConfigManager

if TYPE_CHECKING:
    from tribler.core.libtorrent.download_manager.download import Download

DOWNLOADER = 0  # Node 0 tries to download through the tunnels.
RELAY = 1  # Node 1 acts as a tunnel relay.
EXIT = 2  # Node 2 acts as an exit node.


class GlobalTestSettings(CommunitySettings):
    """
    Keep track of a global node identifier.
    """

    node_id: int = 0


class MockDownloadManager(DownloadManager):
    """
    Mocked manager that always allows shutdown (regardless of the libtorrent state).
    """

    def is_shutdown_ready(self) -> bool:
        """
        Always ready.
        """
        return True


class TestAnonymousDownload(TestBase[TriblerTunnelCommunity]):
    """
    An integration test for anonymous downloads.
    """

    MAX_TEST_TIME = 30

    def setUp(self) -> None:
        """
        Create the necessary tunnel communities.
        """
        super().setUp()

        downloader_config = MockTriblerConfigManager()
        downloader_config.set("libtorrent/dht", False)
        self.download_manager_downloader = MockDownloadManager(downloader_config, Notifier())

        seeder_config = MockTriblerConfigManager()
        seeder_config.set("libtorrent/dht", False)
        seeder_config.set("libtorrent/upnp", False)
        seeder_config.set("libtorrent/natpmp", False)
        seeder_config.set("libtorrent/lsd", False)
        self.download_manager_seeder = MockDownloadManager(seeder_config, Notifier())

        self.socks_servers: list[Socks5Server] = [Socks5Server(hops+1) for hops in range(3)]

        self.initialize(TriblerTunnelCommunity, 3, GlobalTestSettings())

    async def tearDown(self) -> None:
        """
        Tear down all communities and the download managers.
        """
        await self.download_manager_downloader.shutdown()
        await self.download_manager_seeder.shutdown()
        await super().tearDown()

    def create_node(self, settings: CommunitySettings | None = None, create_dht: bool = False,
                    enable_statistics: bool = False) -> MockIPv8:
        """
        Create a downloader, relay, or exit node.

        The seeder does not have an overlay!
        """
        global_settings = cast(GlobalTestSettings, settings)
        my_node_id = global_settings.node_id
        global_settings.node_id += 1
        node_peer = Peer(default_eccrypto.generate_key("curve25519"))

        tunnel_settings = TriblerTunnelSettings(remove_tunnel_delay=0, socks_servers=[], download_manager=None,
                                                notifier=Notifier())

        if my_node_id == DOWNLOADER:
            self.download_manager_downloader.peer_mid = node_peer.mid
            tunnel_settings.download_manager = self.download_manager_downloader
            tunnel_settings.notifier = self.download_manager_downloader.notifier
        elif my_node_id == RELAY:
            tunnel_settings.download_manager = MockDownloadManager(MockTriblerConfigManager(), tunnel_settings.notifier)
            tunnel_settings.download_manager.checkpoint_directory = Mock()
        elif my_node_id == EXIT:
            tunnel_settings.exitnode_enabled = True
            tunnel_settings.peer_flags = {PEER_FLAG_EXIT_BT}
            tunnel_settings.download_manager = MockDownloadManager(MockTriblerConfigManager(), tunnel_settings.notifier)
            tunnel_settings.download_manager.checkpoint_directory = Mock()

        out = MockIPv8(node_peer, TriblerTunnelCommunity, tunnel_settings)
        out.overlay.dht_provider = MockDHTProvider(node_peer)
        out.overlay.settings.remove_tunnel_delay = 0

        return out

    async def start_socks_servers(self) -> None:
        """
        Start the socks servers.
        """
        ports = []
        for server in self.socks_servers:
            await server.start()
            ports.append(server.port)
        self.download_manager_downloader.config.set("libtorrent/socks_listen_ports", ports)
        self.download_manager_downloader.socks_listen_ports = ports

        self.overlay(0).dispatcher.set_socks_servers(self.socks_servers)
        for server in self.socks_servers:
            server.output_stream = self.overlay(0).dispatcher

    async def add_mock_download_config(self, manager: DownloadManager, hops: int) -> DownloadConfig:
        """
        Create a mocked DownloadConfig.
        """
        dest_dir = self.temporary_directory()
        defaults = MockTriblerConfigManager()
        defaults.set("libtorrent/download_defaults/saveas", dest_dir)
        defaults.set("state_dir", dest_dir)
        config = DownloadConfig.from_defaults(defaults)
        config.set_hops(hops)

        manager.state_dir = config.get_dest_dir()
        manager.metadata_tmpdir = Mock(name=config.get_dest_dir())
        manager.checkpoint_directory = config.get_dest_dir()
        manager.peer_mid = b"0000"
        await manager.initialize()
        manager.start()
        await sleep(0)

        return config

    async def start_seeding(self) -> bytes:
        """
        Create a file and start the seeding.
        """
        config = await self.add_mock_download_config(self.download_manager_seeder, 0)
        config.set_safe_seeding(False)

        with open(config.get_dest_dir() / "ubuntu-15.04-desktop-amd64.iso", "wb") as f:  # noqa: ASYNC230
            f.write(bytes([1] * 524288))

        metainfo = create_torrent_file([config.get_dest_dir() / "ubuntu-15.04-desktop-amd64.iso"], {})["metainfo"]
        tdef = TorrentDef(metainfo=libtorrent.bdecode(metainfo))

        download = await self.download_manager_seeder.start_download(tdef=tdef, config=config)
        await download.wait_for_status(DownloadStatus.SEEDING)

        return tdef.infohash

    async def start_anon_download(self, infohash: bytes) -> Download:
        """
        Start an anonymous download in the main Tribler session.
        """
        config = await self.add_mock_download_config(self.download_manager_downloader, 2)

        download = await self.download_manager_downloader.start_download(tdef=TorrentDefNoMetainfo(infohash, b"test"),
                                                                         config=config)

        while not self.download_manager_seeder.listen_ports[0]:
            await sleep(0.1)

        self.overlay(DOWNLOADER).bittorrent_peers[download] = {
            ("127.0.0.1", self.download_manager_seeder.listen_ports[0]["127.0.0.1"])
        }

        return download

    async def test_anon_download(self) -> None:
        """
        Test a plain anonymous download with an exit node.
        """
        await self.start_socks_servers()
        await self.introduce_nodes()
        infohash = await self.start_seeding()

        download = await self.start_anon_download(infohash)

        await download.wait_for_status(DownloadStatus.SEEDING)

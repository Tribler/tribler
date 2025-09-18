from __future__ import annotations

from abc import ABCMeta
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar, cast

from ipv8.bootstrapping.dispersy.bootstrapper import DispersyBootstrapper
from ipv8.community import Community
from ipv8.configuration import DISPERSY_BOOTSTRAPPER
from ipv8.loader import CommunityLauncher, after, kwargs, overlay, precondition, set_in_session, walk_strategy
from ipv8.overlay import Overlay, SettingsClass
from ipv8.peerdiscovery.discovery import DiscoveryStrategy, RandomWalk

if TYPE_CHECKING:
    from collections.abc import Callable

    from ipv8.bootstrapping.bootstrapper_interface import Bootstrapper
    from ipv8.dht.discovery import DHTDiscoveryCommunity
    from ipv8.keyvault.keys import PrivateKey
    from ipv8.peer import Peer
    from ipv8.REST.dht_endpoint import DHTEndpoint
    from ipv8.REST.root_endpoint import RootEndpoint as IPv8RootEndpoint
    from ipv8.REST.tunnel_endpoint import TunnelEndpoint
    from ipv8_service import IPv8

    from tribler.core.content_discovery.community import ContentDiscoveryCommunity
    from tribler.core.content_discovery.restapi.search_endpoint import SearchEndpoint
    from tribler.core.database.restapi.database_endpoint import DatabaseEndpoint
    from tribler.core.database.store import MetadataStore
    from tribler.core.libtorrent.restapi.downloads_endpoint import DownloadsEndpoint
    from tribler.core.recommender.community import RecommenderCommunity
    from tribler.core.recommender.restapi.endpoint import RecommenderEndpoint
    from tribler.core.rendezvous.community import RendezvousCommunity
    from tribler.core.restapi.rest_endpoint import RESTEndpoint
    from tribler.core.restapi.statistics_endpoint import StatisticsEndpoint
    from tribler.core.rss.restapi.endpoint import RSSEndpoint
    from tribler.core.session import Session
    from tribler.core.torrent_checker.torrent_checker import TorrentChecker
    from tribler.core.tunnel.community import TriblerTunnelCommunity
    from tribler.core.versioning.restapi.versioning_endpoint import VersioningEndpoint

# We actually want lazy imports inside the components:
# ruff: noqa: PLC0415

CommunityT = TypeVar("CommunityT", bound=Community)


class CommunityLauncherWEndpoints(CommunityLauncher["Session", CommunityT], metaclass=ABCMeta):
    """
    A CommunityLauncher that can supply endpoints.
    """

    def get_endpoints(self) -> list[RESTEndpoint]:
        """
        Get a list of endpoints that should be loaded.
        """
        return []


class BaseLauncher(CommunityLauncherWEndpoints[CommunityT], metaclass=ABCMeta):
    """
    The base class for all Tribler Community launchers.
    """

    def get_bootstrappers(self, session: Session) -> list[tuple[type[Bootstrapper], dict]]:
        """
        Simply use the old Dispersy bootstrapper format.
        """
        return [(DispersyBootstrapper, DISPERSY_BOOTSTRAPPER["init"])]

    def get_walk_strategies(self) -> list[tuple[type[DiscoveryStrategy], dict, int]]:
        """
        Adhere to the default walking behavior.
        """
        return [(RandomWalk, {}, 20)]

    def get_my_peer(self, ipv8: IPv8, session: Session) -> Peer:
        """
        Get the default key.
        """
        return ipv8.keys["anonymous id"]


class Component(Community):
    """
    A glorified TaskManager. This should also really be a TaskManager.

    I did not make this a TaskManager because I am lazy - Quinten (2024)
    """

    def __init__(self, settings: SettingsClass) -> None:
        """
        Create a new inert fake Community.
        """
        settings.community_id = self.__class__.__name__.encode()
        Overlay.__init__(self, settings)
        self.cancel_pending_task("discover_lan_addresses")
        self.endpoint.remove_listener(self)
        self.bootstrappers: list[Bootstrapper] = []
        self.max_peers = 0
        self._prefix = settings.community_id
        self.settings = settings


class ComponentLauncher(CommunityLauncherWEndpoints[Component]):
    """
    A launcher for components that simply need a TaskManager, not a full Community.
    """

    def get_overlay_class(self) -> type[Component]:
        """
        Create a fake Community.
        """
        return cast("type[Component]", type(f"{self.__class__.__name__}", (Component,), {}))

    def get_my_peer(self, ipv8: IPv8, session: Session) -> Peer:
        """
        Our peer still uses the Tribler default key.
        """
        return ipv8.keys["anonymous id"]


@set_in_session("content_discovery_community")
@after("DatabaseComponent")
@precondition('session.config.get("database/enabled")')
@precondition('session.config.get("torrent_checker/enabled")')
@precondition('session.config.get("content_discovery_community/enabled")')
@overlay("tribler.core.content_discovery.community", "ContentDiscoveryCommunity")
@kwargs(metadata_store="session.mds", torrent_checker="session.torrent_checker", notifier="session.notifier")
class ContentDiscoveryComponent(BaseLauncher["ContentDiscoveryCommunity"]):
    """
    Launch instructions for the content discovery community.
    """

    def finalize(self, ipv8: IPv8, session: Session, community: ContentDiscoveryCommunity) -> None:
        """
        When we are done launching, register our REST API.
        """
        cast("SearchEndpoint",
             session.rest_manager.get_endpoint("/api/search")).content_discovery_community = community
        cast("StatisticsEndpoint",
             session.rest_manager.get_endpoint("/api/statistics")).content_discovery_community = community

    def get_endpoints(self) -> list[RESTEndpoint]:
        """
        Add the search endpoint.
        """
        from tribler.core.content_discovery.restapi.search_endpoint import SearchEndpoint

        return [*super().get_endpoints(), SearchEndpoint()]


@precondition('session.config.get("database/enabled")')
class DatabaseComponent(ComponentLauncher):
    """
    Launch instructions for the database.
    """

    def prepare(self, ipv8: IPv8, session: Session) -> None:
        """
        Create the database instances we need for Tribler.
        """
        from tribler.core.database.store import MetadataStore
        from tribler.core.notifier import Notification

        mds_path = str(Path(session.config.get_version_state_dir()) / "sqlite" / "metadata.db")
        if session.config.get("memory_db"):
            mds_path = ":memory:"

        session.mds = MetadataStore(
            mds_path,
            cast("PrivateKey", session.ipv8.keys["anonymous id"].key),
            notifier=session.notifier,
            disable_sync=False
        )
        session.notifier.add(Notification.torrent_metadata_added,
                             cast("Callable[[dict], None]", session.mds.TorrentMetadata.add_ffa_from_dict))

    def finalize(self, ipv8: IPv8, session: Session, community: Component) -> None:
        """
        When we are done launching, register our REST API.
        """
        cast("StatisticsEndpoint", session.rest_manager.get_endpoint("/api/statistics")).session = session

        db_endpoint = cast("DatabaseEndpoint", session.rest_manager.get_endpoint("/api/metadata"))
        db_endpoint.download_manager = session.download_manager
        db_endpoint.mds = session.mds

    def get_endpoints(self) -> list[RESTEndpoint]:
        """
        Add the database endpoint.
        """
        from tribler.core.database.restapi.database_endpoint import DatabaseEndpoint

        return [*super().get_endpoints(), DatabaseEndpoint()]


@after("DatabaseComponent")
@precondition('session.config.get("rendezvous/enabled")')
@overlay("tribler.core.rendezvous.community", "RendezvousCommunity")
class RendezvousComponent(BaseLauncher["RendezvousCommunity"]):
    """
    Launch instructions for the rendezvous community.
    """

    def get_kwargs(self, session: Session) -> dict:
        """
        Create and forward the rendezvous database for the Community.
        """
        from tribler.core.rendezvous.database import RendezvousDatabase

        out = super().get_kwargs(session)
        out["database"] = (RendezvousDatabase(db_path=Path(session.config.get_version_state_dir()) / "sqlite"
                           / "rendezvous.db"))

        return out

    def finalize(self, ipv8: IPv8, session: Session, community: RendezvousCommunity) -> None:
        """
        Start listening to peer connections after starting.
        """
        from tribler.core.rendezvous.rendezvous_hook import RendezvousHook

        rendezvous_hook = RendezvousHook(community.composition.database, community)
        ipv8.network.add_peer_observer(rendezvous_hook)


@after("DatabaseComponent")
@precondition('session.config.get("torrent_checker/enabled")')
@precondition('session.config.get("database/enabled")')
class TorrentCheckerComponent(ComponentLauncher):
    """
    Launch instructions for the torrent checker.
    """

    def prepare(self, overlay_provider: IPv8, session: Session) -> None:
        """
        Initialize the torrecht checker and the torrent manager.
        """
        from tribler.core.torrent_checker.torrent_checker import TorrentChecker
        from tribler.core.torrent_checker.tracker_manager import TrackerManager

        metadata_store = cast("MetadataStore", session.mds)  # Guaranteed by DatabaseComponent

        tracker_manager = TrackerManager(state_dir=Path(session.config.get_version_state_dir()),
                                         metadata_store=metadata_store)
        torrent_checker = TorrentChecker(config=session.config,
                                         download_manager=session.download_manager,
                                         notifier=session.notifier,
                                         tracker_manager=tracker_manager,
                                         metadata_store=metadata_store,
                                         socks_listen_ports=[s.port for s in session.socks_servers
                                                             if s.port is not None])
        session.torrent_checker = torrent_checker

    def finalize(self, ipv8: IPv8, session: Session, community: Component) -> None:
        """
        When we are done launching, register our REST API.
        """
        torrent_checker = cast("TorrentChecker", session.torrent_checker)  # Created and set in prepare()

        community.register_task("Start torrent checker", torrent_checker.initialize)
        cast("DatabaseEndpoint", session.rest_manager.get_endpoint("/api/metadata")).torrent_checker = torrent_checker


@set_in_session("dht_discovery_community")
@precondition('session.config.get("dht_discovery/enabled")')
@overlay("ipv8.dht.discovery", "DHTDiscoveryCommunity")
class DHTDiscoveryComponent(BaseLauncher["DHTDiscoveryCommunity"]):
    """
    Launch instructions for the DHT discovery community.
    """

    def finalize(self, ipv8: IPv8, session: Session, community: DHTDiscoveryCommunity) -> None:
        """
        When we are done launching, register our REST API.
        """
        ipv8_root_ep = cast("IPv8RootEndpoint", session.rest_manager.get_endpoint("/api/ipv8"))
        cast("DHTEndpoint", ipv8_root_ep.endpoints["/dht"]).dht = community


@precondition('session.config.get("recommender/enabled")')
@overlay("tribler.core.recommender.community", "RecommenderCommunity")
class RecommenderComponent(BaseLauncher["RecommenderCommunity"]):
    """
    Launch instructions for the user recommender community.
    """

    def get_kwargs(self, session: Session) -> dict:
        """
        Create and forward the rendezvous database for the Community.
        """
        from tribler.core.recommender.manager import Manager

        db_path = str(Path(session.config.get_version_state_dir()) / "sqlite" / "recommender.db")
        if session.config.get("memory_db"):
            db_path = ":memory:"

        out = super().get_kwargs(session)
        out["manager"] = Manager(db_path)

        return out

    def finalize(self, ipv8: IPv8, session: Session, community: RecommenderCommunity) -> None:
        """
        When we are done launching, register our REST API.
        """
        endpoint = cast("RecommenderEndpoint", session.rest_manager.get_endpoint("/api/recommender"))
        endpoint.manager = community.manager

    def get_endpoints(self) -> list[RESTEndpoint]:
        """
        Add the knowledge endpoint.
        """
        from tribler.core.recommender.restapi.endpoint import RecommenderEndpoint

        return [*super().get_endpoints(), RecommenderEndpoint()]


@precondition('session.config.get("rss/enabled")')
class RSSComponent(ComponentLauncher):
    """
    Launch instructions for the RSS component.
    """

    def finalize(self, ipv8: IPv8, session: Session, community: Component) -> None:
        """
        When we are done launching, register our REST API.
        """
        from tribler.core.rss.rss import RSSWatcherManager

        manager = RSSWatcherManager(community, session.notifier, session.config.get("rss/urls"))
        manager.start()

        endpoint = cast("RSSEndpoint", session.rest_manager.get_endpoint("/api/rss"))
        endpoint.manager = manager
        endpoint.config = session.config

    def get_endpoints(self) -> list[RESTEndpoint]:
        """
        Add the RSS endpoint.
        """
        from tribler.core.rss.restapi.endpoint import RSSEndpoint

        return [*super().get_endpoints(), RSSEndpoint()]


@set_in_session("tunnel_community")
@precondition('session.config.get("tunnel_community/enabled")')
@after("DHTDiscoveryComponent")
@walk_strategy("tribler.core.tunnel.discovery", "GoldenRatioStrategy", -1)
@overlay("tribler.core.tunnel.community", "TriblerTunnelCommunity")
class TunnelComponent(BaseLauncher["TriblerTunnelCommunity"]):
    """
    Launch instructions for the tunnel community.
    """

    def get_kwargs(self, session: Session) -> dict:
        """
        Extend our community arguments with all necessary config settings and objects.
        """
        from ipv8.dht.discovery import DHTDiscoveryCommunity
        from ipv8.dht.provider import DHTCommunityProvider

        community = cast("DHTDiscoveryCommunity", session.ipv8.get_overlay(DHTDiscoveryCommunity))

        out = super().get_kwargs(session)
        out["exitnode_cache"] =  Path(session.config.get_version_state_dir()) / "exitnode_cache.dat"
        out["notifier"] = session.notifier
        out["download_manager"] = session.download_manager
        out["socks_servers"] = session.socks_servers
        out["min_circuits"] = session.config.get("tunnel_community/min_circuits")
        out["max_circuits"] = session.config.get("tunnel_community/max_circuits")
        out["default_hops"] = session.config.get("libtorrent/download_defaults/number_hops")
        out["dht_provider"] = (DHTCommunityProvider(community, 0) # 0 is unused, requires changes in IPv8.
                               if session.ipv8.get_overlay(DHTDiscoveryCommunity) else None)
        return out

    def finalize(self, ipv8: IPv8, session: Session, community: TriblerTunnelCommunity) -> None:
        """
        When we are done launching, register our REST API.
        """
        cast("DownloadsEndpoint", session.rest_manager.get_endpoint("/api/downloads")).tunnel_community = community
        ipv8_root_ep = cast("IPv8RootEndpoint", session.rest_manager.get_endpoint("/api/ipv8"))
        cast("TunnelEndpoint", ipv8_root_ep.endpoints["/tunnel"]).tunnels = community


@precondition('session.config.get("versioning/enabled")')
class VersioningComponent(ComponentLauncher):
    """
    Launch instructions for the versioning of Tribler.
    """

    def finalize(self, ipv8: IPv8, session: Session, community: Component) -> None:
        """
        When we are done launching, register our REST API.
        """
        from tribler.core.versioning.manager import VersioningManager

        cast("VersioningEndpoint",
             session.rest_manager.get_endpoint("/api/versioning")).versioning_manager = VersioningManager(
            community, session.config
        )

    def get_endpoints(self) -> list[RESTEndpoint]:
        """
        Add the database endpoint.
        """
        from tribler.core.versioning.restapi.versioning_endpoint import VersioningEndpoint

        return [*super().get_endpoints(), VersioningEndpoint()]


@precondition('session.config.get("watch_folder/enabled")')
class WatchFolderComponent(ComponentLauncher):
    """
    Launch instructions for the watch folder.
    """

    def finalize(self, ipv8: IPv8, session: Session, community: Component) -> None:
        """
        When we are done launching, register our REST API.
        """
        from tribler.core.watch_folder.manager import WatchFolderManager

        manager = WatchFolderManager(session, community)
        manager.start()

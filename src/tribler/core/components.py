from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from ipv8.bootstrapping.dispersy.bootstrapper import DispersyBootstrapper
from ipv8.community import Community
from ipv8.configuration import DISPERSY_BOOTSTRAPPER
from ipv8.loader import CommunityLauncher, after, kwargs, overlay, precondition, set_in_session, walk_strategy
from ipv8.overlay import Overlay, SettingsClass
from ipv8.peerdiscovery.discovery import DiscoveryStrategy, RandomWalk

if TYPE_CHECKING:
    from ipv8.bootstrapping.bootstrapper_interface import Bootstrapper
    from ipv8.peer import Peer
    from ipv8.types import IPv8

    from tribler.core.restapi.rest_endpoint import RESTEndpoint
    from tribler.core.session import Session


class CommunityLauncherWEndpoints(CommunityLauncher):
    """
    A CommunityLauncher that can supply endpoints.
    """

    def get_endpoints(self) -> list[RESTEndpoint]:
        """
        Get a list of endpoints that should be loaded.
        """
        return []


class BaseLauncher(CommunityLauncherWEndpoints):
    """
    The base class for all Tribler Community launchers.
    """

    def get_overlay_class(self) -> type[Community]:
        """
        Overwrite this to return the correct Community type.
        """
        raise NotImplementedError

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


class ComponentLauncher(CommunityLauncherWEndpoints):
    """
    A launcher for components that simply need a TaskManager, not a full Community.
    """

    def get_overlay_class(self) -> type[Community]:
        """
        Create a fake Community.
        """
        return cast(type[Community], type(f"{self.__class__.__name__}", (Component,), {}))

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
class ContentDiscoveryComponent(BaseLauncher):
    """
    Launch instructions for the content discovery community.
    """

    def finalize(self, ipv8: IPv8, session: Session, community: Community) -> None:
        """
        When we are done launching, register our REST API.
        """
        session.rest_manager.get_endpoint("/api/search").content_discovery_community = community

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
            session.ipv8.keys["anonymous id"].key,
            notifier=session.notifier,
            disable_sync=False
        )
        session.notifier.add(Notification.torrent_metadata_added, session.mds.TorrentMetadata.add_ffa_from_dict)

    def finalize(self, ipv8: IPv8, session: Session, community: Community) -> None:
        """
        When we are done launching, register our REST API.
        """
        session.rest_manager.get_endpoint("/api/downloads").mds = session.mds
        session.rest_manager.get_endpoint("/api/statistics").mds = session.mds

        db_endpoint = session.rest_manager.get_endpoint("/api/metadata")
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
class RendezvousComponent(BaseLauncher):
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

    def finalize(self, ipv8: IPv8, session: Session, community: Community) -> None:
        """
        Start listening to peer connections after starting.
        """
        from tribler.core.rendezvous.community import RendezvousCommunity
        from tribler.core.rendezvous.rendezvous_hook import RendezvousHook

        rendezvous_hook = RendezvousHook(cast(RendezvousCommunity, community).composition.database)
        ipv8.network.add_peer_observer(rendezvous_hook)


@precondition('session.config.get("torrent_checker/enabled")')
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

        tracker_manager = TrackerManager(state_dir=Path(session.config.get_version_state_dir()),
                                         metadata_store=session.mds)
        torrent_checker = TorrentChecker(config=session.config,
                                         download_manager=session.download_manager,
                                         notifier=session.notifier,
                                         tracker_manager=tracker_manager,
                                         metadata_store=session.mds,
                                         socks_listen_ports=[s.port for s in session.socks_servers])
        session.torrent_checker = torrent_checker

    def finalize(self, ipv8: IPv8, session: Session, community: Community) -> None:
        """
        When we are done launching, register our REST API.
        """
        community.register_task("Start torrent checker", session.torrent_checker.initialize)
        session.rest_manager.get_endpoint("/api/metadata").torrent_checker = session.torrent_checker


@set_in_session("dht_discovery_community")
@precondition('session.config.get("dht_discovery/enabled")')
@overlay("ipv8.dht.discovery", "DHTDiscoveryCommunity")
class DHTDiscoveryComponent(BaseLauncher):
    """
    Launch instructions for the DHT discovery community.
    """

    def finalize(self, ipv8: IPv8, session: Session, community: Community) -> None:
        """
        When we are done launching, register our REST API.
        """
        session.rest_manager.get_endpoint("/api/ipv8").endpoints["/dht"].dht = community


@precondition('session.config.get("recommender/enabled")')
@overlay("tribler.core.recommender.community", "RecommenderCommunity")
class RecommenderComponent(BaseLauncher):
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

    def finalize(self, ipv8: IPv8, session: Session, community: Community) -> None:
        """
        When we are done launching, register our REST API.
        """
        from tribler.core.recommender.community import RecommenderCommunity

        endpoint = session.rest_manager.get_endpoint("/api/recommender")
        endpoint.manager = cast(RecommenderCommunity, community).manager

    def get_endpoints(self) -> list[RESTEndpoint]:
        """
        Add the knowledge endpoint.
        """
        from tribler.core.recommender.restapi.endpoint import RecommenderEndpoint

        return [*super().get_endpoints(), RecommenderEndpoint()]


@set_in_session("tunnel_community")
@precondition('session.config.get("tunnel_community/enabled")')
@after("DHTDiscoveryComponent")
@walk_strategy("tribler.core.tunnel.discovery", "GoldenRatioStrategy", -1)
@overlay("tribler.core.tunnel.community", "TriblerTunnelCommunity")
class TunnelComponent(BaseLauncher):
    """
    Launch instructions for the tunnel community.
    """

    def get_kwargs(self, session: Session) -> dict:
        """
        Extend our community arguments with all necessary config settings and objects.
        """
        from ipv8.dht.discovery import DHTDiscoveryCommunity
        from ipv8.dht.provider import DHTCommunityProvider

        out = super().get_kwargs(session)
        out["exitnode_cache"] =  Path(session.config.get_version_state_dir()) / "exitnode_cache.dat"
        out["notifier"] = session.notifier
        out["download_manager"] = session.download_manager
        out["socks_servers"] = session.socks_servers
        out["min_circuits"] = session.config.get("tunnel_community/min_circuits")
        out["max_circuits"] = session.config.get("tunnel_community/max_circuits")
        out["default_hops"] = session.config.get("libtorrent/download_defaults/number_hops")
        out["dht_provider"] = (DHTCommunityProvider(session.ipv8.get_overlay(DHTDiscoveryCommunity),
                                                    session.config.get("ipv8/port"))
                               if session.ipv8.get_overlay(DHTDiscoveryCommunity) else None)
        return out

    def finalize(self, ipv8: IPv8, session: Session, community: Community) -> None:
        """
        When we are done launching, register our REST API.
        """
        session.rest_manager.get_endpoint("/api/downloads").tunnel_community = community
        session.rest_manager.get_endpoint("/api/ipv8").endpoints["/tunnel"].tunnels = community


@precondition('session.config.get("versioning/enabled")')
class VersioningComponent(ComponentLauncher):
    """
    Launch instructions for the versioning of Tribler.
    """

    def finalize(self, ipv8: IPv8, session: Session, community: Community) -> None:
        """
        When we are done launching, register our REST API.
        """
        from tribler.core.versioning.manager import VersioningManager

        session.rest_manager.get_endpoint("/api/versioning").versioning_manager = VersioningManager(
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

    def finalize(self, ipv8: IPv8, session: Session, community: Community) -> None:
        """
        When we are done launching, register our REST API.
        """
        from tribler.core.watch_folder.manager import WatchFolderManager

        manager = WatchFolderManager(session, community)
        manager.start()

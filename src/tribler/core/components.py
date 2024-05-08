from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Type, cast

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

    from tribler.core.session import Session


class BaseLauncher(CommunityLauncher):
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


class ComponentLauncher(CommunityLauncher):
    """
    A launcher for components that simply need a TaskManager, not a full Community.
    """

    def get_overlay_class(self) -> type[Community]:
        """
        Create a fake Community.
        """
        return cast(Type[Community], type(f"{self.__class__.__name__}", (Component,), {}))

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
        from tribler.core.content_discovery.community import ContentDiscoveryCommunity
        from tribler.core.content_discovery.restapi.search_endpoint import SearchEndpoint

        session.rest_manager.add_endpoint(SearchEndpoint(cast(ContentDiscoveryCommunity, community)))


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
        from tribler.core.database.tribler_database import TriblerDatabase
        from tribler.core.knowledge.rules.knowledge_rules_processor import KnowledgeRulesProcessor
        from tribler.core.notifier import Notification

        db_path = str(Path(session.config.get("state_dir")) / "sqlite" / "tribler.db")
        mds_path = str(Path(session.config.get("state_dir")) / "sqlite" / "metadata.db")
        if session.config.get("memory_db"):
            db_path = ":memory:"
            mds_path = ":memory:"

        session.db = TriblerDatabase(db_path)
        session.mds = MetadataStore(
            mds_path,
            session.ipv8.keys["anonymous id"].key,
            notifier=session.notifier,
            disable_sync=False,
            tag_processor_version=KnowledgeRulesProcessor.version
        )
        session.notifier.add(Notification.torrent_metadata_added, session.mds.TorrentMetadata.add_ffa_from_dict)

    def finalize(self, ipv8: IPv8, session: Session, community: Community) -> None:
        """
        When we are done launching, register our REST API.
        """
        from tribler.core.database.restapi.database_endpoint import DatabaseEndpoint

        session.rest_manager.get_endpoint("/downloads").mds = session.mds
        session.rest_manager.get_endpoint("/statistics").mds = session.mds
        session.rest_manager.add_endpoint(DatabaseEndpoint(session.download_manager,
                                                           torrent_checker=None,
                                                           metadata_store=session.mds,
                                                           tribler_db=session.db))


@set_in_session("knowledge_community")
@after("DatabaseComponent")
@precondition('session.config.get("database/enabled")')
@precondition('session.config.get("knowledge_community/enabled")')
@overlay("tribler.core.knowledge.community", "KnowledgeCommunity")
@kwargs(db="session.db", key='session.ipv8.keys["secondary"].key')
class KnowledgeComponent(CommunityLauncher):
    """
    Launch instructions for the knowledge community.
    """

    def finalize(self, ipv8: IPv8, session: Session, community: Community) -> None:
        """
        When we are done launching, register our REST API.
        """
        from tribler.core.knowledge.community import KnowledgeCommunity
        from tribler.core.knowledge.restapi.knowledge_endpoint import KnowledgeEndpoint
        from tribler.core.knowledge.rules.knowledge_rules_processor import KnowledgeRulesProcessor

        session.knowledge_processor = KnowledgeRulesProcessor(
            notifier=session.notifier,
            db=session.db,
            mds=session.mds,
        )
        session.knowledge_processor.start()
        session.rest_manager.get_endpoint("/metadata").tag_rules_processor = session.knowledge_processor
        session.rest_manager.add_endpoint(KnowledgeEndpoint(session.db, cast(KnowledgeCommunity, community)))


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
        out["database"] = RendezvousDatabase(db_path=Path(session.config.get("state_dir")) / "sqlite" / "rendezvous.db")

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

        tracker_manager = TrackerManager(state_dir=session.config.get("state_dir"), metadata_store=session.mds)
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
        session.rest_manager.get_endpoint("/metadata").torrent_checker = session.torrent_checker


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
        session.rest_manager.get_endpoint("/ipv8").endpoints["/dht"].dht = community


@set_in_session("tunnel_community")
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
        out["exitnode_cache"] =  Path(session.config.get("state_dir")) / "exitnode_cache.dat"
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
        session.rest_manager.get_endpoint("/downloads").tunnel_community = community
        session.rest_manager.get_endpoint("/ipv8").endpoints["/tunnel"].tunnels = community


@after("ContentDiscoveryComponent", "TorrentCheckerComponent")
@precondition('session.config.get("user_activity/enabled")')
class UserActivityComponent(ComponentLauncher):
    """
    Launch instructions for the user activity community.
    """

    def finalize(self, ipv8: IPv8, session: Session, community: Community) -> None:
        """
        When we are done launching, start listening for GUI events.
        """
        from tribler.core.user_activity.manager import UserActivityManager

        component = cast(Component, community)
        max_query_history = session.config.get("user_activity/max_query_history")
        component.settings.manager = UserActivityManager(component, session, max_query_history)

"""
Note: after making changes to this file, run it to generate the `pyi` types!
"""
from __future__ import annotations

import json
import logging
import os
from importlib.metadata import PackageNotFoundError, version
from json import JSONDecodeError
from pathlib import Path
from typing import NotRequired, TypedDict

from ipv8.configuration import default as ipv8_default_config

from tribler.upgrade_script import TO

logger = logging.getLogger(__name__)


class IPv8InterfaceConfig(TypedDict):
    """
    An IPv8 network interface.
    """

    interface: str
    ip: str
    port: int
    worker_threads: NotRequired[int]


class IPv8KeysConfig(TypedDict):
    """
    An IPv8 key configuration.
    """

    alias: str
    generation: str
    file: str


class IPv8LoggerConfig(TypedDict):
    """
    The IPv8 logger configuration.
    """

    level: str


class IPv8WalkerConfig(TypedDict):
    """
    An IPv8 walker configuration.
    """

    strategy: str
    peers: int
    init: dict


IPv8BootstrapperConfig = TypedDict("IPv8BootstrapperConfig", {
    "class": str,
    "init": dict
})
"""
An IPv8 bootstrapper configuration.
"""


IPv8OverlayConfig = TypedDict("IPv8OverlayConfig", {
    "class": str,
    "key": str,
    "walkers": list[IPv8WalkerConfig],
    "bootstrappers": list[IPv8BootstrapperConfig],
    "initialize": dict,
    "on_start": list
})
"""
An IPv8 overlay launch config.
"""


class IPv8Config(TypedDict):
    """
    The main IPv8 configuration dictionary.
    """

    interfaces: list[IPv8InterfaceConfig]
    keys: list[IPv8KeysConfig]
    logger: IPv8LoggerConfig
    working_directory: str
    walker_interval: float
    overlays: list[IPv8OverlayConfig]


class ApiConfig(TypedDict):
    """
    Settings for the API key component.
    """

    key: str
    http_enabled: bool
    http_port: int
    http_host: str
    https_enabled: bool
    https_host: str
    https_port: int
    https_certfile: str
    http_port_running: int
    https_port_running: int


class ContentDiscoveryCommunityConfig(TypedDict):
    """
    Settings for the content discovery component.
    """

    enabled: bool


class DHTDiscoveryCommunityConfig(TypedDict):
    """
    Settings for the DHT discovery component.
    """

    enabled: bool


class DatabaseConfig(TypedDict):
    """
    Settings for the database component.
    """

    enabled: bool


class VersioningConfig(TypedDict):
    """
    Settings for the versioning component.
    """

    enabled: bool
    allow_pre: bool


class DownloadDefaultsConfig(TypedDict):
    """
    Settings for default downloads, used by libtorrent.
    """

    anonymity_enabled: bool
    number_hops: int
    safeseeding_enabled: bool
    saveas: str
    seeding_mode: str
    seeding_ratio: float
    seeding_time: float
    channel_download: bool
    add_download_to_channel: bool
    trackers_file: str
    torrent_folder: str
    auto_managed: bool
    completed_dir: str


class LibtorrentConfig(TypedDict):
    """
    Settings for the libtorrent component.
    """

    socks_listen_ports: list[int]
    listen_interface: str
    port: int
    proxy_type: int
    proxy_server: str
    proxy_auth: str
    max_connections_download: int
    max_download_rate: int
    max_upload_rate: int
    utp: bool
    dht: bool
    dht_readiness_timeout: int
    upnp: bool
    natpmp: bool
    lsd: bool
    announce_to_all_tiers: bool
    announce_to_all_trackers: bool
    max_concurrent_http_announces: int
    check_after_complete: bool

    download_defaults: DownloadDefaultsConfig

    active_downloads: int
    active_seeds: int
    active_checking: int
    active_dht_limit: int
    active_tracker_limit: int
    active_lsd_limit: int
    active_limit: int

    ask_download_settings: bool
    clear_orphaned_parts: bool


class RecommenderConfig(TypedDict):
    """
    Settings for the user recommender component.
    """

    enabled: bool


class RendezvousConfig(TypedDict):
    """
    Settings for the rendezvous component.
    """

    enabled: bool


class RSSConfig(TypedDict):
    """
    Settings for the rss component.
    """

    enabled: bool
    urls: list[str]


class TorrentCheckerConfig(TypedDict):
    """
    Settings for the torrent checker component.
    """

    enabled: bool


class TunnelCommunityConfig(TypedDict):
    """
    Settings for the tunnel community component.
    """

    enabled: bool
    min_circuits: int
    max_circuits: int


class WatchFolderConfig(TypedDict):
    """
    Settings for the watch folder component.
    """

    enabled: bool
    directory: str
    check_interval: float


class TriblerConfig(TypedDict):
    """
    The main Tribler settings and all of its components' sub-settings.
    """

    api: ApiConfig
    headless: bool
    start_minimized: bool

    ipv8: IPv8Config
    statistics: bool

    content_discovery_community: ContentDiscoveryCommunityConfig
    database: DatabaseConfig
    libtorrent: LibtorrentConfig
    recommender: RecommenderConfig
    rendezvous: RendezvousConfig
    rss: RSSConfig
    torrent_checker: TorrentCheckerConfig
    tunnel_community: TunnelCommunityConfig
    versioning: VersioningConfig
    watch_folder: WatchFolderConfig

    state_dir: str
    memory_db: bool
    tray_icon_color: str
    ui: dict


DEFAULT_CONFIG = {
    "api": {
        "http_enabled": True,
        "http_port": 0,
        "http_host": "127.0.0.1",
        "https_enabled": False,
        "https_host": "127.0.0.1",
        "https_port": 0,
        "https_certfile": "https_certfile",
        # Ports currently in-use. Used by run_tribler.py to detect duplicate sessions.
        "http_port_running": 0,
        "https_port_running": 0,
    },
    "headless": False,
    "start_minimized": False,

    "ipv8": ipv8_default_config,
    "statistics": False,

    "content_discovery_community": ContentDiscoveryCommunityConfig(enabled=True),
    "database": DatabaseConfig(enabled=True),
    "dht_discovery": DHTDiscoveryCommunityConfig(enabled=True),
    "libtorrent": LibtorrentConfig(
        socks_listen_ports=[0, 0, 0, 0, 0],
        listen_interface="0.0.0.0",
        port=0,
        proxy_type=0,
        proxy_server="",
        proxy_auth="",
        max_connections_download=-1,
        max_download_rate=0,
        max_upload_rate=0,
        utp=True,
        dht=True,
        dht_readiness_timeout=30,
        upnp=True,
        natpmp=True,
        lsd=True,
        announce_to_all_tiers=False,
        announce_to_all_trackers=False,
        max_concurrent_http_announces=50,
        check_after_complete=False,
        download_defaults=DownloadDefaultsConfig(
            anonymity_enabled=True,
            number_hops=1,
            safeseeding_enabled=True,
            saveas=str(Path("~/Downloads").expanduser()),
            seeding_mode="forever",
            seeding_ratio=2.0,
            seeding_time=60.0,
            channel_download=False,
            add_download_to_channel=False,
            trackers_file="",
            torrent_folder="",
            auto_managed=False,
            completed_dir=""),
        # active_* defaults are the same as the ones used by libtorrent
        active_downloads=3,
        active_seeds=5,
        active_checking=1,
        active_dht_limit=88,
        active_tracker_limit=1600,
        active_lsd_limit=60,
        active_limit=500,
        ask_download_settings=False,
        clear_orphaned_parts=False
        ),
    "recommender": RecommenderConfig(enabled=True),
    "rendezvous": RendezvousConfig(enabled=True),
    "rss": RSSConfig(enabled=True, urls=[]),
    "torrent_checker": TorrentCheckerConfig(enabled=True),
    "tunnel_community": TunnelCommunityConfig(enabled=True, min_circuits=3, max_circuits=8),
    "versioning": VersioningConfig(enabled=True, allow_pre=False),
    "watch_folder": WatchFolderConfig(enabled=False, directory="", check_interval=10.0),

    "state_dir": str((Path(os.environ.get("APPDATA", "~")) / ".Tribler").expanduser().absolute()),
    "memory_db": False,
    "tray_icon_color": "",
    "ui": {}
}

# Changes to IPv8 default config
DEFAULT_CONFIG["ipv8"]["interfaces"].append({
    "interface": "UDPIPv6",
    "ip": "::",
    "port": 8091
})
DEFAULT_CONFIG["ipv8"]["keys"].append({
    "alias": "secondary",
    "generation": "curve25519",
    "file": "secondary_key.pem"
})
DEFAULT_CONFIG["ipv8"]["overlays"] = [overlay for overlay in DEFAULT_CONFIG["ipv8"]["overlays"]
                                      if overlay["class"] == "DiscoveryCommunity"]
DEFAULT_CONFIG["ipv8"]["working_directory"] = DEFAULT_CONFIG["state_dir"]
for key_entry in DEFAULT_CONFIG["ipv8"]["keys"]:
    if "file" in key_entry:
        key_entry["file"] = str(Path(DEFAULT_CONFIG["state_dir"]) / key_entry["file"])

try:
    version("tribler")
    VERSION_SUBDIR = TO  # We use the latest known version's directory NOT our own version
except PackageNotFoundError:
    VERSION_SUBDIR = "git"


class TriblerConfigManager:
    """
    A class that interacts with a JSON configuration file.
    """

    def __init__(self, config_file: Path = Path("configuration.json")) -> None:
        """
        Load a config from a file.
        """
        super().__init__()
        self.config_file = config_file

        logger.info("Load: %s.", self.config_file)
        self.configuration = TriblerConfig()
        if config_file.exists():
            try:
                with open(self.config_file) as f:
                    self.configuration = json.load(f)
            except JSONDecodeError:
                logger.exception("Failed to load stored configuration. Falling back to defaults!")
        if not self.configuration:
            self.configuration = DEFAULT_CONFIG

    def write(self) -> None:
        """
        Write the configuration to disk.
        """
        with open(self.config_file, "w") as f:
            json.dump(self.configuration, f, indent=4)

    def get(self, option: str) -> dict | list | str | float | bool | None:
        """
        Get a config option based on the path-like descriptor.
        """
        out = self.configuration
        for part in Path(option).parts:
            if part in out:
                out = out.get(part)
            else:
                # Fetch from defaults instead.
                out = DEFAULT_CONFIG
                for df_part in Path(option).parts:
                    out = out.get(df_part)
                break
        return out

    def get_version_state_dir(self) -> str:
        """
        Get the state dir for our current version.
        """
        return os.path.join(self.get("state_dir"), VERSION_SUBDIR)

    def set(self, option: str, value: dict | list | str | float | bool | None) -> None:
        """
        Set a config option value based on the path-like descriptor.
        """
        current = self.configuration
        for part in Path(option).parts[:-1]:
            if part in current:
                current = current[part]
            elif Path(option).parts[0] == "ui":
                # The ui settings are sparse and anonymous, just create a new empty dict when a part is missing.
                current[part] = {}
                current = current[part]
            else:
                # Fetch from defaults instead. Same as ``get()``, but now we inject defaults before overwriting.
                out = DEFAULT_CONFIG
                for df_part in Path(option).parts:
                    out = out.get(df_part)
                    if df_part == part:
                        # We found the missing section, inject the defaults here and continue traversing the dict.
                        if isinstance(out, dict):
                            current[part] = {}
                        else:
                            current[part] = out
                        break
        current[Path(option).parts[-1]] = value

if __name__ == "__main__":
    # Run this file to generate ``tribler_config.pyi`` type stubs.
    import ast
    import inspect
    from typing import get_args

    from mypy.errors import Errors
    from mypy.fastparse import ASTConverter
    from mypy.nodes import FuncDef
    from mypy.options import Options
    from mypy.stubgen import ASTStubGenerator

    def _produce_set_overload(key: str, value_type: str) -> str:
        return f"""    @overload
    def set(self, option: Literal["{key}"], value: {value_type}) -> None: ...
"""

    def _produce_get_overload(key: str, value_type: str) -> str:
        return f"""    @overload
    def get(self, option: Literal["{key}"]) -> {value_type}: ...
"""

    global_keys = {}
    typed_dicts = [("TriblerConfig", "")]
    index = 0
    while index < len(typed_dicts):
        for key, value in locals()[typed_dicts[index][0]].__annotations__.items():
            key_type = value
            if hasattr(value, "_evaluate"):  # It's a ForwardRef!
                key_type = value._evaluate(globals(), locals(), recursive_guard=set())  # noqa: SLF001

            abs_key = typed_dicts[index][1] + ("/" if typed_dicts[index][1] else "") + key
            if getattr(key_type, "__name__", None) == "list" and get_args(key_type):
                key_type, = get_args(key_type)
                global_keys[abs_key] = f"list[{getattr(key_type, '__name__', str(key_type))}]"
            elif getattr(key_type, "__name__", None) == "NotRequired":
                key_type, = get_args(key_type)
            else:
                global_keys[abs_key] = getattr(key_type, "__name__", str(key_type))

            if key_type.__module__ == "__main__":
                typed_dicts.append((getattr(key_type, "__name__", str(key_type)), abs_key))
        index += 1

    set_annotations = inspect.get_annotations(TriblerConfigManager.set)
    get_annotations = inspect.get_annotations(TriblerConfigManager.get)

    typed_dicts_sources = []
    unsourced = {v[0] for v in typed_dicts}
    from linecache import getlines
    with open(__file__) as this_file:
        this_module = ast.parse(this_file.read())
    for entry in this_module.body:
        if (isinstance(entry, ast.Assign) and len(entry.targets) == 1 and isinstance(entry.targets[0], ast.Name)
                and entry.targets[0].id in unsourced):
            typed_dicts_sources.append("".join(getlines(__file__)[entry.lineno-1:entry.end_lineno]))
            unsourced.remove(entry.targets[0].id)
    typed_dicts_sources += [inspect.getsource(globals()[k]) for k in unsourced]
    src_typed_dicts = "\n".join(sorted(typed_dicts_sources))

    mypy_opts = Options()
    ast_tcm = ast.parse(inspect.getsource(TriblerConfigManager))
    conv = ASTConverter(mypy_opts, True, Errors(mypy_opts), strip_function_bodies=True, path="")
    mypy_file = conv.visit(ast_tcm)
    cdef, = mypy_file.defs
    stubgen = ASTStubGenerator([key for key in TriblerConfigManager.__dict__
                                if key not in ["__module__", "__doc__", "get", "set", "__dict__", "__weakref__"]])
    stubgen.indent()
    for fdef in cdef.defs.body:
        if isinstance(fdef, FuncDef) and fdef.name not in ["get", "set"]:
            stubgen.visit_func_def(fdef)

    stub = f"""from pathlib import Path
from typing import Literal, NotRequired, TypedDict, overload

# ruff: noqa: PYI021

VERSION_SUBDIR: str

{src_typed_dicts}

class TriblerConfigManager:

    configuration: TriblerConfig
    config_file: Path

{"".join(l for l in stubgen._output if l.startswith("    def"))}
{"".join(_produce_set_overload(k, v) for k, v in global_keys.items())}
{"".join(_produce_get_overload(k, v) for k, v in global_keys.items())}"""  # noqa: SLF001

    with open("tribler_config.pyi", "w") as stub_file:
        stub_file.write(stub)

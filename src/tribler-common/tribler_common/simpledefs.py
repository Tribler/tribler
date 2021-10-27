"""
Simple definitions.

Author(s): Arno Bakker
"""
from enum import Enum
from uuid import UUID

DLSTATUS_ALLOCATING_DISKSPACE = 0  # TODO: make sure this get set when in this alloc mode
DLSTATUS_WAITING4HASHCHECK = 1
DLSTATUS_HASHCHECKING = 2
DLSTATUS_DOWNLOADING = 3
DLSTATUS_SEEDING = 4
DLSTATUS_STOPPED = 5
DLSTATUS_STOPPED_ON_ERROR = 6
DLSTATUS_METADATA = 7
DLSTATUS_CIRCUITS = 8
DLSTATUS_EXIT_NODES = 9

dlstatus_strings = [
    'DLSTATUS_ALLOCATING_DISKSPACE',
    'DLSTATUS_WAITING4HASHCHECK',
    'DLSTATUS_HASHCHECKING',
    'DLSTATUS_DOWNLOADING',
    'DLSTATUS_SEEDING',
    'DLSTATUS_STOPPED',
    'DLSTATUS_STOPPED_ON_ERROR',
    'DLSTATUS_METADATA',
    'DLSTATUS_CIRCUITS',
    'DLSTATUS_EXIT_NODES',
]

UPLOAD = 'up'
DOWNLOAD = 'down'

STATEDIR_CHECKPOINT_DIR = 'dlcheckpoints'
STATEDIR_CHANNELS_DIR = 'channels'
STATEDIR_DB_DIR = "sqlite"

# Infohashes are always 20 byte binary strings
INFOHASH_LENGTH = 20

# Tribler Core states
STATE_STARTING = "STARTING"
STATE_UPGRADING = "UPGRADING"
STATE_STARTED = "STARTED"
STATE_EXCEPTION = "EXCEPTION"
STATE_SHUTDOWN = "SHUTDOWN"

STATE_START_API = 'Starting HTTP API...'
STATE_UPGRADING_READABLE = 'Upgrading Tribler...'
STATE_LOAD_CHECKPOINTS = 'Loading download checkpoints...'
STATE_CHECKPOINTS_LOADED = 'Checkpoints load finished...'
STATE_START_LIBTORRENT = 'Starting libtorrent...'
STATE_START_TORRENT_CHECKER = 'Starting torrent checker...'
STATE_START_API_ENDPOINTS = 'Starting API endpoints...'
STATE_START_WATCH_FOLDER = 'Starting watch folder...'
STATE_START_RESOURCE_MONITOR = 'Starting resource monitor...'


# This UUID is used to push new channels through the events endpoint. GigaChannel Community
# sends updates over the Events endpoints with this UUID when new toplevel channels discovered.
CHANNELS_VIEW_UUID = UUID('094e5bb7-d6b4-4662-825a-4a8c5948ea56')


class NTFY(Enum):
    TORRENT_FINISHED = "torrent_finished"
    TRIBLER_SHUTDOWN_STATE = "tribler_shutdown_state"
    TRIBLER_STARTED = "tribler_started"
    TRIBLER_NEW_VERSION = "tribler_new_version"
    CHANNEL_DISCOVERED = "channel_discovered"
    REMOTE_QUERY_RESULTS = "remote_query_results"
    TUNNEL_REMOVE = "tunnel_remove"
    WATCH_FOLDER_CORRUPT_FILE = "watch_folder_corrupt_file"
    UPGRADER_TICK = "upgrader_tick"
    UPGRADER_STARTED = "upgrader_started"
    UPGRADER_DONE = "upgrader_done"
    CHANNEL_ENTITY_UPDATED = "channel_entity_updated"
    LOW_SPACE = "low_space"
    EVENTS_START = "events_start"
    TRIBLER_EXCEPTION = "tribler_exception"
    POPULARITY_COMMUNITY_ADD_UNKNOWN_TORRENT = "PopularityCommunity:added_unknown_torrent"
    REPORT_CONFIG_ERROR = "report_config_error"
    PEER_DISCONNECTED_EVENT = "peer_disconnected"
    TRIBLER_TORRENT_PEER_UPDATE = "tribler_torrent_peer_update"
    TORRENT_METADATA_ADDED = "torrent_metadata_added"


class CHANNEL_STATE(Enum):
    PERSONAL = "Personal"
    LEGACY = "Legacy"
    COMPLETE = "Complete"
    UPDATING = "Updating"
    DOWNLOADING = "Downloading"
    PREVIEW = "Preview"
    METAINFO_LOOKUP = "Searching for metainfo"


# Max download or upload rate limit for libtorrent.
# On Win64, the compiled version of libtorrent only supported 2^31 - 1
# as rate limit values instead of sys.maxsize or 2^63 -1. Since 2^31
# is a sufficiently large value for download/upload rate limit,
# here we set the max values for these parameters.
MAX_LIBTORRENT_RATE_LIMIT = 2 ** 31 - 1  # bytes per second

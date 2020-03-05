"""
This file contains various definitions used by the Tribler GUI.
"""
DEFAULT_API_PROTOCOL = "http"
DEFAULT_API_HOST = "localhost"
DEFAULT_API_PORT = 8085

# Define stacked widget page indices
PAGE_EDIT_CHANNEL = 0
PAGE_SEARCH_RESULTS = 1
PAGE_SETTINGS = 2
PAGE_VIDEO_PLAYER = 3
PAGE_SUBSCRIBED_CHANNELS = 4
PAGE_DOWNLOADS = 5
PAGE_LOADING = 6
PAGE_DISCOVERING = 7
PAGE_DISCOVERED = 8
PAGE_TRUST = 9
PAGE_MARKET = 10
PAGE_MARKET_TRANSACTIONS = 11
PAGE_MARKET_WALLETS = 12
PAGE_MARKET_ORDERS = 13
PAGE_TOKEN_MINING_PAGE = 14
PAGE_TRUST_GRAPH_PAGE = 15

PAGE_EDIT_CHANNEL_TORRENTS = 2

PAGE_SETTINGS_GENERAL = 0
PAGE_SETTINGS_CONNECTION = 1
PAGE_SETTINGS_BANDWIDTH = 2
PAGE_SETTINGS_SEEDING = 3
PAGE_SETTINGS_ANONYMITY = 4
PAGE_SETTINGS_DEBUG = 5

# Definition of the download statuses and the corresponding strings
DLSTATUS_ALLOCATING_DISKSPACE = 0
DLSTATUS_WAITING4HASHCHECK = 1
DLSTATUS_HASHCHECKING = 2
DLSTATUS_DOWNLOADING = 3
DLSTATUS_SEEDING = 4
DLSTATUS_STOPPED = 5
DLSTATUS_STOPPED_ON_ERROR = 6
DLSTATUS_METADATA = 7
DLSTATUS_CIRCUITS = 8
DLSTATUS_EXIT_NODES = 9

DLSTATUS_STRINGS = [
    "Allocating disk space",
    "Waiting for check",
    "Checking",
    "Downloading",
    "Seeding",
    "Stopped",
    "Stopped on error",
    "Waiting for metadata",
    "Building circuits",
    "Finding exit nodes",
]

# Definitions of the download filters. For each filter, it is specified which download statuses can be displayed.
DOWNLOADS_FILTER_ALL = 0
DOWNLOADS_FILTER_DOWNLOADING = 1
DOWNLOADS_FILTER_COMPLETED = 2
DOWNLOADS_FILTER_ACTIVE = 3
DOWNLOADS_FILTER_INACTIVE = 4
DOWNLOADS_FILTER_CREDITMINING = 5
DOWNLOADS_FILTER_CHANNELS = 6

DOWNLOADS_FILTER_DEFINITION = {
    DOWNLOADS_FILTER_ALL: [
        DLSTATUS_ALLOCATING_DISKSPACE,
        DLSTATUS_WAITING4HASHCHECK,
        DLSTATUS_HASHCHECKING,
        DLSTATUS_DOWNLOADING,
        DLSTATUS_SEEDING,
        DLSTATUS_STOPPED,
        DLSTATUS_STOPPED_ON_ERROR,
        DLSTATUS_METADATA,
        DLSTATUS_CIRCUITS,
        DLSTATUS_EXIT_NODES,
    ],
    DOWNLOADS_FILTER_DOWNLOADING: [DLSTATUS_DOWNLOADING],
    DOWNLOADS_FILTER_COMPLETED: [DLSTATUS_SEEDING],
    DOWNLOADS_FILTER_ACTIVE: [
        DLSTATUS_ALLOCATING_DISKSPACE,
        DLSTATUS_WAITING4HASHCHECK,
        DLSTATUS_HASHCHECKING,
        DLSTATUS_DOWNLOADING,
        DLSTATUS_SEEDING,
        DLSTATUS_METADATA,
        DLSTATUS_CIRCUITS,
        DLSTATUS_EXIT_NODES,
    ],
    DOWNLOADS_FILTER_INACTIVE: [DLSTATUS_STOPPED, DLSTATUS_STOPPED_ON_ERROR],
}

BUTTON_TYPE_NORMAL = 0
BUTTON_TYPE_CONFIRM = 1

VIDEO_EXTS = [
    'aac',
    'asf',
    'avi',
    'dv',
    'divx',
    'flac',
    'flc',
    'flv',
    'mkv',
    'mpeg',
    'mpeg4',
    'mpegts',
    'mpg4',
    'mp3',
    'mp4',
    'mpg',
    'mkv',
    'mov',
    'm4v',
    'ogg',
    'ogm',
    'ogv',
    'oga',
    'ogx',
    'qt',
    'rm',
    'swf',
    'ts',
    'vob',
    'wmv',
    'wav',
    'webm',
]

# Tribler shutdown grace period in milliseconds
SHUTDOWN_WAITING_PERIOD = 120000

ACTION_BUTTONS = u'action_buttons'

# Torrent commit status constants
COMMIT_STATUS_NEW = 0
COMMIT_STATUS_TODELETE = 1
COMMIT_STATUS_COMMITTED = 2
COMMIT_STATUS_UPDATED = 6

HEALTH_CHECKING = u'Checking..'
HEALTH_DEAD = u'No peers'
HEALTH_ERROR = u'Error'
HEALTH_MOOT = u'Peers found'
HEALTH_GOOD = u'Seeds found'
HEALTH_UNCHECKED = u'Unknown'

# Interval for refreshing the results in the debug pane
DEBUG_PANE_REFRESH_TIMEOUT = 5000  # 5 seconds

# This list of content categories is used in drop-down menu when editing a personal channel
# TODO: build this automatically and/or move it somewhere
CATEGORY_LIST = (
    u'Video',
    u'VideoClips',
    u'Audio',
    u'Documents',
    u'CD/DVD/BD',
    u'Compressed',
    u'Games',
    u'Pictures',
    u'Books',
    u'Comics',
    u'Software',
    u'Science',
    u'XXX',
    u'Other',
)

# Trust Graph constants
COLOR_RED = "#b37477"
COLOR_GREEN = "#23cc2b"
COLOR_NEUTRAL = "#cdcdcd"
COLOR_DEFAULT = "#150507"
COLOR_ROOT = "#FE6D01"
COLOR_SELECTED = "#5c58ee"
COLOR_BACKGROUND = "#202020"
HTML_SPACE = '&nbsp;'
TRUST_GRAPH_PEER_LEGENDS = (
    u"<span style='color:%s'>\u25CF Helpful user </span> &nbsp;&nbsp;&nbsp;"
    u"<span style='color:%s'>\u25CF Selfish user </span> &nbsp;&nbsp;&nbsp;"
    u"<span style='color:%s'>\u25CF Unknown </span> &nbsp;&nbsp;&nbsp;"
    u"<span style='color:%s'>\u25CF Selected</span>" % (COLOR_GREEN, COLOR_RED, COLOR_NEUTRAL, COLOR_SELECTED)
)

CONTEXT_MENU_WIDTH = 200

BITTORRENT_BIRTHDAY = 994032000

# Timeout for metainfo request
METAINFO_MAX_RETRIES = 3
METAINFO_TIMEOUT = 65000

# Sizes
KB = 1024
MB = 1024 * KB
GB = 1024 * MB
TB = 1024 * GB
PB = 1024 * TB

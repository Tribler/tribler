"""
This file contains various definitions used by the Tribler GUI.
"""
import sys
from collections import namedtuple

from PyQt5.QtGui import QColor

from tribler.core.utilities.simpledefs import DownloadStatus

DEFAULT_API_PROTOCOL = "http"
DEFAULT_API_HOST = "localhost"

# Define stacked widget page indices
PAGE_SEARCH_RESULTS = 0
PAGE_SETTINGS = 1
PAGE_DOWNLOADS = 2
PAGE_LOADING = 3
PAGE_POPULAR = 4

PAGE_EDIT_CHANNEL_TORRENTS = 2

PAGE_SETTINGS_GENERAL = 0
PAGE_SETTINGS_CONNECTION = 1
PAGE_SETTINGS_BANDWIDTH = 2
PAGE_SETTINGS_SEEDING = 3
PAGE_SETTINGS_ANONYMITY = 4
PAGE_SETTINGS_DATA = 5
PAGE_SETTINGS_DEBUG = 6

STATUS_STRING = {
    DownloadStatus.ALLOCATING_DISKSPACE: "Allocating disk space",
    DownloadStatus.WAITING_FOR_HASHCHECK: "Waiting for check",
    DownloadStatus.HASHCHECKING: "Checking",
    DownloadStatus.DOWNLOADING: "Downloading",
    DownloadStatus.SEEDING: "Seeding",
    DownloadStatus.STOPPED: "Stopped",
    DownloadStatus.STOPPED_ON_ERROR: "Stopped on error",
    DownloadStatus.METADATA: "Waiting for metadata",
    DownloadStatus.CIRCUITS: "Building circuits",
    DownloadStatus.EXIT_NODES: "Finding exit nodes",
}

# Definitions of the download filters. For each filter, it is specified which download statuses can be displayed.
DOWNLOADS_FILTER_ALL = 0
DOWNLOADS_FILTER_DOWNLOADING = 1
DOWNLOADS_FILTER_COMPLETED = 2
DOWNLOADS_FILTER_ACTIVE = 3
DOWNLOADS_FILTER_INACTIVE = 4
DOWNLOADS_FILTER_CHANNELS = 6

DOWNLOADS_FILTER_DEFINITION = {
    DOWNLOADS_FILTER_ALL: [
        DownloadStatus.ALLOCATING_DISKSPACE,
        DownloadStatus.WAITING_FOR_HASHCHECK,
        DownloadStatus.HASHCHECKING,
        DownloadStatus.DOWNLOADING,
        DownloadStatus.SEEDING,
        DownloadStatus.STOPPED,
        DownloadStatus.STOPPED_ON_ERROR,
        DownloadStatus.METADATA,
        DownloadStatus.CIRCUITS,
        DownloadStatus.EXIT_NODES,
    ],
    DOWNLOADS_FILTER_DOWNLOADING: [
        DownloadStatus.DOWNLOADING,
    ],
    DOWNLOADS_FILTER_COMPLETED: [
        DownloadStatus.SEEDING,
    ],
    DOWNLOADS_FILTER_ACTIVE: [
        DownloadStatus.ALLOCATING_DISKSPACE,
        DownloadStatus.WAITING_FOR_HASHCHECK,
        DownloadStatus.HASHCHECKING,
        DownloadStatus.DOWNLOADING,
        DownloadStatus.SEEDING,
        DownloadStatus.METADATA,
        DownloadStatus.CIRCUITS,
        DownloadStatus.EXIT_NODES,
    ],
    DOWNLOADS_FILTER_INACTIVE: [
        DownloadStatus.STOPPED,
        DownloadStatus.STOPPED_ON_ERROR
    ],
}

BUTTON_TYPE_NORMAL = 0
BUTTON_TYPE_CONFIRM = 1

# Tribler shutdown grace period in milliseconds
SHUTDOWN_WAITING_PERIOD = 30000

# Torrent commit status constants
COMMIT_STATUS_NEW = 0
COMMIT_STATUS_TODELETE = 1
COMMIT_STATUS_COMMITTED = 2
COMMIT_STATUS_UPDATED = 6

HEALTH_CHECKING = 'Checking..'
HEALTH_DEAD = 'No peers'
HEALTH_ERROR = 'Error'
HEALTH_MOOT = 'Peers found'
HEALTH_GOOD = 'Seeds found'
HEALTH_UNCHECKED = 'Unknown'

# Interval for refreshing the results in the debug pane
DEBUG_PANE_REFRESH_TIMEOUT = 5000  # 5 seconds

ContentCategoryTuple = namedtuple("ContentCategoryTuple", "code emoji long_name short_name")


class ContentCategories:
    # This class contains definitions of content categories and associated representation
    # methods, e.g. emojis, names, etc.
    # It should never be instanced, but instead used as a collection of classmethods.

    _category_emojis = (
        ('Video', '🎦'),
        ('VideoClips', '📹'),
        ('Audio', '🎧'),
        ('Documents', '📝'),
        ('CD/DVD/BD', '📀'),
        ('Compressed', '🗜'),
        ('Games', '👾'),
        ('Pictures', '📷'),
        ('Books', '📚'),
        ('Comics', '💢'),
        ('Software', '💾'),
        ('Science', '🔬'),
        ('XXX', '💋'),
        ('Other', '🤔'),
    )
    _category_tuples = tuple(
        ContentCategoryTuple(code, emoji, emoji + " " + code, code) for code, emoji in _category_emojis
    )

    _associative_dict = {}
    for cat_index, cat_tuple in enumerate(_category_tuples):
        _associative_dict[cat_tuple.code] = cat_tuple
        _associative_dict[cat_index] = cat_tuple
        _associative_dict[cat_tuple.long_name] = cat_tuple

    codes = tuple(t.code for t in _category_tuples)
    long_names = tuple(t.long_name for t in _category_tuples)
    short_names = tuple(t.short_name for t in _category_tuples)

    @classmethod
    def get(cls, item, default=None):
        return cls._associative_dict.get(item, default)


CATEGORY_SELECTOR_FOR_SEARCH_ITEMS = ("All", "Channels") + ContentCategories.long_names
CATEGORY_SELECTOR_FOR_POPULAR_ITEMS = ("All",) + ContentCategories.long_names

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

DARWIN = sys.platform == 'darwin'
WINDOWS = sys.platform == 'win32'

# Constants related to the tag widgets
TAG_BACKGROUND_COLOR = QColor("#36311e")
TAG_BORDER_COLOR = QColor("#453e25")
TAG_TEXT_COLOR = QColor("#ecbe42")

SUGGESTED_TAG_BACKGROUND_COLOR = TAG_BACKGROUND_COLOR
SUGGESTED_TAG_BORDER_COLOR = TAG_TEXT_COLOR
SUGGESTED_TAG_TEXT_COLOR = TAG_TEXT_COLOR

EDIT_TAG_BACKGROUND_COLOR = QColor("#3B2D06")
EDIT_TAG_BORDER_COLOR = QColor("#271E04")
EDIT_TAG_TEXT_COLOR = SUGGESTED_TAG_TEXT_COLOR

TAG_HEIGHT = 22
TAG_TEXT_HORIZONTAL_PADDING = 10
TAG_TOP_MARGIN = 32
TAG_HORIZONTAL_MARGIN = 6


UPGRADE_CANCELLED_ERROR_TITLE = "Tribler Upgrade cancelled"

NO_DISK_SPACE_ERROR_MESSAGE = "Not enough storage space available. \n" \
                              "Tribler requires at least %s space to continue. \n\n" \
                              "Please free up the required space and re-run Tribler. "

CORRUPTED_DB_WAS_FIXED_MESSAGE = "The corrupted database file was fixed"

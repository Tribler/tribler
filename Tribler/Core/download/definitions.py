from enum import Enum


class DownloadStatus(Enum):
    ALLOCATING_DISK_SPACE = 0  # TODO: make sure this get set when in this alloc mode
    WAITING_FOR_HASH_CHECK = 1
    CHECKING_HASH = 2
    DOWNLOADING = 3
    SEEDING = 4
    STOPPED = 5
    STOPPED_ON_ERROR = 6
    METADATA = 7
    CIRCUITS = 8


class DownloadDirection(Enum):
    UP = 'up'
    DOWN = 'down'


class DownloadMode(Enum):
    NORMAL = 0
    VOD = 1

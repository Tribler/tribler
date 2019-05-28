# The categories that can be assigned to a torrent, tuple of display name and chance of appearing.
CATEGORIES = [
    ('xxx', 0.2),
    ('other', 0.1),
    ('unknown', 0.1),
    ('Video', 0.1),
    ('VideoClips', 0.1),
    ('Audio', 0.1),
    ('Document', 0.1),
    ('Compressed', 0.1),
    ('Picture', 0.1)]

DLSTATUS_STRINGS = ['DLSTATUS_ALLOCATING_DISKSPACE',
                    'DLSTATUS_WAITING4HASHCHECK',
                    'DLSTATUS_HASHCHECKING',
                    'DLSTATUS_DOWNLOADING',
                    'DLSTATUS_SEEDING',
                    'DLSTATUS_STOPPED',
                    'DLSTATUS_STOPPED_ON_ERROR',
                    'DLSTATUS_METADATA',
                    'DLSTATUS_CIRCUITS']


# Metadata, torrents and channel statuses
NEW = 0
TODELETE = 1
COMMITTED = 2
JUST_RECEIVED = 3
UPDATE_AVAILABLE = 4
PREVIEW_UPDATE_AVAILABLE = 5

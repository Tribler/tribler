# Written by Arno Bakker 
# see LICENSE.txt for license information
import os

DLSTATUS_ALLOCATING_DISKSPACE = 0 # TODO: make sure this get set when in this alloc mode
DLSTATUS_WAITING4HASHCHECK = 1
DLSTATUS_HASHCHECKING = 2
DLSTATUS_DOWNLOADING = 3
DLSTATUS_SEEDING = 4
DLSTATUS_STOPPED = 5
DLSTATUS_STOPPED_ON_ERROR = 6

dlstatus_strings = ['DLSTATUS_ALLOCATING_DISKSPACE',
'DLSTATUS_WAITING4HASHCHECK', 
'DLSTATUS_HASHCHECKING',
'DLSTATUS_DOWNLOADING',
'DLSTATUS_SEEDING',
'DLSTATUS_STOPPED',
'DLSTATUS_STOPPED_ON_ERROR']

UPLOAD = 'up'
DOWNLOAD = 'down'

DLMODE_NORMAL = 0
DLMODE_VOD = 1

PERSISTENTSTATE_CURRENTVERSION = 1

STATEDIR_ITRACKER_DIR = 'itracker'
STATEDIR_DLPSTATE_DIR = 'dlcheckpoints'
STATEDIR_SESSCONFIG = 'sessconfig.pickle' 

TRIBLER_TORRENT_EXT = ".tribe"

# For observer/callback mechanism, see Session.add_observer()
   
# subjects
NTFY_PEERS = 'peers'
NTFY_TORRENTS = 'torrents'
NTFY_YOUTUBE = 'youtube'
NTFY_PREFERENCES = 'preferences'

# non data handler subjects
NTFY_DOWNLOADS = 'downloads'             # a torrent download was added/removed/changed
NTFY_ACTIVITIES = 'activities'           # an activity was set (peer met/dns resolved)

# changeTypes
NTFY_UPDATE = 'update'                   # data is updated
NTFY_INSERT = 'insert'                   # new data is inserted
NTFY_DELETE = 'delete'                   # data is deleted
NTFY_SEARCH_RESULT = 'search_result'     # new search result
 
# Written by Arno Bakker 
# see LICENSE.txt for license information
""" Simple definitions for the Tribler Core. """
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

PERSISTENTSTATE_CURRENTVERSION = 3
"""
V1 = SwarmPlayer 1.0.0
V2 = Tribler 4.5.0: SessionConfig: Added NAT fields
V3 = SessionConfig: Added multicast_local_peer_discovery, 
     Removed rss_reload_frequency + rss_check_frequency.

For details see API.py
"""

STATEDIR_ITRACKER_DIR = 'itracker'
STATEDIR_DLPSTATE_DIR = 'dlcheckpoints'
STATEDIR_PEERICON_DIR = 'icons'
STATEDIR_TORRENTCOLL_DIR = 'collected_torrent_files'
STATEDIR_SESSCONFIG = 'sessconfig.pickle'
STATEDIR_SEEDINGMANAGER_DIR = 'seeding_manager_stats'
DESTDIR_COOPDOWNLOAD = 'downloadhelp' 

TRIBLER_TORRENT_EXT = ".tribe"

# For observer/callback mechanism, see Session.add_observer()
   
# subjects
NTFY_PEERS = 'peers'
NTFY_TORRENTS = 'torrents'
NTFY_PREFERENCES = 'preferences'
NTFY_SUPERPEERS = 'superpeers' # use NTFY_PEERS !!
NTFY_FRIENDS = 'friends'       # use NTFY_PEERS !!
NTFY_MYPREFERENCES = 'mypreferences' # currently not observable
NTFY_BARTERCAST = 'bartercast' # currently not observable
NTFY_MYINFO = 'myinfo'
NTFY_SEEDINGSTATS = 'seedingstats'
NTFY_SEEDINGSTATSSETTINGS = 'seedingstatssettings'
NTFY_MODERATIONCAST = 'moderationcast'
NTFY_VOTECAST = 'votecast'
NTFY_SEARCH = 'clicklogsearch' # BuddyCast 4
NTFY_TERM= 'clicklogterm'


# non data handler subjects
NTFY_ACTIVITIES = 'activities' # an activity was set (peer met/dns resolved)
NTFY_REACHABLE = 'reachable'   # the Session is reachable from the Internet

# changeTypes
NTFY_UPDATE = 'update'         # data is updated
NTFY_INSERT = 'insert'         # new data is inserted
NTFY_DELETE = 'delete'         # data is deleted
NTFY_SEARCH_RESULT = 'search_result'     # new search result
NTFY_CONNECTION = 'connection' # connection made or broken

# object IDs for NTFY_ACTIVITIES subject 
NTFY_ACT_NONE = 0
NTFY_ACT_UPNP = 1
NTFY_ACT_REACHABLE = 2
NTFY_ACT_GET_EXT_IP_FROM_PEERS = 3
NTFY_ACT_MEET = 4
NTFY_ACT_GOT_METADATA = 5
NTFY_ACT_RECOMMEND = 6
NTFY_ACT_DISK_FULL = 7
NTFY_ACT_NEW_VERSION = 8
NTFY_ACT_ACTIVE = 9
 
# Disk-allocation policies for download, see DownloadConfig.set_alloc_type
DISKALLOC_NORMAL = 'normal'              
DISKALLOC_BACKGROUND = 'background'      
DISKALLOC_PREALLOCATE = 'pre-allocate'
DISKALLOC_SPARSE = 'sparse'

# UPnP modes, see SessionConfig.set_upnp_mode
UPNPMODE_DISABLED = 0
UPNPMODE_WIN32_HNetCfg_NATUPnP = 1
UPNPMODE_WIN32_UPnP_UPnPDeviceFinder = 2
UPNPMODE_UNIVERSAL_DIRECT = 3

# Buddycast Collecting Policy parameters
BCCOLPOLICY_SIMPLE = 1
# BCCOLPOLICY_T4T = 2 # Future work

# Internal tracker scrape
ITRACKSCRAPE_ALLOW_NONE = 'none'
ITRACKSCRAPE_ALLOW_SPECIFIC = 'specific'
ITRACKSCRAPE_ALLOW_FULL = 'full'

ITRACKDBFORMAT_BENCODE = 'bencode'
ITRACKDBFORMAT_PICKLE= 'pickle'

ITRACKMULTI_ALLOW_NONE = 'none'
ITRACKMULTI_ALLOW_AUTODETECT = 'autodetect'
ITRACKMULTI_ALLOW_ALL = 'all'

ITRACK_IGNORE_ANNOUNCEIP_NEVER = 0
ITRACK_IGNORE_ANNOUNCEIP_ALWAYS = 1
ITRACK_IGNORE_ANNOUNCEIP_IFNONATCHECK = 2

# Cooperative download
COOPDL_ROLE_COORDINATOR = 'coordinator'
COOPDL_ROLE_HELPER = 'helper'

# Methods for authentication of the source in live streaming
LIVE_AUTHMETHOD_NONE = "None"   # None
LIVE_AUTHMETHOD_ECDSA = "ECDSA" # Elliptic Curve DSA signatures
LIVE_AUTHMETHOD_RSA = "RSA" # RSA signatures

# Video-On-Demand / live events
VODEVENT_START = "start"
VODEVENT_PAUSE = "pause"
VODEVENT_RESUME = "resume"


# Friendship messages
F_REQUEST_MSG = "REQ"
F_RESPONSE_MSG = "RESP"
F_FORWARD_MSG = "FWD" # Can forward any type of other friendship message


# States for a friend
FS_NOFRIEND = 0
FS_MUTUAL = 1
FS_I_INVITED = 2
FS_HE_INVITED = 3
FS_I_DENIED = 4
FS_HE_DENIED = 5

P2PURL_SCHEME = "nsp"

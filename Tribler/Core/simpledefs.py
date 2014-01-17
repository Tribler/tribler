# Written by Arno Bakker
# see LICENSE.txt for license information
""" Simple definitions for the Tribler Core. """
import os

DLSTATUS_ALLOCATING_DISKSPACE = 0  # TODO: make sure this get set when in this alloc mode
DLSTATUS_WAITING4HASHCHECK = 1
DLSTATUS_HASHCHECKING = 2
DLSTATUS_DOWNLOADING = 3
DLSTATUS_SEEDING = 4
DLSTATUS_STOPPED = 5
DLSTATUS_STOPPED_ON_ERROR = 6
DLSTATUS_REPEXING = 7
DLSTATUS_METADATA = 8

dlstatus_strings = ['DLSTATUS_ALLOCATING_DISKSPACE',
                    'DLSTATUS_WAITING4HASHCHECK',
                    'DLSTATUS_HASHCHECKING',
'DLSTATUS_DOWNLOADING',
'DLSTATUS_SEEDING',
'DLSTATUS_STOPPED',
'DLSTATUS_STOPPED_ON_ERROR',
'DLSTATUS_REPEXING',
'DLSTATUS_METADATA']

UPLOAD = 'up'
DOWNLOAD = 'down'

DLMODE_NORMAL = 0
DLMODE_VOD = 1
DLMODE_SVC = 2  # Ric: added download mode for Scalable Video Coding (SVC)

PERSISTENTSTATE_CURRENTVERSION = 5
"""
V1 = SwarmPlayer 1.0.0
V2 = Tribler 4.5.0: SessionConfig: Added NAT fields
V3 = SessionConfig: Added multicast_local_peer_discovery,
     Removed rss_reload_frequency + rss_check_frequency.
V4 = ... + added pickled SwiftDef
V5 = no longer pickling data
For details see API.py
"""

STATEDIR_ITRACKER_DIR = 'itracker'
STATEDIR_DLPSTATE_DIR = 'dlcheckpoints'
STATEDIR_PEERICON_DIR = 'icons'
STATEDIR_TORRENTCOLL_DIR = 'collected_torrent_files'
STATEDIR_SWIFTRESEED_DIR = os.path.join(STATEDIR_TORRENTCOLL_DIR, 'swift_reseeds')

STATEDIR_SESSCONFIG = 'libtribler.conf'
STATEDIR_SEEDINGMANAGER_DIR = 'seeding_manager_stats'
PROXYSERVICE_DESTDIR = 'proxyservice'

# For observer/callback mechanism, see Session.add_observer()

# subjects
NTFY_MISC = 'misc'
NTFY_PEERS = 'peers'
NTFY_TORRENTS = 'torrents'
NTFY_PLAYLISTS = 'playlists'
NTFY_COMMENTS = 'comments'
NTFY_MODIFICATIONS = 'modifications'
NTFY_MARKINGS = 'markings'
NTFY_MODERATIONS = 'moderations'
NTFY_FRIENDS = 'friends'  # use NTFY_PEERS !!
NTFY_MYPREFERENCES = 'mypreferences'  # currently not observable
NTFY_MYINFO = 'myinfo'
NTFY_SEEDINGSTATS = 'seedingstats'
NTFY_SEEDINGSTATSSETTINGS = 'seedingstatssettings'
NTFY_VOTECAST = 'votecast'
NTFY_CHANNELCAST = 'channelcast'
NTFY_TRACKERINFO = 'trackerinfo'

# non data handler subjects
NTFY_ACTIVITIES = 'activities'  # an activity was set (peer met/dns resolved)
NTFY_REACHABLE = 'reachable'  # the Session is reachable from the Internet
NTFY_PROXYDOWNLOADER = "proxydownloader"  # the proxydownloader object was created
NTFY_PROXYDISCOVERY = "proxydiscovery"  # a new proxy was discovered
# ProxyService 90s Test_
# NTFY_GUI_STARTED = "guistarted"
# _ProxyService 90s Test
NTFY_DISPERSY = 'dispersy'  # an notification regarding dispersy

# changeTypes
NTFY_UPDATE = 'update'  # data is updated
NTFY_INSERT = 'insert'  # new data is inserted
NTFY_DELETE = 'delete'  # data is deleted
NTFY_CREATE = 'create'  # new data is created, meaning in the case of Channels your own channel is created
NTFY_SEARCH_RESULT = 'search_result'  # new search result
NTFY_CONNECTION = 'connection'  # connection made or broken
NTFY_STARTED = 'started'
NTFY_STATE = 'state'
NTFY_MODIFIED = 'modified'
NTFY_FINISHED = 'finished'
NTFY_MAGNET_STARTED = 'magnet_started'
NTFY_MAGNET_GOT_PEERS = 'magnet_peers'
NTFY_MAGNET_PROGRESS = 'magnet_progress'
NTFY_MAGNET_CLOSE = 'magnet_close'
NTFY_VIDEO_STARTED = 'video_started'
NTFY_VIDEO_STOPPED = 'video_stopped'
NTFY_VIDEO_ENDED = 'video_ended'

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

# Buddycast Collecting Policy parameters
BCCOLPOLICY_SIMPLE = 1
# BCCOLPOLICY_T4T = 2 # Future work

# Internal tracker scrape
ITRACKSCRAPE_ALLOW_NONE = 'none'
ITRACKSCRAPE_ALLOW_SPECIFIC = 'specific'
ITRACKSCRAPE_ALLOW_FULL = 'full'

ITRACKDBFORMAT_BENCODE = 'bencode'
ITRACKDBFORMAT_PICKLE = 'pickle'

ITRACKMULTI_ALLOW_NONE = 'none'
ITRACKMULTI_ALLOW_AUTODETECT = 'autodetect'
ITRACKMULTI_ALLOW_ALL = 'all'

ITRACK_IGNORE_ANNOUNCEIP_NEVER = 0
ITRACK_IGNORE_ANNOUNCEIP_ALWAYS = 1
ITRACK_IGNORE_ANNOUNCEIP_IFNONATCHECK = 2

# ProxyService
PROXYSERVICE_DOE_OBJECT = "doe-obj"
PROXYSERVICE_PROXY_OBJECT = "proxy-obj"

PROXYSERVICE_ROLE_DOE = 'doe-role'
PROXYSERVICE_ROLE_PROXY = 'proxy-role'
PROXYSERVICE_ROLE_NONE = 'none-role'

DOE_MODE_OFF = 0
DOE_MODE_PRIVATE = 1
DOE_MODE_SPEED = 2

PROXYSERVICE_OFF = 0
PROXYSERVICE_ON = 1

# Methods for authentication of the source in live streaming
LIVE_AUTHMETHOD_NONE = "None"  # No auth, also no abs. piece nr. or timestamp.
LIVE_AUTHMETHOD_ECDSA = "ECDSA"  # Elliptic Curve DSA signatures
LIVE_AUTHMETHOD_RSA = "RSA"  # RSA signatures

# Video-On-Demand / live events
VODEVENT_START = "start"
VODEVENT_PAUSE = "pause"
VODEVENT_RESUME = "resume"


# Friendship messages
F_REQUEST_MSG = "REQ"
F_RESPONSE_MSG = "RESP"
F_FORWARD_MSG = "FWD"  # Can forward any type of other friendship message


# States for a friend
FS_NOFRIEND = 0
FS_MUTUAL = 1
FS_I_INVITED = 2
FS_HE_INVITED = 3
FS_I_DENIED = 4
FS_HE_DENIED = 5

P2PURL_SCHEME = "tribe"  # No colon
SWIFT_URL_SCHEME = "tswift"  # No colon

URL_MIME_TYPE = 'text/x-url'
TSTREAM_MIME_TYPE = "application/x-ns-stream"

TRIBLER_TORRENT_EXT = ".tribe"  # Unused

# Infohashes are always 20 byte binary strings
INFOHASH_LENGTH = 20

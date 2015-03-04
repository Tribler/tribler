# Written by Arno Bakker
# see LICENSE.txt for license information

""" Simple definitions for the Tribler Core. """
DLSTATUS_ALLOCATING_DISKSPACE = 0  # TODO: make sure this get set when in this alloc mode
DLSTATUS_WAITING4HASHCHECK = 1
DLSTATUS_HASHCHECKING = 2
DLSTATUS_DOWNLOADING = 3
DLSTATUS_SEEDING = 4
DLSTATUS_STOPPED = 5
DLSTATUS_STOPPED_ON_ERROR = 6
DLSTATUS_METADATA = 7
DLSTATUS_CIRCUITS = 8

dlstatus_strings = ['DLSTATUS_ALLOCATING_DISKSPACE',
                    'DLSTATUS_WAITING4HASHCHECK',
                    'DLSTATUS_HASHCHECKING',
                    'DLSTATUS_DOWNLOADING',
                    'DLSTATUS_SEEDING',
                    'DLSTATUS_STOPPED',
                    'DLSTATUS_STOPPED_ON_ERROR',
                    'DLSTATUS_METADATA',
                    'DLSTATUS_CIRCUITS']

UPLOAD = 'up'
DOWNLOAD = 'down'

DLMODE_NORMAL = 0
DLMODE_VOD = 1

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

STATEDIR_DLPSTATE_DIR = 'dlcheckpoints'
STATEDIR_PEERICON_DIR = 'icons'
STATEDIR_TORRENT_STORE_DIR = 'collected_torrents'

STATEDIR_SESSCONFIG = 'libtribler.conf'

# For observer/callback mechanism, see Session.add_observer()

# subjects
NTFY_MISC = 'misc'
NTFY_METADATA = 'metadata'
NTFY_PEERS = 'peers'
NTFY_TORRENTS = 'torrents'
NTFY_PLAYLISTS = 'playlists'
NTFY_COMMENTS = 'comments'
NTFY_MODIFICATIONS = 'modifications'
NTFY_MARKINGS = 'markings'
NTFY_MODERATIONS = 'moderations'
NTFY_MYPREFERENCES = 'mypreferences'
NTFY_SEEDINGSTATS = 'seedingstats'
NTFY_SEEDINGSTATSSETTINGS = 'seedingstatssettings'
NTFY_VOTECAST = 'votecast'
NTFY_CHANNELCAST = 'channelcast'
NTFY_TUNNEL = 'tunnel'
NTFY_TRACKERINFO = 'trackerinfo'

# non data handler subjects
NTFY_ACTIVITIES = 'activities'  # an activity was set (peer met/dns resolved)
NTFY_REACHABLE = 'reachable'  # the Session is reachable from the Internet
NTFY_DISPERSY = 'dispersy'  # an notification regarding dispersy

# changeTypes
NTFY_UPDATE = 'update'  # data is updated
NTFY_INSERT = 'insert'  # new data is inserted
NTFY_DELETE = 'delete'  # data is deleted
NTFY_CREATE = 'create'  # new data is created, meaning in the case of Channels your own channel is created
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
NTFY_VIDEO_BUFFERING = 'video_bufering'
NTFY_CREATED = 'created'
NTFY_EXTENDED = 'extended'
NTFY_EXTENDED_FOR = 'extended_for'
NTFY_BROKEN = 'broken'
NTFY_SELECT = 'select'
NTFY_JOINED = 'joined'

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


# Methods for authentication of the source in live streaming
LIVE_AUTHMETHOD_NONE = "None"  # No auth, also no abs. piece nr. or timestamp.
LIVE_AUTHMETHOD_ECDSA = "ECDSA"  # Elliptic Curve DSA signatures
LIVE_AUTHMETHOD_RSA = "RSA"  # RSA signatures

# Infohashes are always 20 byte binary strings
INFOHASH_LENGTH = 20


# SIGNALS
SIGNAL_ALLCHANNEL = 'allchannel'
SIGNAL_SEARCH_COMMUNITY = 'search_community'
SIGNAL_ONSEARCHRESULTS = 'onsearchresults'

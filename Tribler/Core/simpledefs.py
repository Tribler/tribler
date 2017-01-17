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

STATEDIR_DLPSTATE_DIR = u'dlcheckpoints'
STATEDIR_PEERICON_DIR = u'icons'
STATEDIR_TORRENT_STORE_DIR = u'collected_torrents'
STATEDIR_METADATA_STORE_DIR = u'collected_metadata'

STATEDIR_SESSCONFIG = 'libtribler.conf'
STATEDIR_DLCONFIG = 'tribler.conf'
STATEDIR_GUICONFIG = 'tribler.conf'
STATEDIR_CONFIG = 'triblerd.conf'

# For observer/callback mechanism, see Session.add_observer()

# subjects
NTFY_PEERS = 'peers'
NTFY_TORRENTS = 'torrents'
NTFY_TORRENT = 'torrent'
NTFY_CHANNEL = 'channel'
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

NTFY_IP_REMOVED = 'intropointremoved'
NTFY_RP_REMOVED = 'rendezvouspointremoved'
NTFY_IP_RECREATE = 'intropointrecreate'
NTFY_DHT_LOOKUP = 'dhtlookupanontorrent'
NTFY_KEY_REQUEST = 'keyrequest'
NTFY_KEY_RESPOND = 'ipkeyrespond'
NTFY_KEY_RESPONSE = 'keyresponsereceived'
NTFY_CREATE_E2E = 'createendtoend'
NTFY_ONCREATED_E2E = 'oncreatedendtoend'
NTFY_IP_CREATED = 'intropointcreated'
NTFY_RP_CREATED = 'rendezvouspointcreated'
NTFY_UPGRADER = 'upgraderdone'
NTFY_UPGRADER_TICK = 'upgradertick'

NTFY_STARTUP_TICK = 'startuptick'
NTFY_CLOSE_TICK = 'closetick'

# non data handler subjects
NTFY_ACTIVITIES = 'activities'  # an activity was set (peer met/dns resolved)
NTFY_REACHABLE = 'reachable'  # the Session is reachable from the Internet
NTFY_TRIBLER = 'tribler'  # notifications regarding Tribler in general
NTFY_DISPERSY = 'dispersy'  # an notification regarding dispersy
NTFY_WATCH_FOLDER_CORRUPT_TORRENT = 'corrupt_torrent'  # a corrupt torrent has been found in the watch folder
NTFY_NEW_VERSION = 'newversion' # a new version of Tribler is available

# changeTypes
NTFY_UPDATE = 'update'  # data is updated
NTFY_INSERT = 'insert'  # new data is inserted
NTFY_DELETE = 'delete'  # data is deleted
NTFY_CREATE = 'create'  # new data is created, meaning in the case of Channels your own channel is created
NTFY_SCRAPE = 'scrape'
NTFY_STARTED = 'started'
NTFY_STATE = 'state'
NTFY_MODIFIED = 'modified'
NTFY_FINISHED = 'finished'
NTFY_ERROR = 'error'
NTFY_MAGNET_STARTED = 'magnet_started'
NTFY_MAGNET_GOT_PEERS = 'magnet_peers'
NTFY_MAGNET_CLOSE = 'magnet_close'
NTFY_CREATED = 'created'
NTFY_EXTENDED = 'extended'
NTFY_JOINED = 'joined'
NTFY_REMOVE = 'remove'
NTFY_DISCOVERED = 'discovered'

# object IDs for NTFY_ACTIVITIES subject
NTFY_ACT_MEET = 4


# Infohashes are always 20 byte binary strings
INFOHASH_LENGTH = 20


# SIGNALS (for internal use)
SIGNAL_ALLCHANNEL_COMMUNITY = 'signal_allchannel_community'
SIGNAL_CHANNEL_COMMUNITY = 'signal_channel_community'
SIGNAL_SEARCH_COMMUNITY = 'signal_search_community'

SIGNAL_ON_SEARCH_RESULTS = 'signal_on_search_results'
SIGNAL_ON_TORRENT_UPDATED = 'signal_on_torrent_updated'


# SIGNALS (for common use, like APIs)
SIGNAL_TORRENT = 'signal_torrent'
SIGNAL_CHANNEL = 'signal_channel'
SIGNAL_RSS_FEED = 'signal_rss_feed'

SIGNAL_ON_CREATED = 'signal_on_created'
SIGNAL_ON_UPDATED = 'signal_on_updated'


# Tribler Core states
STATE_STARTING = "STARTING"
STATE_UPGRADING = "UPGRADING"
STATE_STARTED = "STARTED"
STATE_EXCEPTION = "EXCEPTION"

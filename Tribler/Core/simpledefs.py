"""
Simple definitions.

Author(s): Arno Bakker
"""

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

dlstatus_strings = ['DLSTATUS_ALLOCATING_DISKSPACE',
                    'DLSTATUS_WAITING4HASHCHECK',
                    'DLSTATUS_HASHCHECKING',
                    'DLSTATUS_DOWNLOADING',
                    'DLSTATUS_SEEDING',
                    'DLSTATUS_STOPPED',
                    'DLSTATUS_STOPPED_ON_ERROR',
                    'DLSTATUS_METADATA',
                    'DLSTATUS_CIRCUITS',
                    'DLSTATUS_EXIT_NODES']

UPLOAD = 'up'
DOWNLOAD = 'down'

DLMODE_NORMAL = 0
DLMODE_VOD = 1

PERSISTENTSTATE_CURRENTVERSION = 5

STATEDIR_DLPSTATE_DIR = u'dlcheckpoints'
STATEDIR_WALLET_DIR = u'wallet'
STATEDIR_CHANNELS_DIR = u'channels'
STATEDIR_DB_DIR = u"sqlite"

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
NTFY_CREDIT_MINING = 'creditmining'

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

NTFY_MARKET_ON_ASK = 'onmarketask'
NTFY_MARKET_ON_BID = 'onmarketbid'
NTFY_MARKET_ON_ASK_TIMEOUT = 'onmarketasktimeout'
NTFY_MARKET_ON_BID_TIMEOUT = 'onmarketbidtimeout'
NTFY_MARKET_ON_TRANSACTION_COMPLETE = 'onmarkettransactioncomplete'
NTFY_MARKET_ON_PAYMENT_RECEIVED = 'onmarketpaymentreceived'
NTFY_MARKET_ON_PAYMENT_SENT = 'onmarketpaymentsent'
NTFY_MARKET_IOM_INPUT_REQUIRED = 'onmarketiominputrequired'

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

SIGNAL_RESOURCE_CHECK = 'signal_resource_check'
SIGNAL_LOW_SPACE = 'signal_low_space'

# Tribler Core states
STATE_STARTING = "STARTING"
STATE_UPGRADING = "UPGRADING"
STATE_STARTED = "STARTED"
STATE_EXCEPTION = "EXCEPTION"
STATE_SHUTDOWN = "SHUTDOWN"

STATE_START_API = 'Starting HTTP API...'
STATE_UPGRADING_READABLE = 'Upgrading Tribler...'
STATE_LOAD_CHECKPOINTS = 'Loading download checkpoints...'
STATE_START_LIBTORRENT = 'Starting libtorrent...'
STATE_START_TORRENT_CHECKER = 'Starting torrent checker...'
STATE_START_API_ENDPOINTS = 'Starting API endpoints...'
STATE_START_WATCH_FOLDER = 'Starting watch folder...'
STATE_START_CREDIT_MINING = 'Starting credit mining...'
STATE_START_RESOURCE_MONITOR = 'Starting resource monitor...'
STATE_READABLE_STARTED = 'Started'

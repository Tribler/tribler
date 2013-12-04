# Written by Arno Bakker and Bram Cohen
# Updated by George Milescu
# Updated by Egbert Bouman, added subsection names + using OrderedDict + cleanup 
# see LICENSE.txt for license information

""" Default values for all configurarable parameters of the Core"""
#
# For an explanation of each parameter, see SessionConfig/DownloadConfig.py
#
# defaults with comments behind them are not user-setable via the
# *ConfigInterface classes, because they are not currently implemented (IPv6)
# or we only use them internally.
#
# WARNING:
#    As we have release Tribler 4.5.0 you must now take into account that
#    people have stored versions of these params on their disk. Make sure
#    you change the version number of the structure and provide upgrade code
#    such that your code won't barf because we loaded an older version from
#    disk that does not have your new fields.
#

from collections import OrderedDict

DEFAULTPORT = 7760

#
# Session opts
#
# History:
#  Version 2: as released in Tribler 4.5.0
#  Version 3: cleanup unused params
#

SESSDEFAULTS_VERSION = 3
sessdefaults = OrderedDict()

# General Tribler settings
sessdefaults['general'] = OrderedDict()
sessdefaults['general']['version'] = SESSDEFAULTS_VERSION
sessdefaults['general']['state_dir'] = None
sessdefaults['general']['install_dir'] = u'.'
sessdefaults['general']['ip'] = ''
sessdefaults['general']['minport'] = DEFAULTPORT
sessdefaults['general']['maxport'] = DEFAULTPORT
sessdefaults['general']['bind'] = []
sessdefaults['general']['ipv6_enabled'] = 0  # allow the client to connect to peers via IPv6 (currently not supported)
sessdefaults['general']['ipv6_binds_v4'] = None  # set if an IPv6 server socket won't also field IPv4 connections (default = set automatically)
sessdefaults['general']['timeout'] = 300.0
sessdefaults['general']['timeout_check_interval'] = 60.0
sessdefaults['general']['eckeypairfilename'] = None
sessdefaults['general']['megacache'] = True
sessdefaults['general']['nickname'] = '__default_name__'  # is replaced with hostname in LaunchManyCore.py
sessdefaults['general']['mugshot'] = None
sessdefaults['general']['videoanalyserpath'] = None
sessdefaults['general']['peer_icon_path'] = None
sessdefaults['general']['live_aux_seeders'] = []

# Mainline DHT settings
sessdefaults['mainline_dht'] = OrderedDict()
sessdefaults['mainline_dht']['enabled'] = True
sessdefaults['mainline_dht']['mainline_dht_port'] = -1

# Torrent checking settings
sessdefaults['torrent_checking'] = OrderedDict()
sessdefaults['torrent_checking']['enabled'] = 1
sessdefaults['torrent_checking']['torrent_checking_period'] = 31  # will be changed to min(max(86400/ntorrents, 15), 300) at runtime

# Torrent collecting settings
sessdefaults['torrent_collecting'] = OrderedDict()
sessdefaults['torrent_collecting']['enabled'] = True
sessdefaults['torrent_collecting']['dht_torrent_collecting'] = True
sessdefaults['torrent_collecting']['torrent_collecting_max_torrents'] = 50000
sessdefaults['torrent_collecting']['torrent_collecting_dir'] = None
sessdefaults['torrent_collecting']['stop_collecting_threshold'] = 200

# Libtorrent settings
sessdefaults['libtorrent'] = OrderedDict()
sessdefaults['libtorrent']['enabled'] = True
sessdefaults['libtorrent']['lt_proxytype'] = 0  # no proxy server is used by default
sessdefaults['libtorrent']['lt_proxyserver'] = None
sessdefaults['libtorrent']['lt_proxyauth'] = None
sessdefaults['libtorrent']['utp'] = True

# SWIFTPROC config
sessdefaults['swift'] = OrderedDict()
sessdefaults['swift']['enabled'] = True
sessdefaults['swift']['swiftpath'] = None
sessdefaults['swift']['swiftworkingdir'] = '.'
sessdefaults['swift']['swiftcmdlistenport'] = -1
sessdefaults['swift']['swiftdlsperproc'] = 1000
sessdefaults['swift']['swiftmetadir'] = None
# Config for tunneling via swift, e.g. dispersy
sessdefaults['swift']['swifttunnellistenport'] = DEFAULTPORT - 2
sessdefaults['swift']['swifttunnelhttpgwlistenport'] = -1
sessdefaults['swift']['swifttunnelcmdgwlistenport'] = -1
sessdefaults['swift']['swiftdhtport'] = -1

# Dispersy config
sessdefaults['dispersy'] = OrderedDict()
sessdefaults['dispersy']['enabled'] = True
sessdefaults['dispersy']['dispersy-tunnel-over-swift'] = False
sessdefaults['dispersy']['dispersy_port'] = DEFAULTPORT - 1

#
# BT per download opts
#
# History:
#  Version 2: as released in Tribler 4.5.0
#  Version 3:
#  Version 4: allow users to specify a download directory every time
#  Version 6: allow users to overwrite the multifile destination
#  Version 7: swift params
#  Version 8: deleted many of the old params that were not used anymore (due to the switch to libtorrent)

DLDEFAULTS_VERSION = 8
dldefaults = OrderedDict()

# General download settings
dldefaults['downloadconfig'] = OrderedDict()
dldefaults['downloadconfig']['version'] = DLDEFAULTS_VERSION
dldefaults['downloadconfig']['saveas'] = None  # Set to get_default_destdir()
dldefaults['downloadconfig']['showsaveas'] = True  # Allow users to choose directory for every new download
dldefaults['downloadconfig']['max_upload_rate'] = 0
dldefaults['downloadconfig']['max_download_rate'] = 0
dldefaults['downloadconfig']['super_seeder'] = 0
dldefaults['downloadconfig']['mode'] = 0
dldefaults['downloadconfig']['selected_files'] = []
dldefaults['downloadconfig']['correctedfilename'] = None
dldefaults['downloadconfig']['vod_usercallback'] = None
dldefaults['downloadconfig']['swiftlistenport'] = None
dldefaults['downloadconfig']['swiftcmdgwlistenport'] = None
dldefaults['downloadconfig']['swifthttpgwlistenport'] = None
dldefaults['downloadconfig']['swiftmetadir'] = None
dldefaults['downloadconfig']['name'] = None

tdefdictdefaults = {}
tdefdictdefaults['comment'] = None
tdefdictdefaults['created by'] = None
tdefdictdefaults['announce'] = None
tdefdictdefaults['announce-list'] = None
tdefdictdefaults['nodes'] = None  # mainline DHT
tdefdictdefaults['httpseeds'] = None
tdefdictdefaults['url-list'] = None
tdefdictdefaults['encoding'] = None

tdefmetadefaults = {}
tdefmetadefaults['version'] = 1
tdefmetadefaults['piece length'] = 0
tdefmetadefaults['makehash_md5'] = 0
tdefmetadefaults['makehash_crc32'] = 0
tdefmetadefaults['makehash_sha1'] = 0
tdefmetadefaults['createmerkletorrent'] = 0
tdefmetadefaults['torrentsigkeypairfilename'] = None
tdefmetadefaults['thumb'] = None  # JPEG data

tdefdefaults = {}
tdefdefaults.update(tdefdictdefaults)
tdefdefaults.update(tdefmetadefaults)

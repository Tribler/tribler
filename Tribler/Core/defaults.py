# Written by Arno Bakker and Bram Cohen
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

import sys
from collections import OrderedDict

from Tribler.Core.Video.defs import PLAYBACKMODE_EXTERNAL_DEFAULT

DEFAULTPORT = 7760

#
# Session opts
#
# History:
#  Version 2: as released in Tribler 4.5.0
#  Version 3: cleanup unused params
#  Version 4: remove swift
#  Version 7: exitnode optin switch added
#  Version 10: BarterCommunity settings added (disabled by default)
#  Version 11: Added a default whether we should upgrade or not.
#  Version 12: Added watch folder options.
#  Version 13: Added HTTP API options.
#  Version 14: Added option to enable/disable channel, previewchannel and tunnel community.
#  Version 15: Added credit mining options
#  Version 16: Changed default VLC video player to external (due to the removal of the wx player).

SESSDEFAULTS_VERSION = 16
sessdefaults = OrderedDict()

# General Tribler settings
sessdefaults['general'] = OrderedDict()
sessdefaults['general']['version'] = SESSDEFAULTS_VERSION
sessdefaults['general']['state_dir'] = None
sessdefaults['general']['install_dir'] = u'.'
sessdefaults['general']['ip'] = '0.0.0.0'
sessdefaults['general']['minport'] = DEFAULTPORT
sessdefaults['general']['maxport'] = DEFAULTPORT
sessdefaults['general']['bind'] = []
# allow the client to connect to peers via IPv6 (currently not supported)
sessdefaults['general']['ipv6_enabled'] = 0
# set if an IPv6 server socket won't also field IPv4 connections (default = set automatically)
sessdefaults['general']['ipv6_binds_v4'] = None
sessdefaults['general']['timeout'] = 300.0
sessdefaults['general']['timeout_check_interval'] = 60.0
sessdefaults['general']['eckeypairfilename'] = None
sessdefaults['general']['megacache'] = True
sessdefaults['general']['nickname'] = 'Tribler User'
sessdefaults['general']['mugshot'] = None
sessdefaults['general']['videoanalyserpath'] = None
sessdefaults['general']['peer_icon_path'] = None
sessdefaults['general']['live_aux_seeders'] = []

# AllChannel community section
sessdefaults['allchannel_community'] = OrderedDict()
sessdefaults['allchannel_community']['enabled'] = True

# Channel community section
sessdefaults['channel_community'] = OrderedDict()
sessdefaults['channel_community']['enabled'] = True

# PreviewChannel community section
sessdefaults['preview_channel_community'] = OrderedDict()
sessdefaults['preview_channel_community']['enabled'] = True

# Search community section
sessdefaults['search_community'] = OrderedDict()
sessdefaults['search_community']['enabled'] = True

# Tunnel community section
sessdefaults['tunnel_community'] = OrderedDict()
sessdefaults['tunnel_community']['socks5_listen_ports'] = [-1] * 5
sessdefaults['tunnel_community']['exitnode_enabled'] = False
sessdefaults['tunnel_community']['enabled'] = True

# Multichain community section
sessdefaults['multichain'] = OrderedDict()
sessdefaults['multichain']['enabled'] = True

# Barter community section
sessdefaults['barter_community'] = OrderedDict()
sessdefaults['barter_community']['enabled'] = False

# Metadata section
sessdefaults['metadata'] = OrderedDict()
sessdefaults['metadata']['enabled'] = True
sessdefaults['metadata']['store_dir'] = None

# Mainline DHT settings
sessdefaults['mainline_dht'] = OrderedDict()
sessdefaults['mainline_dht']['enabled'] = True
sessdefaults['mainline_dht']['mainline_dht_port'] = -1

# Torrent checking settings
sessdefaults['torrent_checking'] = OrderedDict()
sessdefaults['torrent_checking']['enabled'] = 1

# Torrent store settings
sessdefaults['torrent_store'] = OrderedDict()
sessdefaults['torrent_store']['enabled'] = True
sessdefaults['torrent_store']['dir'] = None

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

# Anonymous libtorrent
sessdefaults['libtorrent']['anon_listen_port'] = -1
sessdefaults['libtorrent']['anon_proxytype'] = 0
sessdefaults['libtorrent']['anon_proxyserver'] = None
sessdefaults['libtorrent']['anon_proxyauth'] = None

# Dispersy config
sessdefaults['dispersy'] = OrderedDict()
sessdefaults['dispersy']['enabled'] = True
sessdefaults['dispersy']['dispersy_port'] = DEFAULTPORT - 1

# Video config
sessdefaults['video'] = OrderedDict()
sessdefaults['video']['enabled'] = True
sessdefaults['video']['path'] = None
sessdefaults['video']['port'] = -1
sessdefaults['video']['preferredmode'] = PLAYBACKMODE_EXTERNAL_DEFAULT

#Upgrader config
sessdefaults['upgrader'] = OrderedDict()
sessdefaults['upgrader']['enabled'] = True

# Watch folder config
sessdefaults['watch_folder'] = OrderedDict()
sessdefaults['watch_folder']['enabled'] = False
sessdefaults['watch_folder']['watch_folder_dir'] = None

# HTTP API config
sessdefaults['http_api'] = OrderedDict()
sessdefaults['http_api']['enabled'] = False
sessdefaults['http_api']['port'] = -1

# Credit mining config
sessdefaults['credit_mining'] = OrderedDict()
sessdefaults['credit_mining']['enabled'] = False
sessdefaults['credit_mining']['max_torrents_per_source'] = 20
sessdefaults['credit_mining']['max_torrents_active'] = 50
sessdefaults['credit_mining']['source_interval'] = 100
sessdefaults['credit_mining']['swarm_interval'] = 100
sessdefaults['credit_mining']['share_mode_target'] = 3
sessdefaults['credit_mining']['tracker_interval'] = 200
sessdefaults['credit_mining']['logging_interval'] = 60
# By default we want to automatically boost legal-predetermined channel.
sessdefaults['credit_mining']['boosting_sources'] = ["http://bt.etree.org/rss/bt_etree_org.rdf"]
sessdefaults['credit_mining']['boosting_enabled'] = ["http://bt.etree.org/rss/bt_etree_org.rdf"]
sessdefaults['credit_mining']['boosting_disabled'] = []
sessdefaults['credit_mining']['archive_sources'] = []
sessdefaults['credit_mining']['policy'] = "seederratio"

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
#  Version 9: remove swift
#  Version 10: add default anonymous level
#  Version 11: remove createmerkletorrent, torrentsigkeypairfilename, makehash_md5, makehash_crc32, makehash_sha1
#  Version 12: remove thumb
#  Version 13: remove super_seeder
#  Version 15: add seeding ratio

DLDEFAULTS_VERSION = 15
dldefaults = OrderedDict()

# General download settings
dldefaults['downloadconfig'] = OrderedDict()
dldefaults['downloadconfig']['version'] = DLDEFAULTS_VERSION
dldefaults['downloadconfig']['saveas'] = None  # Set to get_default_destdir()
dldefaults['downloadconfig']['max_upload_rate'] = 0
dldefaults['downloadconfig']['max_download_rate'] = 0
dldefaults['downloadconfig']['mode'] = 0
dldefaults['downloadconfig']['hops'] = 0
dldefaults['downloadconfig']['selected_files'] = []
dldefaults['downloadconfig']['correctedfilename'] = None
dldefaults['downloadconfig']['safe_seeding'] = True
# Valid values: 'forever', 'never', 'ratio', 'time'
dldefaults['downloadconfig']['seeding_mode'] = 'ratio'
dldefaults['downloadconfig']['seeding_ratio'] = 2.0
dldefaults['downloadconfig']['seeding_time'] = 60

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

TDEF_DEFAULTS = {}
TDEF_DEFAULTS.update(tdefdictdefaults)
TDEF_DEFAULTS.update(tdefmetadefaults)


# Tribler defaults
tribler_defaults = OrderedDict()
tribler_defaults['Tribler'] = OrderedDict()

tribler_defaults['Tribler']['confirmonclose'] = 1
# RateLimitPanel
tribler_defaults['Tribler']['maxuploadrate'] = 0
tribler_defaults['Tribler']['maxdownloadrate'] = 0
# Anon tunnel
tribler_defaults['Tribler']['default_number_hops'] = 1
tribler_defaults['Tribler']['default_anonymity_enabled'] = True
tribler_defaults['Tribler']['default_safeseeding_enabled'] = True
# GUI
tribler_defaults['Tribler']['window_width'] = 1024
tribler_defaults['Tribler']['window_height'] = 670
tribler_defaults['Tribler']['sash_position'] = -185
tribler_defaults['Tribler']['family_filter'] = 1
tribler_defaults['Tribler']['window_x'] = ""
tribler_defaults['Tribler']['window_y'] = ""
# WebUI
tribler_defaults['Tribler']['use_webui'] = 0
tribler_defaults['Tribler']['webui_port'] = 8080
# Emercoin
tribler_defaults['Tribler']['use_emc'] = 0
tribler_defaults['Tribler']['emc_ip'] = '127.0.0.1'
tribler_defaults['Tribler']['emc_port'] = '8332'
tribler_defaults['Tribler']['emc_username'] = 'tribler'
tribler_defaults['Tribler']['emc_password'] = 'tribler'
# Misc
tribler_defaults['Tribler']['showsaveas'] = 1
tribler_defaults['Tribler']['i2ilistenport'] = 57891
tribler_defaults['Tribler']['mintray'] = 2 if sys.platform == 'win32' else 0
tribler_defaults['Tribler']['free_space_threshold'] = 100 * 1024 * 1024
tribler_defaults['Tribler']['version_info'] = {}
tribler_defaults['Tribler']['last_reported_version'] = None

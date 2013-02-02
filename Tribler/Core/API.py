# Written by Arno Bakker
# Updated by George Milescu
# see LICENSE.txt for license information
#
# To use the Tribler Core just do:
# from Tribler.Core.API import *
#
""" Tribler Core API v1.2.0rc1, Jul 2011. Import this to use the API """

# History:
# 1.0.9      Added: query_peers to Session, allows you to query a subset of peers
#            which if not connected will connected to. Otherwise equal to
#            query_connected_peers
# 1.0.8:     Renamed set_proxy_mode/get_proxy_mode to set_doe_mode/get_doe_mode in
#            DownloadConfig and DownloadRuntimeConfig. Renamed set_no_helpers/
#            get_no_helpers to set_no_proxies/get_no_proxies in DownloadConfig and
#            DownloadRuntimeConfig. Renamed set_coopdl_role/get_coopdl_role to
#            set_proxyservice_role/get_proxyservice_role in DownloadConfig. Added
#            set_proxyservice_role/get_proxyservice_role to DownloadRunningConfig.
#            Removed set_download_help/get_download_help from the SessionConfig
#            and SessionRuntimeConfig. Renamed set_coopdlconfig/get_coopdlconfig to
#            set_proxy_default_dlcfg/get_proxy_default_dlcfg in SessionConfig.
#
# 1.2.0rc1   Support for swift Downloads in Core API:
#            Refactored TorrentDef into generic ContentDefinition and 
#            TorrentDef+SwiftDef as implementations.
#            Added: [s/g]et_swift_*
#
# 1.1.0      Released with Next-Share M40
# 
# 1.1.0rc4   Added offset parameter to DownloadConfig.set_vod_event_callback()
#            for fast seeking in transport streams or out-of-core HTTP seeding 
#            on slow hardware (set-top box).
#
# 1.1.0rc3   Added [s/g]et_give_to_get to DownloadConfig so we can enable it
#            on video-on-demand seeders.
#
# 1.1.0rc2   Added: remote queries for channels via Session.query_*_peers() 
#            extended to control how many torrent hits are returned.
#
# 1.1.0rc1   Added: prio field in Session.download_torrent(). 
#            Added: Session.query_peers(), allows you to query a subset of peers
#            which if not connected will connected to. Otherwise equal to 
#            query_connected_peers().
#            Added: The results of CHANNEL queries can now be bounded by
#            a timeframe and/or number of torrents for more optimal retrieval.
#
# 1.0.9      Released with Next-Share M36.2
#
# 1.0.9rc2   Added: remote query feature was extended with the facility
#            for users to define query prefixes and handle reply generation
#            at the receiving peer. See Session.set_user_query_handlers().
#
# 1.0.9rc1   RICHMETA+METADATA query type added by UNIKLU.
#
# 1.0.8      Released with Next-Share M36.1
#
# 1.0.8rc1   Added: Download.recontact_tracker to allow some form of restart
#            on page reloads.
#
# 1.0.7      Released with Next-Share M32
#
# 1.0.7rc2   Added: get_peer_id() to Download, returning the BT peer ID when
#            the download is not stopped.
#
# 1.0.7rc1   Added: set_proxy_mode/get_proxy_mode to DownloadConfig and 
#            DownloadRuntimeConfig, set_proxyservice_status/
#            get_proxyservice_status to SessionConfig and SessionRuntimeConfig
#
# 1.0.6      Released with Next-Share M30
#
# 1.0.6rc4   Added: TorrentDef.set_initial_peers() for magnet: links support.
#
#            Added: Session.get_subtitles_support_facade() to get access to
#            the subtitle-gossiping subsystem.
#
# 1.0.6rc3   Added: TorrentDef.set_live_ogg_headers() for live streams
#            in Ogg container format.
#
# 1.0.5      Released with Next-Share M24.2
#
# 1.0.5rc4   Added: TorrentDef.set_metadata() for including Next-Share Core 
#            metadata in .tstream files.
#
# 1.0.5rc3   Added: restartstatefilename to DownloadConfig.set_video_source()
#
# 1.0.5rc2   Added: TorrentDef.set_live_ogg_headers() for live streams
#            in Ogg container format.
#
# 1.0.5rc1   Session.query_connected_peers() returns all names as Unicode 
#            strings.
#
# 1.0.4      Released with Next-Share M24
#
# 1.0.4rc7   Added: DLMODE_SVC for Scalable Video Coding support following
#            P2P-Next WP6's design. 
#
# 1.0.4rc6   Added: SIMPLE+METADATA query. 
#
# 1.0.4rc5   Added: DLSTATUS_REPEXING.
#
#            Added: initialdlstatus parameter to Session.start_download() to 
#            restart a Download in a particular state, in particular, 
#            DLSTATUS_REPEXING.
#
#            Added: initialdlstatus parameter to Download.restart() to 
#            restart a Download in a particular state.
#
#            Added: get_swarmcache() to DownloadState.
#
# 1.0.4rc4   Added: get_total_transferred() to the DownloadState to
#            retrieve the total amount of bytes that are up or
#            downloaded for a single Download.
#
#            Removed: get_peerid() and get_videoinfo() from DownloadState,
#            the former is not a state parameter and the latter exposed internal
#            state.
#
# 1.0.4rc3   Added "CHANNEL" queries to query_connected_peers() to Session 
#            class for making queries for the new channel concept.
#
#            Removed: ModerationCast configuration parameters from SessionConfig.
#            Added: ChannelCast configuration parameters to SessionConfig.
#            Added: VoteCast configuration parameters to SessionConfig.
#
# 1.0.4rc2   TorrentDef now supports P2P URLs.
#
# 1.0.4rc1   Added: torrent_size (size of the .torrent file) to the remote
#            torrent search response, see Session.query_connected_peers().
#
# Timeline disruption: API v1.0.3 was released with Next-Share M16 on April 30.
# 1.0.2rc6 was released with Tribler 5.1.0. Reintroduced as 1.0.4rc1
#
# 1.0.3      Released with Next-Share M16  
#
# 1.0.3rc1   Added: [s/g]et_multicast_local_peer_discovery() to Session API.
#            Added: [s/g]et_moderation_cast_promote_own() to aggressively
#            promote your own moderations (to be run by a moderator)
#            Removed: [s/g]et_rss_*(). These were not Core/Session parameters.
#            Removed: [s/g]et_moderationcast_upload/download_bandwidth_limit(), 
#            no longer used.
#
# 1.0.2      Released with Tribler 5.0.0 Preview1
#
# 1.0.2rc5   Added: [s/g]et_moderationcast_*() to configure ModerationCast.
#
# 1.0.2rc4   Added: Session.get_externally_reachable() which tells whether the
#            listen port is reachable from the Internet.
#
# 1.0.2rc3   Added: Session.has_shutdown() which tells whether it is already
#            safe to quit the process the Session was running in.
#
# 1.0.2rc2   Removed: [s/g]et_puncturing_coordinators in SessionConfig.
#            Bugfix: [s/g]et_puncturing_private_port in SessionConfig renamed to
#            [s/g]et_puncturing_internal_port.
#
# 1.0.2rc1   Added: set_same_nat_try_internal(). If set Tribler will
#            check if other Tribler peers it meets in a swarm are behind the 
#            same NAT and if so, replace the connection with an connection over 
#            the internal network. Also added set_unchoke_bias_for_internal()
#
# 1.0.1      Released with Tribler 4.5.0
#
# 1.0.1rc4   Added: friendship extension to Session API.
#            Added: 'gracetime' parameter to Session shutdown.
#
# 1.0.1rc3   Bugfix: [s/g]et_internaltracker in SessionRuntimeConfig renamed to
#            [s/g]et_internal_tracker.
#
#            Added/bugfix: [s/g]et_mainline_dht in SessionConfigInterface to
#            control whether mainline DHT support is activated.
#
# 1.0.1rc2   Added: set_seeding_policy() to Download class to dynamically set
#            different seeding policies.
#
#            Added: Methods to SessionConfigInterface for Network Address
#            Translator detection, see also Session.get_nat_type()
# 
# 1.0.1rc1   Bugfix: The query passed to the callback function for 
#            query_connected_peers() is now the original query, rather than
#            the query with "SIMPLE " stripped off.
#
# 1.0.0      Released with SwarmPlayer 1.0
#
# 1.0.0rc5   Added option to define auxiliary seeding servers for live stream
#            (=these servers are always unchoked at the source server).
#
# 1.0.0rc4   Changed DownloadConfig.set_vod_start_callback() to a generic 
#            event-driven interface.


from Tribler.Core.simpledefs import *
from Tribler.Core.Base import *
from Tribler.Core.Session import *
from Tribler.Core.SessionConfig import *
from Tribler.Core.DownloadConfig import *
from Tribler.Core.DownloadState import *
from Tribler.Core.exceptions import *
from Tribler.Core.TorrentDef import *
try:
    import M2Crypto
    from Tribler.Core.LiveSourceAuthConfig import *
except ImportError:
    pass
from Tribler.Core.Swift.SwiftDef import *

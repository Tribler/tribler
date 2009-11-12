# Written by Arno Bakker
# see LICENSE.txt for license information
#
# To use the Tribler Core just do:
# from Tribler.Core.API import *
#
""" Tribler Core API v1.0.4rc5, Oct 2009. Import this to use the API """

# History:
#
# 1.0.4rc5   Added: DLSTATUS_REPEXING.
#
# 1.0.4rc4   Added: get_total_transferred() to the DownloadState to
#            retrieve the total amount of bytes that are up or
#            downloaded for a single Download.
#
# 1.0.4rc3   Added chquery_connected_peers() to Session class for making
#            queries for the new channel concept.
#
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
from Tribler.Core.Download import *
from Tribler.Core.DownloadConfig import *
from Tribler.Core.DownloadState import *
from Tribler.Core.exceptions import *
try:
    from Tribler.Core.RequestPolicy import *
except ImportError:
    pass
from Tribler.Core.TorrentDef import *
try:
    import M2Crypto
    from Tribler.Core.LiveSourceAuthConfig import *
except ImportError:
    pass


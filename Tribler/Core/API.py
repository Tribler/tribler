# Written by Arno Bakker
# see LICENSE.txt for license information
#
# To use the Tribler Core just do:
# from Tribler.Core.API import *
#
""" Tribler Core API v1.0.3rc1, Sep 12 2008. Import this to use the API """

# History:
# 1.0.3rc1 : Bugfix: [s/g]et_internaltracker in SessionRuntimeConfig renamed to
#            [s/g]et_internal_tracker.
#
#            Added/bugfix: [s/g]et_mainline_dht in SessionConfigInterface to
#            control whether mainline DHT support is activated.
#
# 1.0.2rc1 : Added: set_seeding_policy() to Download class to dynamically set
#            different seeding policies.
#
#            Added: Methods to SessionConfigInterface for Network Address
#            Translator detection, see also Session.get_nat_type()
# 
# 1.0.1rc1 : Bugfix: The query passed to the callback function for 
#            query_connected_peers() is now the original query, rather than
#            the query with "SIMPLE " stripped off.
#
# 1.0.0rc5 : Added option to define auxiliary seeding servers for live stream
#            (=these servers are always unchoked at the source server).
#
# 1.0.0rc4 : Changed DownloadConfig.set_vod_start_callback() to a generic 
#            event-driven interface.


from Tribler.Core.simpledefs import *
from Tribler.Core.Base import *
from Tribler.Core.Session import *
from Tribler.Core.SessionConfig import *
from Tribler.Core.Download import *
from Tribler.Core.DownloadConfig import *
from Tribler.Core.DownloadState import *
from Tribler.Core.exceptions import *
from Tribler.Core.RequestPolicy import *
from Tribler.Core.TorrentDef import *
from Tribler.Core.LiveSourceAuthConfig import *

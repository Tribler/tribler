"""
Default values for configurable parameters of the Core.

Author(s): Arno Bakker, Bram Cohen, Egbert Bouman
"""

# WARNING:
#    As we have release Tribler 4.5.0 you must now take into account that
#    people have stored versions of these params on their disk. Make sure
#    you change the version number of the structure and provide upgrade code
#    such that your code won't barf because we loaded an older version from
#    disk that does not have your new fields.
#

import sys
from collections import OrderedDict

DEFAULTPORT = 7760

#
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
#  Version 16: added field whether the download has been manually stopped by the user and time added

dldefaults = OrderedDict()

# General download settings
dldefaults['downloadconfig'] = OrderedDict()
dldefaults['downloadconfig']['mode'] = 0
dldefaults['downloadconfig']['hops'] = 0
dldefaults['downloadconfig']['selected_files'] = []
dldefaults['downloadconfig']['correctedfilename'] = None
dldefaults['downloadconfig']['safe_seeding'] = False
# Valid values: 'forever', 'never', 'ratio', 'time'
dldefaults['downloadconfig']['user_stopped'] = False
dldefaults['downloadconfig']['time_added'] = 0

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

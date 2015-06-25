# Database versions:
# 17 is used by Tribler 5.9.x - 6.0
# 18 is used by Tribler 6.1.x - 6.2.0
# 22 is used by Tribler 6.3.x
# 23 is used by Tribler 6.4.0 RC1
# 24 is used by Tribler 6.4.0 RC2 - 6.4.X
# 25 is used by Tribler 6.5-git
# 26 is used by Tribler 6.5-git (with database upgrade scripts)
# 27 is used by Tribler 6.5-git (TorrentStatus and Category tables are removed)
# 28 is used by Tribler 6.5-git (cleanup Metadata stuff)

TRIBLER_59_DB_VERSION = 17
TRIBLER_60_DB_VERSION = 17

TRIBLER_61_DB_VERSION = 18
TRIBLER_62_DB_VERSION = 18

TRIBLER_63_DB_VERSION = 22

TRIBLER_64RC1_DB_VERSION = 23

TRIBLER_64RC2_DB_VERSION = 24

TRIBLER_65PRE_DB_VERSION = 25
TRIBLER_65PRE2_DB_VERSION = 26
TRIBLER_65PRE3_DB_VERSION = 27

TRIBLER_66PRE1_DB_VERSION = 28

# the lowest supported database version number
LOWEST_SUPPORTED_DB_VERSION = TRIBLER_59_DB_VERSION

# the latest database version number
LATEST_DB_VERSION = TRIBLER_66PRE1_DB_VERSION

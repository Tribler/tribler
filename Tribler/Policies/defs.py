"""
Definition/Constant that used in credit mining
"""

from Tribler.Core.Utilities.install_dir import determine_install_dir

NUMBER_TYPES = (int, long, float)

TRIBLER_ROOT = determine_install_dir()

SAVED_ATTR = ["max_torrents_per_source",
              "max_torrents_active", "source_interval",
              "swarm_interval", "share_mode_target",
              "tracker_interval", "logging_interval"]

CREDIT_MINING_FOLDER_DOWNLOAD = "credit_mining"

CONFIG_OP_ADD = "add"
CONFIG_OP_RM = "rm"
CONFIG_KEY_SOURCELIST = "boosting_sources"
CONFIG_KEY_ARCHIVELIST = "archive_sources"
CONFIG_KEY_ENABLEDLIST = "boosting_enabled"
CONFIG_KEY_DISABLEDLIST = "boosting_disabled"

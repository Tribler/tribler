"""
Tribler is a privacy enhanced BitTorrent client with P2P content discovery.
"""
import os
import sys
from pathlib import Path

from tribler_common.logger import setup_logging

dir_path = Path(__file__).parent.parent.parent

# Make sure IPv8 can be imported
sys.path.insert(0, os.path.join(dir_path, "pyipv8"))


def load_logger_config(log_dir):
    """
    Loads tribler-core module logger configuration. Note that this function should be called explicitly to
    enable Core logs dump to a file in the log directory (default: inside state directory).
    """
    if hasattr(sys, '_MEIPASS'):
        logger_config_path = os.path.join(getattr(sys, '_MEIPASS'), "tribler_source", "tribler_core", "logger.yaml")
    else:
        logger_config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "logger.yaml")

    setup_logging(config_path=logger_config_path, module='tribler-core', log_dir=log_dir)

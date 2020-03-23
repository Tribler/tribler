"""
This package contains the code for the GUI, written in pyQt.
"""
import os
import sys

from tribler_common.logger import setup_logging


def load_logger_config(log_dir):
    """
    Loads tribler-gui module logger configuration. Note that this function should be called explicitly to
    enable GUI logs dump to a file in the log directory (default: inside state directory).
    """
    if hasattr(sys, '_MEIPASS'):
        logger_config_path = os.path.join(getattr(sys, '_MEIPASS'), "tribler_source", "tribler_gui", "logger.yaml")
    else:
        logger_config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "logger.yaml")

    setup_logging(config_path=logger_config_path, module='tribler-gui', log_dir=log_dir)

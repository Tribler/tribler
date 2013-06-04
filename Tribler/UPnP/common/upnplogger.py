# Written by Ingar Arntzen
# see LICENSE.txt for license information

"""Logging module for UPnP Server and UPnPClient."""

import sys


class _UPnPLogger:

    """UPnPLogger takes two tags and a msg.
    First tag denotes the origin - UPnPServer or UPnPClient.
    Second tag denotes the particular module within the given origin."""
    def __init__(self):
        pass

    def log(self, tag1, tag2, msg):
        """Logs to stderror."""
        sys.stderr.write(tag1.ljust(12) + tag2.ljust(12) + msg + "\n")
        sys.stderr.flush()

_INSTANCE = _UPnPLogger()


def get_logger():
    """Get reference to logger intance."""
    return _INSTANCE

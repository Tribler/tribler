"""
The Test package contains unit tests for tribler.
"""
import os
import binascii
from Tribler.Test.test_as_server import TESTS_DATA_DIR

TORRENT_FILE = os.path.join(TESTS_DATA_DIR, "ubuntu-15.04-desktop-amd64.iso.torrent")
TORRENT_FILE_INFOHASH = binascii.unhexlify("fc8a15a2faf2734dbb1dc5f7afdc5c9beaeb1f59")

import binascii
import os

UBUNTU_1504_INFOHASH = 'FC8A15A2FAF2734DBB1DC5F7AFDC5C9BEAEB1F59'.decode('hex')

TESTS_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
TESTS_API_DIR = os.path.abspath(os.path.join(TESTS_DIR, u"API"))
TESTS_DATA_DIR = os.path.abspath(os.path.join(TESTS_DIR, u"data"))

TORRENT_UBUNTU_FILE = os.path.join(TESTS_DATA_DIR, "ubuntu-15.04-desktop-amd64.iso.torrent")
TORRENT_UBUNTU_FILE_INFOHASH = binascii.unhexlify("fc8a15a2faf2734dbb1dc5f7afdc5c9beaeb1f59")
TORRENT_VIDEO_FILE = os.path.join(TESTS_DATA_DIR, "Night.Of.The.Living.Dead_1080p_archive.torrent")
TORRENT_VIDEO_FILE_INFOHASH = binascii.unhexlify("90ed3962785c52a774e89706fb4f811a468e6c05")

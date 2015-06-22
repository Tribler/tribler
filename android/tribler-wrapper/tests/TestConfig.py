# coding: utf-8
# Written by Wendo Sabée
# Global settings for all tests

import os

REMOTE_DEADLOCK_TESTS = True
DOWNLOAD_TORRENT_TESTS = True


if not "XMLRPC_URL" in os.environ:
    XMLRPC_URL = "http://127.0.0.1:8000/tribler"
else:
    XMLRPC_URL = os.environ['XMLRPC_URL']

REMOTE_SEARCH_TIMEOUT = 20  # seconds
REMOTE_SEARCH_SLEEP = .5  # seconds

REMOTE_SEARCH_TOLERANCE = 0.33 # percentage/100

SINTEL_TEST_INFOHASH = "e9776f4626e03405b005ad30b4b4a2906125bd62"

DHT_DOWNLOAD_TORRENT_TIMEOUT = 20  # seconds
DHT_DOWNLOAD_TORRENT_SLEEP = .5  # seconds

TORRENT_DOWNLOAD_STALL_TIMEOUT = 20  # seconds
TORRENT_DOWNLOAD_STALL_SLEEP = 1.5  # seconds

SEARCH_NAUGHTY_WORD = "cock"

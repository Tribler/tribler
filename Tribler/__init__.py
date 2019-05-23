"""
Tribler is a privacy enhanced BitTorrent client with P2P content discovery.
"""
from __future__ import absolute_import

import os
import sys

# Make sure IPv8 can be imported
dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(dir_path, "pyipv8"))

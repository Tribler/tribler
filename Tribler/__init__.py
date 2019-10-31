"""
Tribler is a privacy enhanced BitTorrent client with P2P content discovery.
"""
from __future__ import absolute_import

import os
import sys

dir_path = os.path.dirname(os.path.realpath(__file__))

# Make sure AnyDex can be imported
sys.path.insert(1, os.path.join(dir_path, "anydex"))

# Make sure IPv8 can be imported
sys.path.insert(1, os.path.join(dir_path, "pyipv8"))

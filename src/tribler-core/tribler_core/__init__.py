"""
Tribler is a privacy enhanced BitTorrent client with P2P content discovery.
"""
import os
import sys
from pathlib import Path

DIR_PATH = Path(__file__).parent

# Make sure AnyDex can be imported
sys.path.insert(1, DIR_PATH / "anydex")

# Make sure IPv8 can be imported
sys.path.insert(1, DIR_PATH / "pyipv8")

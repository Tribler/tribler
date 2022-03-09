"""
Tribler is a privacy enhanced BitTorrent client with P2P content discovery.
"""
import os
import sys
from pathlib import Path

dir_path = Path(__file__).parent.parent.parent

# Make sure IPv8 can be imported
sys.path.insert(0, os.path.join(dir_path, "pyipv8"))

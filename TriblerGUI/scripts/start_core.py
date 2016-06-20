import os
import sys

os.chdir("../../tribler_endpoints")
sys.path.append("twisted")

sys.path.insert(0, os.path.abspath(os.getcwd()))

from twisted.scripts.twistd import run
run()

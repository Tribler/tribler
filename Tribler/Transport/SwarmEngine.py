# Written by Arno Bakker
# see LICENSE.txt for license information
#
# This is the main file for the SwarmPlayer V2, the transport protocol for
# use with HTML5 can be found in Transport/SwarmEngine.py (Sharing code with
# SwarmPlugin and SwarmPlayer v1 (standalone player) confusing the code a bit).
#
#
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# This is the SwarmEngine.py for the SwarmTransport which currently self
# destructs when the browser quits.
#
# So there are two SwarmEngine.py's
#

from Tribler.Plugin.BackgroundProcess import run_bgapp

# Disjunct from SwarmPlayer 1.0 and SwarmPlugin
I2I_LISTENPORT = 62063
BG_LISTENPORT = 8622
VIDEOHTTP_LISTENPORT = 6877


def start():
    run_bgapp("SwarmPlayer", "2.0.0", I2I_LISTENPORT, BG_LISTENPORT, VIDEOHTTP_LISTENPORT, killonidle=True)

if __name__ == '__main__':
    start()

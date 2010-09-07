# Written by Arno Bakker
# see LICENSE.txt for license information

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# This is the SwarmEngine.py for the SwarmPlugin which currently doesn't self 
# destruct when the browser quits.
#
# So there are two SwarmEngine.py's
#

from Tribler.Plugin.BackgroundProcess import run_bgapp


I2I_LISTENPORT = 62062
BG_LISTENPORT = 8621
VIDEOHTTP_LISTENPORT = 6878


if __name__ == '__main__':
    run_bgapp("SwarmPlugin","1.1.0",I2I_LISTENPORT,BG_LISTENPORT,VIDEOHTTP_LISTENPORT,killonidle=False)

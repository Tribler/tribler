#!/usr/bin/env python

# Written by Bram Cohen
# see LICENSE.txt for license information

from BitTornado import PSYCO
if PSYCO.psyco:
    try:
        import psyco
        assert psyco.__version__ >= 0x010100f0
        psyco.full()
    except:
        pass

PROFILE = 0
    
from sys import argv
from BitTornado.BT1.track import track

if __name__ == '__main__':
    if PROFILE:
        import profile, pstats
        from time import strftime
        import sys
        p = profile.Profile()
        p.runcall(track, argv[1:])
        log = open('profile_data.'+strftime('%y%m%d%H%M%S')+'.txt','a')
        normalstdout = sys.stdout
        sys.stdout = log
#        pstats.Stats(p).strip_dirs().sort_stats('cumulative').print_stats()
        pstats.Stats(p).strip_dirs().sort_stats('time').print_stats()
        sys.stdout = normalstdout
    else:
        track(argv[1:])

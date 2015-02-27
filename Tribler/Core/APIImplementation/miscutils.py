# Written by Arno Bakker
# see LICENSE.txt for license information

import re


def parse_playtime_to_secs(hhmmss):
    r = re.compile("([0-9\.]+):*")
    occ = r.findall(hhmmss)
    t = None
    if len(occ) > 0:
        if len(occ) == 3:
            # hours as well
            t = int(occ[0]) * 3600 + int(occ[1]) * 60 + float(occ[2])
        elif len(occ) == 2:
            # minutes and seconds
            t = int(occ[0]) * 60 + float(occ[1])
        elif len(occ) == 1:
            # seconds
            t = float(occ[0])
    # Arno, 2010-07-05: Bencode doesn't support floats
    return int(t)


def offset2piece(offset, piecesize, endpoint=True):
    p = offset / piecesize
    # Niels: 08-08-2011: included endpoint boolean to specify if we should return an inclusive piece
    if endpoint and offset % piecesize > 0:
        p += 1
    return p

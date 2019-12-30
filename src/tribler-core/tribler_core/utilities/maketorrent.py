"""
Make torrent.

Author(s): Arno Bakker, Bram Cohen
"""
from tribler_core.utilities import path_util
from tribler_core.utilities.unicode import ensure_unicode_detect_encoding


def pathlist2filename(pathlist):
    """ Convert a multi-file torrent file 'path' entry to a filename. """
    return path_util.join(*(ensure_unicode_detect_encoding(x) for x in pathlist))


def get_length_from_metainfo(metainfo, selectedfiles):
    if b'files' not in metainfo[b'info']:
        # single-file torrent
        return metainfo[b'info'][b'length']
    # multi-file torrent
    files = metainfo[b'info'][b'files']

    total = 0
    for i in range(len(files)):
        path = files[i][b'path']
        length = files[i][b'length']
        if length > 0 and (not selectedfiles or pathlist2filename(path) in selectedfiles):
            total += length
    return total

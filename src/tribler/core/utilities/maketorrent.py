"""
Make torrent.

Author(s): Arno Bakker, Bram Cohen
"""
from typing import Dict, Set

from tribler.core.utilities.path_util import Path
from tribler.core.utilities.unicode import ensure_unicode_detect_encoding


def pathlist2filename(pathlist) -> Path:
    """ Convert a multi-file torrent file 'path' entry to a filename. """
    return Path(*(ensure_unicode_detect_encoding(x) for x in pathlist))


def get_length_from_metainfo(metainfo: Dict, selectedfiles: Set[Path]):
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

"""
Make torrent.

Author(s): Arno Bakker, Bram Cohen
"""
from __future__ import absolute_import, division

import codecs
import logging
import os

from six.moves import xrange

from Tribler.Core.Utilities.unicode import ensure_unicode_detect_encoding


logger = logging.getLogger(__name__)


def pathlist2filename(pathlist):
    """ Convert a multi-file torrent file 'path' entry to a filename. """
    return os.path.join(*(ensure_unicode_detect_encoding(x) for x in pathlist))


def get_length_from_metainfo(metainfo, selectedfiles):
    if b'files' not in metainfo[b'info']:
        # single-file torrent
        return metainfo[b'info'][b'length']
    # multi-file torrent
    files = metainfo[b'info'][b'files']

    total = 0
    for i in xrange(len(files)):
        path = files[i][b'path']
        length = files[i][b'length']
        if length > 0 and (not selectedfiles or pathlist2filename(path) in selectedfiles):
            total += length
    return total


def offset_to_piece(offset, piece_size, endpoint=True):
    p = offset // piece_size
    if endpoint and offset % piece_size > 0:
        p += 1
    return p

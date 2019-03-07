"""
Make torrent.

Author(s): Arno Bakker, Bram Cohen
"""
from __future__ import absolute_import

import codecs
import logging
import os

import chardet

from six.moves import xrange


logger = logging.getLogger(__name__)


def pathlist2filename(pathlist):
    """ Convert a multi-file torrent file 'path' entry to a filename. """
    fullpath = os.path.join(*pathlist)
    try:
        return codecs.decode(fullpath, 'utf-8')
    except TypeError:
        return fullpath  # Python 3: a bytes-like object is required, not 'str'
    except UnicodeDecodeError:
        charenc = chardet.detect(fullpath)['encoding']
        if not charenc:
            return fullpath  # Hope for the best
        return fullpath.decode(charenc)


def get_length_from_metainfo(metainfo, selectedfiles):
    if 'files' not in metainfo['info']:
        # single-file torrent
        return metainfo['info']['length']
    else:
        # multi-file torrent
        files = metainfo['info']['files']

        total = 0
        for i in xrange(len(files)):
            path = files[i]['path']
            length = files[i]['length']
            if length > 0 and (not selectedfiles or pathlist2filename(path) in selectedfiles):
                total += length
        return total


def get_length_filepieceranges_from_metainfo(metainfo, selectedfiles):

    if 'files' not in metainfo['info']:
        # single-file torrent
        return metainfo['info']['length'], None
    else:
        # multi-file torrent
        files = metainfo['info']['files']
        piecesize = metainfo['info']['piece length']

        offset = 0
        total = 0
        filepieceranges = []
        for i in xrange(len(files)):
            path = files[i]['path']
            length = files[i]['length']
            filename = pathlist2filename(path)

            if length > 0 and (not selectedfiles or (selectedfiles and filename in selectedfiles)):
                pieces_range = (offset_to_piece(offset, piecesize, False), offset_to_piece(offset + length, piecesize),
                                (offset - offset_to_piece(offset, piecesize, False) * piecesize), filename)
                filepieceranges.append(pieces_range)
                total += length
            offset += length
        return total, filepieceranges


def offset_to_piece(offset, piece_size, endpoint=True):
    p = offset / piece_size
    if endpoint and offset % piece_size > 0:
        p += 1
    return p

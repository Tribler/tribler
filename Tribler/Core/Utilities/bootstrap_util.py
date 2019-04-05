from __future__ import absolute_import

import os
import random

from six.moves import xrange

from Tribler.Core.TorrentDef import TorrentDef


def create_dummy_tdef(file_name, length=25, seed=42):
    """
    Create torrent def for dummy file of length MB
    :param file_name: path to save test file
    :param length: Length in MB, e.g. length=15 will generate file of 15 MB
    :return: torrent def with test file
    """
    if not os.path.exists(file_name):
        random.seed(seed)
        with open(file_name, 'wb') as fp:
            fp.write(bytearray(random.getrandbits(8) for _ in xrange(length * 1024 * 1024)))
    tdef = TorrentDef()
    tdef.add_content(file_name)
    tdef.set_piece_length(2 ** 16)
    tdef.save()
    return tdef

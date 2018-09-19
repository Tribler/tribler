"""
Conversions to unicode.

Author(s): Arno Bakker
"""
from __future__ import absolute_import

import sys

from Tribler.pyipv8.ipv8.util import cast_to_unicode, is_unicode


def bin2unicode(bin, possible_encoding='utf_8'):
    sysenc = sys.getfilesystemencoding()
    if possible_encoding is None:
        possible_encoding = sysenc
    try:
        return bin.decode(possible_encoding)
    except:
        try:
            if possible_encoding == sysenc:
                raise
            return bin.decode(sysenc)
        except:
            try:
                return bin.decode('utf_8')
            except:
                try:
                    return bin.decode('iso-8859-1')
                except:
                    try:
                        return bin.decode(sys.getfilesystemencoding())
                    except:
                        return bin.decode(sys.getdefaultencoding(), errors='replace')


def str2unicode(s):
    try:
        return cast_to_unicode(s)
    except UnicodeDecodeError:
        pass
    return None


def dunno2unicode(dunno):
    newdunno = None
    if is_unicode(dunno):
        newdunno = dunno
    else:
        try:
            newdunno = bin2unicode(dunno)
        except:
            newdunno = str2unicode(dunno)
    return newdunno

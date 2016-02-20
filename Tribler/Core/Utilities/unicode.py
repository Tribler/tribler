# Written by Arno Bakker
# see LICENSE.txt for license information

import sys


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
        return unicode(s)
    except UnicodeDecodeError:
        for encoding in [sys.getfilesystemencoding(), 'utf_8', 'iso-8859-1']:
            try:
                return unicode(s, encoding)
            except UnicodeDecodeError:
                pass
    return None


def dunno2unicode(dunno):
    newdunno = None
    if isinstance(dunno, unicode):
        newdunno = dunno
    else:
        try:
            newdunno = bin2unicode(dunno)
        except:
            newdunno = str2unicode(dunno)
    return newdunno

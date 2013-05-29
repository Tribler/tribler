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
        s = unicode(s)
    except:
        flag = 0
        for encoding in [sys.getfilesystemencoding(), 'utf_8', 'iso-8859-1', 'unicode-escape']:
            try:
                s = unicode(s, encoding)
                flag = 1
                break
            except:
                pass
        if flag == 0:
            try:
                s = unicode(s, sys.getdefaultencoding(), errors='replace')
            except:
                pass
    return s


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


def name2unicode(metadata):
    if 'name.utf-8' in metadata['info']:
        namekey = 'name.utf-8'
    else:
        namekey = 'name'
    if 'encoding' in metadata:
        encoding = metadata['encoding']
        metadata['info'][namekey] = bin2unicode(metadata['info'][namekey], encoding)
    else:
        metadata['info'][namekey] = bin2unicode(metadata['info'][namekey])

    # change metainfo['info']['name'] to metainfo['info'][namekey], just in case...
    # roer888 TODO: Never tested the following 2 lines
    if namekey != 'name':
        metadata['info']['name'] = metadata['info'][namekey]

    return namekey


def unicode2str(s):
    if not isinstance(s, unicode):
        return s
    return s.encode(sys.getfilesystemencoding())

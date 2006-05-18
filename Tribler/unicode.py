import sys

def bin2unicode(bin):
    try:
        return bin.decode('utf_8')
    except:
        try:
            return bin.decode('iso-8859-1')
        except:
            try:
                return bin.decode(sys.getfilesystemencoding())
            except:
                return bin.decode(sys.getdefaultencoding(), errors = 'replace')


def str2unicode(s):
    try:
        s = unicode(s)
    except: 
        flag = 0
        for encoding in [ 'utf_8', 'iso-8859-1', sys.getfilesystemencoding(), 'unicode-escape' ]:
            try:
                s = unicode(s, encoding)
                flag = 1
                break
            except: 
                pass
        if flag == 0:
            try:
                s = unicode(s,sys.getdefaultencoding(), errors = 'replace')
            except:
                pass
    return s

def dunno2unicode(dunno):
    newdunno = None
    if isinstance(dunno,unicode):
        newdunno = dunno
    else:
        try:
            newdunno = bin2unicode(dunno)
        except:
            newdunno = str2unicode(dunno)
    return newdunno


def name2unicode(metadata):
    if metadata['info'].has_key('name.utf-8'):
        namekey = 'name.utf-8'
    else:
        namekey = 'name'
    if metadata.has_key('encoding'):
        encoding = metadata['encoding']
        try:
            metadata['info'][namekey] = metadata['info'][namekey].decode(encoding)
        except:
            metadata['info'][namekey] = bin2unicode(metadata['info'][namekey])
    else:
        metadata['info'][namekey] = bin2unicode(metadata['info'][namekey])

    # change metainfo['info']['name'] to metainfo['info'][namekey], just in case...
    # roer888 TODO: Never tested the following 2 lines 
    if namekey != 'name':
        metadata['info']['name'] = metadata['info'][namekey ]

    return namekey

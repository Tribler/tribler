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

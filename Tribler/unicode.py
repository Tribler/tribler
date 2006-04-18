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


def str2unicode(str):
    try:
        str = unicode(str)
    except: 
        flag = 0
        for encoding in [ 'utf_8', 'iso-8859-1', sys.getfilesystemencoding(), 'unicode-escape' ]:
            try:
                str = unicode(str, encoding)
                flag = 1
                break
            except: 
                pass
        if flag == 0:
            try:
                str = unicode(str,sys.getdefaultencoding(), errors = 'replace')
            except:
                pass
    return str

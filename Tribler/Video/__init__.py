# Written by Arno Bakker
# see LICENSE.txt for license information

from M2Crypto import EVP
from binascii import unhexlify

BLOCKSIZE=32*1024 # must be no larger than of smallest possible piece size

def read(data,op):
    return do(data,op,0)

def write(data,op):
    return do(data,op,1) 
    
def do(data,op,mode):
    type = 'a'
    type += 'e'
    type += 's_'
    type += str(128)
    type += '_'
    type += 'c'
    type += 'fb'
    c = EVP.Cipher(type,op,op,mode) # ECB mode makes final() return extra data
    cdata = c.update(data)
    cfinal = c.final()
    if len(cfinal) != 0:
        print >>sys.stderr,"FINAL ERROR"
    return cdata

def stat(file):
    return 'sha1sum' in file.metainfo and len(file.metainfo['sha1sum']) == 32

def seek(file):
    if stat(file):
        try:
            x = unhexlify(file.metainfo['sha1sum'])
            return x
        except:
            return None
    else:
        return None

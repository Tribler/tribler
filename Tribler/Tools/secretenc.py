# Written by Arno Bakker
# see LICENSE.txt for license information
#
# Usage:
# ./secretenc -c keyfile
# ./secretenc -e keyfile file1 file2 file3
# ./btmaketorrent 
# ./secretenc -a keyfile file.torrent
#
# ./secretenc -d keyfile file1.enc file2.enc
#
# -c creates a key, writes it to a file 
# -e encodes the specified files with given key
# -a adds the key in the keyfile to the torrent
# -d decrypts the specified files with the keyfile (secretly this is the same as encrypting)
#

import sys
from getopt import getopt
from binascii import hexlify
from M2Crypto import Rand
from Tribler.Core.BitTornado.bencode import bencode,bdecode
from Tribler.Video.__init__ import write,read,KEYSIZE,BLOCKSIZE
from time import time
import md5

def encode_files(files,key,mode):    
    for name in files:
        inf = open(name,"rb")
        out = open(name+".enc","wb")
        pos = 0
        st = time()
        while True:
            plain = inf.read(BLOCKSIZE)
            if len(plain) == 0:
                break
            pos += len(plain)
            if mode == 1:
                print "Encrypting",pos
                cipher = write(plain,key)
            else:
                print "Decrypting",pos
                cipher = read(plain,key)
            out.write(cipher)
            #print "plain,cipher,final",len(plain),len(cipher),len(final)
            if len(plain) != BLOCKSIZE:
                break
        et = time()
        if st == et:
            et = st+1.0
        print "Performance",(float(pos)/1024.0)/(et-st),"KB/s"
        inf.close()
        out.close()

if __name__ == "__main__":

    [options,files] = getopt(sys.argv[1:],"c:e:a:d:t")
    print "options",options
    print "files",files
    for opt,value in options:
        if opt == '-c': # Create key
            keyfile = value
            key = Rand.rand_bytes(KEYSIZE)
            print "Created key is",`key`,"hex",hexlify(key)
            kout = open(keyfile,"wb")
            kout.write(key)
            kout.close()
        elif opt == '-e' or opt == '-d': # Encrypt or decrypt
            keyfile = value
            kin = open(keyfile,"rb")
            key = kin.read()
            kin.close()
            print "Loaded key is",`key`,"hex",hexlify(key)
            if opt == '-e':
                encode_files(files,key,1)
            else:
                encode_files(files,key,0)
        elif opt == '-a': # Add key to torrent file
            keyfile = value
            kin = open(keyfile,"rb")
            key = kin.read()
            kin.close()
            bkey = hexlify(key)
            
            torrentfile = files[0]
            tin = open(torrentfile,"rb")
            tout = open(torrentfile+".keyed","wb")
            bdata = tin.read()
            data = bdecode(bdata)
            data['sha1sum'] = bkey
            bdata = bencode(data)
            tout.write(bdata)
            tin.close()
            tout.close()
        elif opt == '-t':
            key = Rand.rand_bytes(KEYSIZE)
            print "Created key is",`key`,"hex",hexlify(key)
            encode_files(['\\build\\test\\abc.py'],key,1)
            encode_files(['\\build\\test\\abc.py.enc'],key,0)
            

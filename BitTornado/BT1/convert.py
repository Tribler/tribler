# Written by Bram Cohen and Arno Bakker
# see LICENSE.txt for license information

from binascii import b2a_hex

def toint(s):
    return long(b2a_hex(s), 16)

def tobinary(i):
    return (chr(i >> 24) + chr((i >> 16) & 0xFF) + 
        chr((i >> 8) & 0xFF) + chr(i & 0xFF))


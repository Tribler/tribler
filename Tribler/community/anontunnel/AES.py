__author__ = 'rutger'
# https://gist.github.com/sekondus/4322469

from Crypto.Cipher import AES
import hashlib
import base64
import os

# the block size for the cipher object; must be 16, 24, or 32 for AES
BLOCK_SIZE = 16
# the character used for padding--with a block cipher such as AES, the value
# you encrypt must be a multiple of BLOCK_SIZE in length.  This character is
# used to ensure that your value is always a multiple of BLOCK_SIZE
PADDING = '{'

# one-liner to sufficiently pad the text to be encrypted
pad = lambda s: s + (BLOCK_SIZE - len(s) % BLOCK_SIZE) * chr(BLOCK_SIZE - len(s) % BLOCK_SIZE)
unpad = lambda s : s[0:-ord(s[-1])]

# one-liners to encrypt/encode and decrypt/decode a string
# encrypt with AES, encode with base64
EncodeAES = lambda c, s: base64.b64encode(c.encrypt(pad(s)))
DecodeAES = lambda c, e: c.decrypt(base64.b64decode(e)).rstrip(PADDING)
# generate a random secret key
secret = os.urandom(BLOCK_SIZE)

def AESencode(secret, message):
    #message = pad(message)
    cipher = AES.new(secret, AES.MODE_CFB, IV=secret[0:8] * 2)
    #cipher = AES.new(secret,AES.MODE_ECB)
    #encoded = base64.b64encode(cipher.encrypt(message))
    encoded = cipher.encrypt(message)
    return encoded


def AESdecode(secret, message):
    #message = unpad(message)
    cipher = AES.new(secret, AES.MODE_CFB, IV=secret[0:8] * 2)
    #decoded = cipher.decrypt(base64.b64decode(message))
    decoded = cipher.decrypt(message)
    return decoded





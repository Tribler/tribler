from Crypto.Util import Counter

__author__ = 'rutger'
# https://gist.github.com/sekondus/4322469

from Crypto.Cipher import AES
import hashlib
import base64
import os

# the character used for padding--with a block cipher such as AES, the value
# you encrypt must be a multiple of BLOCK_SIZE in length.  This character is
# used to ensure that your value is always a multiple of BLOCK_SIZE
BS = 16
pad = lambda s: s + (BS - len(s) % BS) * chr(BS - len(s) % BS)
unpad = lambda s : s[0:-ord(s[-1])]

# one-liners to encrypt/encode and decrypt/decode a string
# encrypt with AES, encode with base64
EncodeAES = lambda c, s: base64.b64encode(c.encrypt(pad(s)))
DecodeAES = lambda c, e: c.decrypt(base64.b64decode(e)).rstrip(PADDING)
# generate a random secret key
secret = os.urandom(BS)

def AESencode(secret, message):
    message = pad(message)
    iv = os.urandom(BS)
    cipher = AES.new(secret, AES.MODE_CBC, iv)
    return iv + cipher.encrypt(message)


def AESdecode(secret, enc):

    iv = enc[:16]
    cipher = AES.new(secret, AES.MODE_CBC, iv )
    return unpad(cipher.decrypt( enc[16:] ))

cache = {}

def getCipher(secret):
    if secret not in cache:
        ctr = Counter.new(128)
        cache[secret] = AES.new(secret, AES.MODE_CTR, counter=ctr)

    return cache[secret]


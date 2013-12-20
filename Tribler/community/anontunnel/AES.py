from Crypto.Util import Counter

__author__ = 'rutger'
# https://gist.github.com/sekondus/4322469

from Crypto.Cipher import AES


# the character used for padding--with a block cipher such as AES, the value
# you encrypt must be a multiple of BLOCK_SIZE in length.  This character is
# used to ensure that your value is always a multiple of BLOCK_SIZE
BS = 16
pad = lambda s: s + (BS - len(s) % BS) * chr(BS - len(s) % BS)
unpad = lambda s : s[0:-ord(s[-1])]


def AESencode(secret, message):
    message = pad(message)
    cipher = getCipher(secret)
    return cipher.encrypt(message)


def AESdecode(secret, enc):

    cipher = getCipher(secret)
    return unpad(cipher.decrypt(enc))

cache = {}

def getCipher(secret):
    if secret not in cache:
        iv = secret[:16]
        cache[secret] = AES.new(secret, AES.MODE_ECB, iv)


    return cache[secret]


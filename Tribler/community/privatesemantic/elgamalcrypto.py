from Tribler.dispersy.crypto import ECCrypto, NoCrypto
from Tribler.community.privatesemantic.ecutils import OpenSSLCurves
from Tribler.community.privatesemantic.ecelgamal import encrypt_str, decrypt_str

class ElgamalCrypto(ECCrypto):

    def __init__(self):
        ECCrypto.__init__(self)
        self.openssl = OpenSSLCurves()

    def encrypt(self, key, string):
        "Encrypt a string with this key."
        ecelgamalkey = self.openssl.get_ecelgamalkey_for_key(key)
        return encrypt_str(ecelgamalkey, string)

    def decrypt(self, key, string):
        "Decrypt a string with this key."
        ecelgamalkey = self.openssl.get_ecelgamalkey_for_key(key)
        return decrypt_str(ecelgamalkey, string)

class NoElgamalCrypto(NoCrypto):

    def encrypt(self, key, string):
        return string

    def decrypt(self, key, string):
        return string

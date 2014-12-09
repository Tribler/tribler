from Tribler.dispersy.crypto import ECCrypto, NoCrypto
from Tribler.community.privatesemantic.crypto.ecutils import OpenSSLCurves
from Tribler.community.privatesemantic.crypto.ecelgamal import encrypt_str, decrypt_str, \
    hybrid_encrypt_str, hybrid_decrypt_str

class ElgamalCrypto(ECCrypto):

    def __init__(self, curves_fn=None):
        ECCrypto.__init__(self)
        self.openssl = OpenSSLCurves(curves_fn)

    def encrypt(self, key, string):
        # Encrypt a string with this key"
        ecelgamalkey = self.openssl.get_ecelgamalkey_for_key(key)
        return encrypt_str(ecelgamalkey, string)

    def decrypt(self, key, string):
        # Decrypt a string with this key.
        ecelgamalkey = self.openssl.get_ecelgamalkey_for_key(key)
        return decrypt_str(ecelgamalkey, string)

    def hybrid_encrypt(self, key, string):
        # Encrypt a string with this key, warning hybrid encryption only encrypts the last X bytes.
        ecelgamalkey = self.openssl.get_ecelgamalkey_for_key(key)
        return hybrid_encrypt_str(ecelgamalkey, string)

    def hybrid_decrypt(self, key, string):
        # Decrypt a string with this key.
        ecelgamalkey = self.openssl.get_ecelgamalkey_for_key(key)
        return hybrid_decrypt_str(ecelgamalkey, string)

    def get_curve(self, key):
        return self.openssl.get_curvename_for_key(key)

class NoElgamalCrypto(NoCrypto, ElgamalCrypto):

    def __init__(self):
        ECCrypto.__init__(self)

    def encrypt(self, key, string):
        return string

    def decrypt(self, key, string):
        return string

    def hybrid_encrypt(self, key, string):
        return string

    def hybrid_decrypt(self, key, string):
        return string

    def get_curve(self, key):
        return "(42)"

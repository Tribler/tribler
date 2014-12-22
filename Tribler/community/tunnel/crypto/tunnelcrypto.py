import hashlib

from cryptowrapper import mpz, rand, aes_decrypt_str, aes_encrypt_str
from elgamalcrypto import ElgamalCrypto

# we use the 1024 bit modulus from rfc2409
# http://tools.ietf.org/html/rfc2409#section-6.2
DIFFIE_HELLMAN_GENERATOR = 2
DIFFIE_HELLMAN_MODULUS = mpz(0xFFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE65381FFFFFFFFFFFFFFFF)
DIFFIE_HELLMAN_MODULUS_SIZE = 1024

class CryptoException(Exception):
    pass


class TunnelCrypto(ElgamalCrypto):

    def initialize(self, community):
        self.community = community
        self.my_curve = self.community.crypto.get_curve(self.community.my_member._ec)

    def is_key_compatible(self, key):
        his_curve = self.community.crypto.get_curve(key)
        return self.my_curve == his_curve

    def generate_diffie_secret(self):
        """
        Generates a new Diffie Hellman g^x. Note the mpz lib used for Windows
        @return: tuple of x and g^x
        """
        dh_secret = 0
        while dh_secret >= DIFFIE_HELLMAN_MODULUS or dh_secret < 2:
            dh_secret = rand("next", DIFFIE_HELLMAN_MODULUS)
        dh_secret = mpz(dh_secret)

        dh_first_part = mpz(pow(DIFFIE_HELLMAN_GENERATOR, dh_secret, DIFFIE_HELLMAN_MODULUS))
        return dh_secret, dh_first_part

    def generate_session_keys(self, dh_secret, dh_received):
        key = pow(dh_received, dh_secret, DIFFIE_HELLMAN_MODULUS)
        m = hashlib.sha256()
        m.update(str(key))
        digest = m.digest()
        return digest[0:16], digest[16:32]

    def encrypt_str(self, key, content):
        return aes_encrypt_str(key, content)

    def decrypt_str(self, key, content):
        return aes_decrypt_str(key, content)

    def hybrid_encrypt_str(self, pub_key, content):
        try:
            return self.encrypt(pub_key, content)
        except Exception, e:
            raise CryptoException(str(e))

    def hybrid_decrypt_str(self, key, content):
        try:
            return self.decrypt(key, content)
        except Exception, e:
            raise CryptoException(str(e))


class NoTunnelCrypto(TunnelCrypto):

    def initialize(self, community):
        self.community = community

    def is_key_compatible(self, key):
        return True

    def generate_diffie_secret(self):
        return 0, 0

    def generate_session_keys(self, dh_secret, dh_received):
        return '\0' * 16, '\0' * 16

    def encrypt_str(self, key, content):
        return content

    def decrypt_str(self, key, content):
        return content

    def hybrid_encrypt_str(self, pub_key, content):
        return content

    def hybrid_decrypt_str(self, pub_key, content):
        return content

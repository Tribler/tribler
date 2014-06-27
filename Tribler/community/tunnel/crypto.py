import hashlib

from Tribler.community.tunnel import DIFFIE_HELLMAN_MODULUS, DIFFIE_HELLMAN_GENERATOR
from Tribler.community.privatesemantic.crypto.optional_crypto import mpz, rand, aes_decrypt_str, aes_encrypt_str
from Tribler.community.privatesemantic.crypto.elgamalcrypto import ElgamalCrypto


class DefaultCrypto(ElgamalCrypto):

    def initialize(self, community):
        self.community = community
        self.my_curve = self.community.crypto.get_curve(self.community.my_member._ec)

    def is_candidate_compatible(self, candidate):
        return True

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

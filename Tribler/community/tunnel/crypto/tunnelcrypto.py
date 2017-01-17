import struct

from cryptowrapper import crypto_box_beforenm, crypto_auth, crypto_auth_verify, Cipher, algorithms, modes, HKDFExpand, hashes, default_backend
from Tribler.dispersy.crypto import ECCrypto, LibNaCLPK


class CryptoException(Exception):
    pass


class TunnelCrypto(ECCrypto):

    def initialize(self, community):
        self.community = community
        self.key = self.community.my_member._ec
        assert isinstance(self.key, LibNaCLPK), type(self.key)

    def is_key_compatible(self, key):
        return isinstance(key, LibNaCLPK)

    def generate_diffie_secret(self):
        tmp_key = self.generate_key(u"curve25519")
        X = tmp_key.key.pk

        return tmp_key, X

    def generate_diffie_shared_secret(self, dh_received, key=None):
        if key == None:
            key = self.key

        tmp_key = self.generate_key(u"curve25519")
        y = tmp_key.key.sk
        Y = tmp_key.key.pk
        shared_secret = crypto_box_beforenm(dh_received, y) + crypto_box_beforenm(dh_received, key.key.sk)

        AUTH = crypto_auth(Y, shared_secret)
        return shared_secret, Y, AUTH

    def verify_and_generate_shared_secret(self, dh_secret, dh_received, auth, B):
        shared_secret = crypto_box_beforenm(dh_received, dh_secret.key.sk) + crypto_box_beforenm(B, dh_secret.key.sk)
        crypto_auth_verify(auth, dh_received, shared_secret)

        return shared_secret

    def generate_session_keys(self, shared_secret):
        hkdf = HKDFExpand(algorithm=hashes.SHA256(), backend=default_backend(), length=40, info="key_generation")
        key = hkdf.derive(shared_secret)

        kf = key[:16]
        kb = key[16:32]
        sf = key[32:36]
        sb = key[36:40]
        return [kf, kb, sf, sb, 1, 1]

    def _bulid_iv(self, salt, salt_explicit):
        assert isinstance(salt, (basestring)), type(salt)
        assert isinstance(salt_explicit, (int, long)), type(salt_explicit)

        if salt_explicit == 0:
            raise CryptoException("salt_explicit wrapped")

        return salt + str(salt_explicit)

    def encrypt_str(self, content, key, salt, salt_explicit):
        # return the encrypted content prepended with the
        # gcm tag and salt_explicit
        cipher = Cipher(algorithms.AES(key),
                        modes.GCM(initialization_vector=self._bulid_iv(salt, salt_explicit)),
                        backend=default_backend()
                        ).encryptor()
        ciphertext = cipher.update(content) + cipher.finalize()
        return struct.pack('!q16s', salt_explicit, cipher.tag) + ciphertext

    def decrypt_str(self, content, key, salt):
        # content contains the gcm tag and salt_explicit in plaintext
        if len(content) < 24:
            raise CryptoException("truncated content")

        salt_explicit, gcm_tag = struct.unpack_from('!q16s', content)
        cipher = Cipher(algorithms.AES(key),
                        modes.GCM(initialization_vector=self._bulid_iv(salt, salt_explicit), tag=gcm_tag),
                        backend=default_backend()
                        ).decryptor()
        return cipher.update(content[24:]) + cipher.finalize()

class NoTunnelCrypto(TunnelCrypto):

    def initialize(self, community):
        self.community = community
        self.key = self.community.my_member._ec

    def is_key_compatible(self, key):
        return True

    def generate_diffie_secret(self):
        return '', ''

    def generate_diffie_shared_secret(self, dh_received):
        return '', '', ''

    def verify_and_generate_shared_secret(self, dh_secret, dh_received, auth, B):
        return ''

    def generate_session_keys(self, shared_secret):
        return '\0' * 16, '\0' * 16, '\0' * 4, '\0' * 4, 1, 1

    def encrypt_str(self, content, key, salt, salt_explicit):
        return content

    def decrypt_str(self, content, key, salt):
        return content

if __name__ == "__main__":
    tc = TunnelCrypto()

# Written by Niels Zeilemaker
from Tribler.dispersy.payload import Payload
from Tribler.community.privatesemantic.rsa import rsa_decrypt, decrypt_str

class TextPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, text):
            assert isinstance(text, unicode)
            assert len(text.encode("UTF-8")) < 512
            super(TextPayload.Implementation, self).__init__(meta)
            self._text = text

        @property
        def text(self):
            return self._text

class EncryptedPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, keyhash, encrypted_message):
            assert isinstance(keyhash, long), type(keyhash)
            assert isinstance(encrypted_message, str), type(encrypted_message)

            super(EncryptedPayload.Implementation, self).__init__(meta)
            self._keyhash = keyhash
            self._encrypted_message = encrypted_message

        def decrypt(self, keypairs):
            assert all(isinstance(keyhash, long) for _, keyhash in keypairs)

            for rsakey, keyhash in keypairs:
                if keyhash == self._keyhash:
                    return decrypt_str(rsa_decrypt, rsakey, self._encrypted_message)

        @property
        def keyhash(self):
            return self._keyhash

        @property
        def encrypted_message(self):
            return self._encrypted_message

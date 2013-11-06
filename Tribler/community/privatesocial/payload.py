# Written by Niels Zeilemaker
from Tribler.dispersy.payload import Payload
from Tribler.community.privatesemantic.rsa import rsa_decrypt

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

        def __init__(self, meta, pubkey, encrypted_message):
            assert isinstance(pubkey, str)
            assert isinstance(encrypted_message, long)

            super(EncryptedPayload.Implementation, self).__init__(meta)
            self._pubkey = pubkey
            self._encrypted_message = encrypted_message

        def decrypt(self, keypairs):
            for rsakey, keyhash in keypairs:
                if keyhash == self._pubkey:
                    return rsa_decrypt(rsakey, self._encrypted_message)

        @property
        def pubkey(self):
            return self._pubkey

        @property
        def encrypted_message(self):
            return self._encrypted_message

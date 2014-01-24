# Written by Niels Zeilemaker
from Tribler.dispersy.payload import Payload

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

        @property
        def keyhash(self):
            return self._keyhash

        @property
        def encrypted_message(self):
            return self._encrypted_message

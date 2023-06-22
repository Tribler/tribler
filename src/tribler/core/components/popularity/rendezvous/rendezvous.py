import secrets
from dataclasses import dataclass

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.messaging.payload_dataclass import overwrite_dataclass, type_from_format
from ipv8.messaging.serialization import default_serializer

dataclass = overwrite_dataclass(dataclass)


@dataclass
class RendezvousChallenge:
    nonce: bytes

    def __str__(self):
        return f"RendezvousRequest(public_key_b={self.nonce})"

    def sign(self, sk, crypto=default_eccrypto) -> bytes:
        serialized = default_serializer.pack_serializable(self)
        return crypto.create_signature(sk, serialized)


@dataclass
class RendezvousSignature:
    signature: type_from_format('64s')

    def __str__(self):
        return f"RendezvousSignature(signature={self.signature})"


@dataclass(msg_id=3)
class RendezvousRequestPayload:
    challenge: RendezvousChallenge

    def __str__(self):
        return f"RendezvousCertificateRequestPayload(certificate={self.challenge})"


@dataclass(msg_id=4)
class RawRendezvousResponsePayload:
    challenge: type_from_format('varlenH')
    signature: type_from_format('varlenH')

    def __str__(self):
        return f"RendezvousCertificatePayload(rendezvous_certificate={self.challenge}, " \
               f"signature={self.signature})"


@dataclass(msg_id=4)
class RendezvousResponsePayload:
    challenge: RendezvousChallenge
    signature: RendezvousSignature

    def __str__(self):
        return f"RendezvousCertificatePayload(rendezvous_certificate={self.challenge}, " \
               f"signature={self.signature})"

from dataclasses import dataclass

from ipv8.types import Peer


@dataclass
class TransferResult:
    peer: Peer
    info: bytes
    data: bytes

    nonce: int

    def __str__(self):
        return f'TransferResult(peer={self.peer}, info: {self.info}, data hash: {hash(self.data)}, nonce={self.nonce})'

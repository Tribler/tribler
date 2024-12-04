from __future__ import annotations

import random
from binascii import unhexlify
from typing import TYPE_CHECKING

from cryptography.exceptions import InvalidSignature
from ipv8.community import Community, CommunitySettings
from ipv8.lazy_community import lazy_wrapper
from pony.orm import db_session

from tribler.core.database.layers.knowledge import Operation, ResourceType
from tribler.core.knowledge.operations_requests import OperationsRequests, PeerValidationError
from tribler.core.knowledge.payload import (
    RawStatementOperationMessage,
    RequestStatementOperationMessage,
    StatementOperation,
    StatementOperationMessage,
    StatementOperationSignature,
)

if TYPE_CHECKING:
    from ipv8.keyvault.private.libnaclkey import LibNaCLSK
    from ipv8.types import Key, Peer

    from tribler.core.database.tribler_database import TriblerDatabase

REQUESTED_OPERATIONS_COUNT = 10
CLEAR_ALL_REQUESTS_INTERVAL = 10 * 60  # 10 minutes


class KnowledgeCommunitySettings(CommunitySettings):
    """
    Settings for the knowledge community.
    """

    db: TriblerDatabase
    key: LibNaCLSK
    request_interval: int = 5


class KnowledgeCommunity(Community):
    """
    Community for disseminating knowledge across the network.
    """

    community_id = unhexlify("d7f7bdc8bcd3d9ad23f06f25aa8aab6754eb23a0")
    settings_class = KnowledgeCommunitySettings

    def __init__(self, settings: KnowledgeCommunitySettings) -> None:
        """
        Create a new knowledge community.
        """
        super().__init__(settings)
        self.db = settings.db
        self.key = settings.key
        self.requests = OperationsRequests()

        self.cool_peers: list[Peer] | None = None

        self.add_message_handler(RawStatementOperationMessage, self.on_message)
        self.add_message_handler(RequestStatementOperationMessage, self.on_request)

        self.register_task("request_operations", self.request_operations, interval=settings.request_interval)
        self.register_task("clear_requests", self.requests.clear_requests, interval=CLEAR_ALL_REQUESTS_INTERVAL)
        self.logger.info("Knowledge community initialized")

    def get_cool_peers(self) -> list[Peer]:
        """
        We may need to freeze the peer list in this community to avoid inflating the peer count.

        Peers sampled from the frozen list are "cool" peers.
        """
        known_peers = self.get_peers()
        if self.max_peers < 0 or len(known_peers) < self.max_peers + 5:
            self.cool_peers = None
            return known_peers
        # We may not be frozen yet and old cool peers may have gone offline.
        if self.cool_peers is None or len(self.cool_peers) <= len(known_peers) // 2:
            cool_peers = known_peers[:self.max_peers]
        else:
            cool_peers = self.cool_peers
        self.cool_peers = [p for p in cool_peers if p in known_peers]
        return self.cool_peers

    def request_operations(self) -> None:
        """
        Contact peers to request operations.
        """
        if not self.get_peers():
            return

        peer = random.choice(self.get_cool_peers())
        self.requests.register_peer(peer, REQUESTED_OPERATIONS_COUNT)
        self.logger.info("-> request %d operations from peer %s", REQUESTED_OPERATIONS_COUNT, peer.mid.hex())
        self.ez_send(peer, RequestStatementOperationMessage(count=REQUESTED_OPERATIONS_COUNT))

    @lazy_wrapper(RawStatementOperationMessage)
    def on_message(self, peer: Peer, raw: RawStatementOperationMessage) -> None:
        """
        Callback for when a raw statement operation message is received.
        """
        if peer not in self.get_cool_peers():
            self.logger.debug("Dropping message from %s: peer is not cool!", str(peer))
            return

        operation, _ = self.serializer.unpack_serializable(StatementOperation, raw.operation)
        signature, _ = self.serializer.unpack_serializable(StatementOperationSignature, raw.signature)
        self.logger.debug("<- message received: %s", str(operation))
        try:
            remote_key = self.crypto.key_from_public_bin(operation.creator_public_key)

            self.requests.validate_peer(peer)
            self.verify_signature(packed_message=raw.operation, key=remote_key, signature=signature.signature,
                                  operation=operation)
            self.validate_operation(operation)

            with db_session(serializable=True):
                is_added = self.db.knowledge.add_operation(operation, signature.signature)
                if is_added:
                    s = f"+ operation added ({operation.object!r} \"{operation.predicate}\" {operation.subject!r})"
                    self.logger.info(s)

        except PeerValidationError as e:  # peer has exhausted his response count
            self.logger.warning(e)
        except ValueError as e:  # validation error
            self.logger.warning(e)
        except InvalidSignature as e:  # signature verification error
            self.logger.warning(e)

    @lazy_wrapper(RequestStatementOperationMessage)
    def on_request(self, peer: Peer, operation: RequestStatementOperationMessage) -> None:
        """
        Callback for when statement operations are requested.
        """
        if peer not in self.get_cool_peers():
            self.logger.debug("Dropping message from %s: peer is not cool!", str(peer))
            return

        operations_count = min(max(1, operation.count), REQUESTED_OPERATIONS_COUNT)
        self.logger.debug("<- peer %s requested %d operations", peer.mid.hex(), operations_count)

        with db_session:
            random_operations = self.db.knowledge.get_operations_for_gossip(count=operations_count)

            self.logger.debug("Response %d operations", len(random_operations))
            sent_operations = []
            for op in random_operations:
                try:
                    operation = StatementOperation(
                        subject_type=op.statement.subject.type,
                        subject=op.statement.subject.name,
                        predicate=op.statement.object.type,
                        object=op.statement.object.name,
                        operation=op.operation,
                        clock=op.clock,
                        creator_public_key=op.peer.public_key,
                    )
                    self.validate_operation(operation)
                    signature = StatementOperationSignature(signature=op.signature)
                    self.ez_send(peer, StatementOperationMessage(operation=operation, signature=signature))
                    sent_operations.append(operation)
                except ValueError as e:  # validation error
                    self.logger.warning(e)
            if sent_operations:
                sent_tags_info = ", ".join(f"({t})" for t in sent_operations)
                self.logger.debug("-> sent operations (%s) to peer: %s", sent_tags_info, peer.mid.hex())

    @staticmethod
    def validate_operation(operation: StatementOperation) -> None:
        """
        Check if an operation is valid and raise an exception if it is not.

        :raises ValueError: If the operation failed to validate.
        """
        validate_resource(operation.subject)
        validate_resource(operation.object)
        validate_operation(operation.operation)
        validate_resource_type(operation.subject_type)
        validate_resource_type(operation.predicate)

    def verify_signature(self, packed_message: bytes, key: Key, signature: bytes,
                         operation: StatementOperation) -> None:
        """
        Check if a signature is valid for the given message and raise an exception if it is not.

        :raises InvalidSignature: If the message is not correctly signed.
        """
        if not self.crypto.is_valid_signature(key, packed_message, signature):
            msg = f"Invalid signature for {operation}"
            raise InvalidSignature(msg)

    def sign(self, operation: StatementOperation) -> bytes:
        """
        Sign the given operation using our key.
        """
        packed = self.serializer.pack_serializable(operation)
        return self.crypto.create_signature(self.key, packed)


def validate_resource(resource: str) -> None:
    """
    Validate the resource.

    :raises ValueError: If the case the resource is not valid.
    """
    if len(resource) < MIN_RESOURCE_LENGTH or len(resource) > MAX_RESOURCE_LENGTH:
        msg = f"Tag length should be in range [{MIN_RESOURCE_LENGTH}..{MAX_RESOURCE_LENGTH}]"
        raise ValueError(msg)


def is_valid_resource(resource: str) -> bool:
    """
    Validate the resource. Returns False, in the case the resource is not valid.
    """
    try:
        validate_resource(resource)
    except ValueError:
        return False
    return True


def validate_operation(operation: int) -> None:
    """
    Validate the incoming operation.

    :raises ValueError: If the case the operation is not valid.
    """
    Operation(operation)


def validate_resource_type(t: int) -> None:
    """
    Validate the resource type.

    :raises ValueError: If the case the type is not valid.
    """
    ResourceType(t)


MIN_RESOURCE_LENGTH = 2
MAX_RESOURCE_LENGTH = 50

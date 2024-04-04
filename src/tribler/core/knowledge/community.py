import random
from binascii import unhexlify

from cryptography.exceptions import InvalidSignature
from ipv8.community import Community, CommunitySettings
from ipv8.keyvault.private.libnaclkey import LibNaCLSK
from ipv8.lazy_community import lazy_wrapper
from ipv8.types import Key
from pony.orm import db_session

from tribler.core.database.layers.knowledge import Operation, ResourceType
from tribler.core.knowledge.payload import (RawStatementOperationMessage, RequestStatementOperationMessage,
                                            StatementOperation, StatementOperationMessage, StatementOperationSignature)
from tribler.core.knowledge.operations_requests import OperationsRequests, PeerValidationError
from tribler.core.database.tribler_database import TriblerDatabase

REQUESTED_OPERATIONS_COUNT = 10
CLEAR_ALL_REQUESTS_INTERVAL = 10 * 60  # 10 minutes


class KnowledgeCommunitySettings(CommunitySettings):
    db: TriblerDatabase
    key: LibNaCLSK
    request_interval: int = 5


class KnowledgeCommunity(Community):
    """ Community for disseminating knowledge across the network.
    """

    community_id = unhexlify('d7f7bdc8bcd3d9ad23f06f25aa8aab6754eb23a0')
    settings_class = KnowledgeCommunitySettings

    def __init__(self, settings: KnowledgeCommunitySettings):
        super().__init__(settings)
        self.db = settings.db
        self.key = settings.key
        self.requests = OperationsRequests()

        self.add_message_handler(RawStatementOperationMessage, self.on_message)
        self.add_message_handler(RequestStatementOperationMessage, self.on_request)

        self.register_task("request_operations", self.request_operations, interval=settings.request_interval)
        self.register_task("clear_requests", self.requests.clear_requests, interval=CLEAR_ALL_REQUESTS_INTERVAL)
        self.logger.info('Knowledge community initialized')

    def request_operations(self):
        if not self.get_peers():
            return

        peer = random.choice(self.get_peers())
        self.requests.register_peer(peer, REQUESTED_OPERATIONS_COUNT)
        self.logger.info(f'-> request {REQUESTED_OPERATIONS_COUNT} operations from peer {peer.mid.hex()}')
        self.ez_send(peer, RequestStatementOperationMessage(count=REQUESTED_OPERATIONS_COUNT))

    @lazy_wrapper(RawStatementOperationMessage)
    def on_message(self, peer, raw: RawStatementOperationMessage):
        operation, _ = self.serializer.unpack_serializable(StatementOperation, raw.operation)
        signature, _ = self.serializer.unpack_serializable(StatementOperationSignature, raw.signature)
        self.logger.debug(f'<- message received: {operation}')
        try:
            remote_key = self.crypto.key_from_public_bin(operation.creator_public_key)

            self.requests.validate_peer(peer)
            self.verify_signature(packed_message=raw.operation, key=remote_key, signature=signature.signature,
                                  operation=operation)
            self.validate_operation(operation)

            with db_session():
                is_added = self.db.knowledge.add_operation(operation, signature.signature)
                if is_added:
                    s = f'+ operation added ({operation.object!r} "{operation.predicate}" {operation.subject!r})'
                    self.logger.info(s)

        except PeerValidationError as e:  # peer has exhausted his response count
            self.logger.warning(e)
        except ValueError as e:  # validation error
            self.logger.warning(e)
        except InvalidSignature as e:  # signature verification error
            self.logger.warning(e)

    @lazy_wrapper(RequestStatementOperationMessage)
    def on_request(self, peer, operation):
        operations_count = min(max(1, operation.count), REQUESTED_OPERATIONS_COUNT)
        self.logger.debug('<- peer %s requested %d operations', peer.mid.hex(), operations_count)

        with db_session:
            random_operations = self.db.knowledge.get_operations_for_gossip(count=operations_count)

            self.logger.debug(f'Response {len(random_operations)} operations')
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
                self.logger.debug(f'-> sent operations (%s) to peer: %s', sent_tags_info, peer.mid.hex())

    @staticmethod
    def validate_operation(operation: StatementOperation):
        validate_resource(operation.subject)
        validate_resource(operation.object)
        validate_operation(operation.operation)
        validate_resource_type(operation.subject_type)
        validate_resource_type(operation.predicate)

    def verify_signature(self, packed_message: bytes, key: Key, signature: bytes, operation: StatementOperation):
        if not self.crypto.is_valid_signature(key, packed_message, signature):
            raise InvalidSignature(f"Invalid signature for {operation}")

    def sign(self, operation: StatementOperation) -> bytes:
        packed = self.serializer.pack_serializable(operation)
        return self.crypto.create_signature(self.key, packed)


def validate_resource(resource: str):
    """Validate the resource. Raises ValueError, in the case the resource is not valid."""
    if len(resource) < MIN_RESOURCE_LENGTH or len(resource) > MAX_RESOURCE_LENGTH:
        raise ValueError(f'Tag length should be in range [{MIN_RESOURCE_LENGTH}..{MAX_RESOURCE_LENGTH}]')


def is_valid_resource(resource: str) -> bool:
    """Validate the resource. Returns False, in the case the resource is not valid."""
    try:
        validate_resource(resource)
    except ValueError:
        return False
    return True


def validate_operation(operation: int):
    """Validate the incoming operation. Raises ValueError, in the case the operation is not valid."""
    Operation(operation)


def validate_resource_type(t: int):
    """Validate the resource type. Raises ValueError, in the case the type is not valid."""
    ResourceType(t)


MIN_RESOURCE_LENGTH = 2
MAX_RESOURCE_LENGTH = 50

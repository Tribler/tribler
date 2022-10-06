import random
from binascii import unhexlify

from cryptography.exceptions import InvalidSignature
from ipv8.keyvault.private.libnaclkey import LibNaCLSK
from ipv8.lazy_community import lazy_wrapper
from ipv8.types import Key
from pony.orm import db_session

from tribler.core.components.ipv8.tribler_community import TriblerCommunity
from tribler.core.components.tag.community.tag_payload import (
    RawStatementOperationMessage,
    RequestStatementOperationMessage,
    StatementOperation,
    StatementOperationMessage,
    StatementOperationSignature,
)
from tribler.core.components.tag.community.tag_requests import PeerValidationError, TagRequests
from tribler.core.components.tag.community.tag_validator import validate_operation, validate_tag
from tribler.core.components.tag.db.tag_db import TagDatabase

REQUESTED_TAGS_COUNT = 10

REQUEST_INTERVAL = 5  # 5 sec
CLEAR_ALL_REQUESTS_INTERVAL = 10 * 60  # 10 minutes
TIME_DELTA_FOR_TAGS_THAT_READY_TO_GOSSIP = {'minutes': 1}


class TagCommunity(TriblerCommunity):
    """ Community for disseminating tags across the network.

    Only tags are older than 1 minute will be gossiped.
    """

    community_id = unhexlify('042020c5e5e2ee0727fe99d704b430698e308d98')

    def __init__(self, *args, db: TagDatabase, tags_key: LibNaCLSK, request_interval=REQUEST_INTERVAL,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.db = db
        self.tags_key = tags_key
        self.requests = TagRequests()

        self.add_message_handler(RawStatementOperationMessage, self.on_message)
        self.add_message_handler(RequestStatementOperationMessage, self.on_request)

        self.register_task("request_tags", self.request_tags, interval=request_interval)
        self.register_task("clear_requests", self.requests.clear_requests, interval=CLEAR_ALL_REQUESTS_INTERVAL)
        self.logger.info('Tag community initialized')

    def request_tags(self):
        if not self.get_peers():
            return

        peer = random.choice(self.get_peers())
        self.requests.register_peer(peer, REQUESTED_TAGS_COUNT)
        self.logger.info(f'-> request {REQUESTED_TAGS_COUNT} tags from peer {peer.mid.hex()}')
        self.ez_send(peer, RequestStatementOperationMessage(count=REQUESTED_TAGS_COUNT))

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
                is_added = self.db.add_operation(operation, signature.signature)
                if is_added:
                    s = f'+ tag added ({operation.object!r} "{operation.predicate}" {operation.subject!r})'
                    self.logger.info(s)

        except PeerValidationError as e:  # peer has exhausted his response count
            self.logger.warning(e)
        except ValueError as e:  # validation error
            self.logger.warning(e)
        except InvalidSignature as e:  # signature verification error
            self.logger.warning(e)

    @lazy_wrapper(RequestStatementOperationMessage)
    def on_request(self, peer, operation):
        tags_count = min(max(1, operation.count), REQUESTED_TAGS_COUNT)
        self.logger.info(f'<- peer {peer.mid.hex()} requested {tags_count} tags')

        with db_session:
            random_tag_operations = self.db.get_operations_for_gossip(
                count=tags_count,
                time_delta=TIME_DELTA_FOR_TAGS_THAT_READY_TO_GOSSIP
            )

            self.logger.debug(f'Response {len(random_tag_operations)} tags')
            sent_tags = []
            for op in random_tag_operations:
                try:
                    operation = StatementOperation(
                        subject=op.statement.subject.name,
                        predicate=op.statement.predicate,
                        object=op.statement.object.name,
                        operation=op.operation,
                        clock=op.clock,
                        creator_public_key=op.peer.public_key,
                    )
                    self.validate_operation(operation)
                    signature = StatementOperationSignature(signature=op.signature)
                    self.ez_send(peer, StatementOperationMessage(operation=operation, signature=signature))
                    sent_tags.append(operation)
                except ValueError as e:  # validation error
                    self.logger.warning(e)
            if sent_tags:
                sent_tags_info = ", ".join(f"({t})" for t in sent_tags)
                self.logger.info(f'-> sent {len(sent_tags)} tags to peer: {peer.mid.hex()}')
                self.logger.debug(f'-> sent tags ({sent_tags_info}) to peer: {peer.mid.hex()}')

    @staticmethod
    def validate_operation(operation: StatementOperation):
        validate_tag(operation.subject)
        validate_operation(operation.operation)

    def verify_signature(self, packed_message: bytes, key: Key, signature: bytes, operation: StatementOperation):
        if not self.crypto.is_valid_signature(key, packed_message, signature):
            raise InvalidSignature(f'Invalid signature for {operation}')

    def sign(self, operation: StatementOperation) -> bytes:
        packed = self.serializer.pack_serializable(operation)
        return self.crypto.create_signature(self.tags_key, packed)

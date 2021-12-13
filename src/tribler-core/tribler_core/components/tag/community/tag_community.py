import random
from binascii import unhexlify

from cryptography.exceptions import InvalidSignature

from ipv8.keyvault.private.libnaclkey import LibNaCLSK
from ipv8.lazy_community import lazy_wrapper
from ipv8.types import Key

from pony.orm import db_session

from tribler_core.components.ipv8.tribler_community import TriblerCommunity
from tribler_core.components.tag.community.tag_payload import (
    RawTagOperationMessage,
    RequestTagOperationMessage,
    TagOperation,
    TagOperationMessage,
    TagOperationSignature,
)
from tribler_core.components.tag.community.tag_requests import PeerValidationError, TagRequests
from tribler_core.components.tag.community.tag_validator import validate_operation, validate_tag
from tribler_core.components.tag.db.tag_db import TagDatabase
from tribler_core.utilities.unicode import hexlify

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

        self.add_message_handler(RawTagOperationMessage, self.on_message)
        self.add_message_handler(RequestTagOperationMessage, self.on_request)

        self.register_task("request_tags", self.request_tags, interval=request_interval)
        self.register_task("clear_requests", self.requests.clear_requests, interval=CLEAR_ALL_REQUESTS_INTERVAL)
        self.logger.info('Tag community initialized')

    def request_tags(self):
        if not self.get_peers():
            return

        peer = random.choice(self.get_peers())
        self.requests.register_peer(peer, REQUESTED_TAGS_COUNT)
        self.logger.info(f'-> request {REQUESTED_TAGS_COUNT} tags from peer {hexlify(peer.mid)}')
        self.ez_send(peer, RequestTagOperationMessage(count=REQUESTED_TAGS_COUNT))

    @lazy_wrapper(RawTagOperationMessage)
    def on_message(self, peer, raw: RawTagOperationMessage):
        operation, _ = self.serializer.unpack_serializable(TagOperation, raw.operation)
        signature, _ = self.serializer.unpack_serializable(TagOperationSignature, raw.signature)
        self.logger.debug(f'<- message received: {operation}')
        try:
            remote_key = self.crypto.key_from_public_bin(operation.creator_public_key)

            self.requests.validate_peer(peer)
            self.verify_signature(packed_message=raw.operation, key=remote_key, signature=signature.signature,
                                  operation=operation)
            self.validate_operation(operation)

            with db_session():
                is_added = self.db.add_tag_operation(operation, signature.signature)
                if is_added:
                    self.logger.info(f'+ tag added ({operation.tag} ,{hexlify(operation.infohash)})')

        except PeerValidationError as e:  # peer has exhausted his response count
            self.logger.warning(e)
        except ValueError as e:  # validation error
            self.logger.warning(e)
        except InvalidSignature as e:  # signature verification error
            self.logger.warning(e)

    @lazy_wrapper(RequestTagOperationMessage)
    def on_request(self, peer, operation):
        tags_count = min(max(1, operation.count), REQUESTED_TAGS_COUNT)
        self.logger.info(f'<- peer {hexlify(peer.mid)} requested {tags_count} tags')

        with db_session:
            random_tag_operations = self.db.get_tags_operations_for_gossip(
                count=tags_count,
                time_delta=TIME_DELTA_FOR_TAGS_THAT_READY_TO_GOSSIP
            )

            self.logger.debug(f'Response {len(random_tag_operations)} tags')
            sent_tags = []
            for tag_operation in random_tag_operations:
                try:
                    operation = TagOperation(
                        infohash=tag_operation.torrent_tag.torrent.infohash,
                        operation=tag_operation.operation,
                        clock=tag_operation.clock,
                        creator_public_key=tag_operation.peer.public_key,
                        tag=tag_operation.torrent_tag.tag.name,
                    )
                    self.validate_operation(operation)
                    signature = TagOperationSignature(signature=tag_operation.signature)
                    self.ez_send(peer, TagOperationMessage(operation=operation, signature=signature))
                    sent_tags.append(operation)
                except ValueError as e:  # validation error
                    self.logger.warning(e)
            if sent_tags:
                sent_tags_info = ", ".join(f"({t})" for t in sent_tags)
                self.logger.info(f'-> sent tags ({sent_tags_info}) to peer: {hexlify(peer.mid)}')

    @staticmethod
    def validate_operation(operation: TagOperation):
        validate_tag(operation.tag)
        validate_operation(operation.operation)

    def verify_signature(self, packed_message: bytes, key: Key, signature: bytes, operation: TagOperation):
        if not self.crypto.is_valid_signature(key, packed_message, signature):
            raise InvalidSignature(f'Invalid signature for {operation}')

    def sign(self, operation: TagOperation) -> bytes:
        packed = self.serializer.pack_serializable(operation)
        return self.crypto.create_signature(self.tags_key, packed)

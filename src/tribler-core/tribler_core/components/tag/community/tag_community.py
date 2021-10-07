import random
from binascii import unhexlify

from cryptography.exceptions import InvalidSignature
from pony.orm import TransactionIntegrityError, db_session

from ipv8.lazy_community import lazy_wrapper
from tribler_core.components.tag.community.tag_crypto import TagCrypto
from tribler_core.components.tag.community.tag_payload import RequestTagOperationMessage, TagOperationMessage
from tribler_core.components.tag.community.tag_request_controller import PeerValidationError, TagRequestController
from tribler_core.components.tag.community.tag_validator import TagValidator
from tribler_core.components.tag.db.tag_db import TagDatabase
from tribler_core.modules.tribler_community import TriblerCommunity

REQUESTED_TAGS_COUNT = 10
GOSSIP_RANDOM_PEERS_COUNT = 10

REQUEST_INTERVAL = 5  # 5 sec
CLEAR_ALL_REQUESTS_INTERVAL = 10 * 60  # 10 minutes


class TagCommunity(TriblerCommunity):
    """ Community for disseminating tags across the network.
    """

    community_id = unhexlify('042020c5e5e2ee0727fe99d704b430698e308d98')

    def __init__(self, *args, db: TagDatabase, validator: TagValidator = None, crypto: TagCrypto = None,
                 request_controller: TagRequestController = None, request_interval=REQUEST_INTERVAL,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.db = db
        self.validator = validator
        self.crypto = crypto
        self.request_controller = request_controller

        self.add_message_handler(TagOperationMessage, self.on_message)
        self.add_message_handler(RequestTagOperationMessage, self.on_request)

        self.register_task("request_tags", self.request_tags, interval=request_interval)
        if self.request_controller:
            self.register_task("clear_requests", self.request_controller.clear_requests,
                               interval=CLEAR_ALL_REQUESTS_INTERVAL)

        self.logger.info('Tag community initialized')

    def request_tags(self):
        if not self.get_peers():
            return

        peer = random.choice(self.get_peers())
        if self.request_controller:
            self.request_controller.register_peer(peer, REQUESTED_TAGS_COUNT)
        self.logger.info(f'Request {REQUESTED_TAGS_COUNT} tags')
        self.ez_send(peer, RequestTagOperationMessage(REQUESTED_TAGS_COUNT))

    @lazy_wrapper(TagOperationMessage)
    def on_message(self, peer, payload):
        self.logger.debug(f'Message received: {payload}')
        try:
            if self.request_controller:
                self.request_controller.validate_peer(peer)
            if self.validator:
                self.validator.validate_mesage(payload)
            if self.crypto:
                self.crypto.validate_signature(payload)
            with db_session():
                self.db.add_tag_operation(payload.infohash, payload.tag.decode(), payload.operation, payload.time,
                                          payload.creator_public_key, payload.signature)
                self.logger.info(f'Tag added: {payload.tag}:{payload.infohash}')

        except TransactionIntegrityError:  # db error
            pass
        except PeerValidationError as e:  # peer has exhausted his response count
            self.logger.warning(e)
        except ValueError as e:  # validation error
            self.logger.warning(e)
        except InvalidSignature as e:  # signature verification error
            self.logger.error(e)

    @lazy_wrapper(RequestTagOperationMessage)
    def on_request(self, peer, payload):
        tags_count = min(max(1, payload.count), REQUESTED_TAGS_COUNT)
        self.logger.info(f'On request {tags_count} tags')

        with db_session:
            random_tag_operations = list(self.db.instance.TorrentTagOp.select_random(tags_count))
            self.logger.debug(f'Response {len(random_tag_operations)} tags')
            for tag_operation in random_tag_operations:
                try:
                    payload = TagOperationMessage(tag_operation.torrent_tag.torrent.infohash, tag_operation.operation,
                                                  tag_operation.time, tag_operation.peer.public_key,
                                                  tag_operation.signature, tag_operation.torrent_tag.tag.name.encode())

                    if self.validator:
                        self.validator.validate_mesage(payload)
                    self.ez_send(peer, payload)
                except ValueError as e:  # validation error
                    self.logger.warning(e)

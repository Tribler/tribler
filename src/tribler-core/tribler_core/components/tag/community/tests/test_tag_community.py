from pony.orm import db_session

from ipv8.test.base import TestBase
from ipv8.test.mocking.ipv8 import MockIPv8
from tribler_core.components.tag.community.tag_community import TagCommunity
from tribler_core.components.tag.community.tag_crypto import TagCrypto
from tribler_core.components.tag.community.tag_request_controller import TagRequestController
from tribler_core.components.tag.community.tag_validator import TagValidator
from tribler_core.components.tag.db.tag_db import Operation, TagDatabase

REQUEST_INTERVAL_FOR_RANDOM_TAGS = 0.1  # in seconds


class TestTagCommunity(TestBase):
    def setUp(self):
        super().setUp()
        self.initialize(TagCommunity, 2)

    async def tearDown(self):
        await super().tearDown()

    def create_node(self, *args, **kwargs):
        return MockIPv8("curve25519", TagCommunity, db=TagDatabase(), validator=TagValidator(), crypto=TagCrypto(),
                        request_controller=TagRequestController(), request_interval=REQUEST_INTERVAL_FOR_RANDOM_TAGS)

    @db_session
    async def fill_db(self):
        # create 10 tag operations
        for i in range(10):
            infohash = f'{i}'.encode() * 20
            tag = f'{i}' * 3
            operation = Operation.ADD
            time = 1
            creator_public_key = self.overlay(0).my_peer.public_key.key_to_bin()
            signature = TagCrypto.sign(infohash, tag, operation, time, creator_public_key,
                                       key=self.overlay(0).my_peer.key)

            # 5 of them be signed incorrectly
            if i >= 5:
                signature = f'{i}'.encode() * 64

            self.overlay(0).db.add_tag_operation(infohash, tag, operation, time, creator_public_key, signature)

    async def test_gossip(self):
        # when crypto is enabled, only 5 messages should be propagated
        await self.fill_db()
        await self.introduce_nodes()
        await self.deliver_messages(timeout=REQUEST_INTERVAL_FOR_RANDOM_TAGS * 2)
        with db_session:
            assert self.overlay(0).db.instance.TorrentTagOp.select().count() == 10
            assert self.overlay(1).db.instance.TorrentTagOp.select().count() == 5

    async def test_gossip_no_crypto_validation(self):
        # when crypto is disabled, all 10 messages should be propagated
        self.overlay(0).crypto = None
        self.overlay(1).crypto = None

        await self.fill_db()
        await self.introduce_nodes()
        await self.deliver_messages(timeout=REQUEST_INTERVAL_FOR_RANDOM_TAGS * 2)
        with db_session:
            assert self.overlay(0).db.instance.TorrentTagOp.select().count() == 10
            assert self.overlay(1).db.instance.TorrentTagOp.select().count() == 10

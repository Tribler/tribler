import datetime
from unittest.mock import MagicMock, Mock

from cryptography.exceptions import InvalidSignature
from pony.orm import db_session

from ipv8.keyvault.private.libnaclkey import LibNaCLSK
from ipv8.test.base import TestBase
from ipv8.test.mocking.ipv8 import MockIPv8
from tribler_core.components.tag.community.tag_community import TagCommunity
from tribler_core.components.tag.community.tag_payload import TagOperation
from tribler_core.components.tag.community.tag_requests import PeerValidationError
from tribler_core.components.tag.db.tag_db import TagDatabase, TagOperationEnum

REQUEST_INTERVAL_FOR_RANDOM_TAGS = 0.1  # in seconds


class TestTagCommunity(TestBase):
    def setUp(self):
        super().setUp()
        self.initialize(TagCommunity, 2)

    async def tearDown(self):
        await super().tearDown()

    def create_node(self, *args, **kwargs):
        return MockIPv8("curve25519", TagCommunity, db=TagDatabase(), tags_key=LibNaCLSK(),
                        request_interval=REQUEST_INTERVAL_FOR_RANDOM_TAGS)

    def create_operation(self, tag=''):
        community = self.overlay(0)
        operation = TagOperation(infohash=b'1' * 20, operation=TagOperationEnum.ADD, clock=0,
                                 creator_public_key=community.tags_key.pub().key_to_bin(), tag=tag)
        operation.clock = community.db.get_clock(operation) + 1
        return operation

    @db_session
    async def fill_db(self):
        # create 10 tag operations:
        # first 5 of them are correct
        # next 5 of them are incorrect
        community = self.overlay(0)
        for i in range(10):
            message = self.create_operation(f'{i}' * 3)
            signature = community.sign(message)
            # 5 of them are signed incorrectly
            if i >= 5:
                signature = b'1' * 64

            community.db.add_tag_operation(message, signature)

        # put them into the past
        for tag_op in community.db.instance.TorrentTagOp.select():
            tag_op.set(updated_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=2))

    async def test_gossip(self):
        # Test default gossip.
        # Only 5 correct messages should be propagated
        await self.fill_db()
        await self.introduce_nodes()
        await self.deliver_messages(timeout=REQUEST_INTERVAL_FOR_RANDOM_TAGS * 2)
        with db_session:
            assert self.overlay(0).db.instance.TorrentTagOp.select().count() == 10
            assert self.overlay(1).db.instance.TorrentTagOp.select().count() == 5

    async def test_gossip_no_fresh_tags(self):
        # Test that no fresh tags be propagated
        # add one fresh operation into dataset and assert that it is not be propagated.
        await self.fill_db()

        # put the first operation into the current moment (make it fresh)
        with db_session:
            tag_operation = self.overlay(0).db.instance.TorrentTagOp.select().first()
            tag_operation.updated_at = datetime.datetime.utcnow()

        await self.introduce_nodes()
        await self.deliver_messages(timeout=REQUEST_INTERVAL_FOR_RANDOM_TAGS * 2)
        with db_session:
            assert self.overlay(0).db.instance.TorrentTagOp.select().count() == 10
            assert self.overlay(1).db.instance.TorrentTagOp.select().count() == 4  # 5 invalid signature + 1 fresh tag

    async def test_on_message_eat_exceptions(self):
        # Tests that except blocks in on_message function works as expected
        # some exceptions should be eaten silently
        exception_to_be_tested = {PeerValidationError, ValueError, AssertionError,
                                  InvalidSignature}
        await self.fill_db()
        for exception_class in exception_to_be_tested:
            # let's "break" the function that will be called on on_message()
            self.overlay(1).verify_signature = Mock(side_effect=exception_class(''))
            # occurred exception should be ate by community silently
            await self.introduce_nodes()
            await self.deliver_messages(timeout=REQUEST_INTERVAL_FOR_RANDOM_TAGS * 2)
            self.overlay(1).verify_signature.assert_called()

    async def test_on_request_eat_exceptions(self):
        # Tests that except blocks in on_request function works as expected
        # ValueError should be eaten silently
        await self.fill_db()
        # let's "break" the function that will be called on on_request()
        self.overlay(0).db.get_tags_operations_for_gossip = Mock(return_value=[MagicMock()])
        # occurred exception should be ate by community silently
        await self.introduce_nodes()
        await self.deliver_messages(timeout=REQUEST_INTERVAL_FOR_RANDOM_TAGS * 2)
        self.overlay(0).db.get_tags_operations_for_gossip.assert_called()

    async def test_no_peers(self):
        # Test that no error occurs in the community, in case there is no peers
        self.overlay(0).get_peers = Mock(return_value=[])
        await self.fill_db()
        await self.introduce_nodes()
        await self.deliver_messages(timeout=REQUEST_INTERVAL_FOR_RANDOM_TAGS * 2)
        self.overlay(0).get_peers.assert_called()

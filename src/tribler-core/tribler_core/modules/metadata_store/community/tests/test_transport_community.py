import logging
import random
import sys
from binascii import unhexlify

from ipv8.lazy_community import lazy_wrapper
from ipv8.messaging.lazy_payload import VariablePayload, vp_compile
from ipv8.test.base import TestBase

import pytest

from tribler_core.modules.metadata_store.community.transport_community import Tcp8MessageCommunity

random.seed(123)
root = logging.getLogger()
root.setLevel(logging.DEBUG)


class PrintHandler(logging.Handler):
    def emit(self, record):
        print(self.format(record))


handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
logging.getLogger('faker').setLevel(logging.ERROR)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
# root.addHandler(handler)
root.addHandler(PrintHandler())


@vp_compile
class DumbPayload(VariablePayload):
    msg_id = 11
    names = ['data']
    format_list = ['raw']


class TransportTestCommunity(Tcp8MessageCommunity):
    community_id = unhexlify('eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.received_messages = []

        self.add_message_handler(DumbPayload, self.on_dumb_payload)

    @lazy_wrapper(DumbPayload)
    def on_dumb_payload(self, src_peer, payload):
        self.received_messages.append(payload)


class TestC3Transfer(TestBase):
    """
    Unit tests for the base RemoteQueryCommunity which do not need a real Session.
    """

    def setUp(self):
        super().setUp()
        self.count = 0
        self.initialize(TransportTestCommunity, 2)

    def create_node(self, *args, **kwargs):
        node = super().create_node(*args, **kwargs)
        self.count += 1
        return node

    async def tst_send(self, src, dst, data):
        payload = DumbPayload(data)
        src.overlay.fat_send(dst.my_peer, payload)
        await self.deliver_messages(timeout=0.5)
        assert dst.overlay.received_messages[-1].data == payload.data

    @pytest.mark.timeout(0)
    async def test_send_message(self):
        p0 = self.nodes[0]
        p1 = self.nodes[1]

        # Test sending a message
        await self.tst_send(p0, p1, b"a" * 1000 * 10)

        # Test sending another message to the same peer
        await self.tst_send(p0, p1, b"c" * 1000 * 10)

        # Test sending a message back
        await self.tst_send(p1, p0, b"f" * 1000 * 10)

        # Test sending another message back
        await self.tst_send(p1, p0, b"e" * 1000 * 10)

    @pytest.mark.timeout(20)
    async def test_send_many_messages(self):
        p0 = self.nodes[0]
        p1 = self.nodes[1]

        for i in range(0, 10):
            await self.tst_send(p0, p1, b"0123456789abcd"[i : i + 1] * 500 * i)

    @pytest.mark.timeout(0)
    async def test_send_messages_reciprocal(self):
        p0 = self.nodes[0]
        p1 = self.nodes[1]
        data0 = b"a" * 800 * 10
        data1 = b"c" * 700 * 10

        p0.overlay.fat_send(p1.my_peer, DumbPayload(data0))
        p1.overlay.fat_send(p0.my_peer, DumbPayload(data1))
        await self.deliver_messages(timeout=0.5)

        assert p1.overlay.received_messages[-1].data == data0
        assert p0.overlay.received_messages[-1].data == data1

    async def test_send_messages_concurrent(self):
        p0 = self.nodes[0]
        p1 = self.nodes[1]
        data0 = b"a" * 800 * 10
        data1 = b"c" * 700 * 10

        p0.overlay.fat_send(p1.my_peer, DumbPayload(data0))
        p0.overlay.fat_send(p1.my_peer, DumbPayload(data1))
        await self.deliver_messages(timeout=0.5)

        assert p1.overlay.received_messages[0].data == data0
        assert p1.overlay.received_messages[1].data == data1

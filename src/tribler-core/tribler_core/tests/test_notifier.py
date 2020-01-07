from asyncio import Future

from tribler_common.simpledefs import NTFY

from tribler_core.notifier import Notifier
from tribler_core.tests.tools.base_test import TriblerCoreTest
from tribler_core.tests.tools.tools import timeout


class TriblerCoreTestNotifier(TriblerCoreTest):

    async def setUp(self):
        await super(TriblerCoreTestNotifier, self).setUp()
        self.test_future = Future()
        self.called_callback = False

    def callback_func(self, *args):
        self.called_callback = True
        self.test_future.set_result(None)

    @timeout(10)
    async def test_notifier(self):
        notifier = Notifier()
        notifier.add_observer(NTFY.TORRENT_FINISHED, self.callback_func)
        notifier.notify(NTFY.TORRENT_FINISHED)
        await self.test_future
        self.assertTrue(self.called_callback)

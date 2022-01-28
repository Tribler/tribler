import asyncio
from unittest.mock import Mock

import pytest

from tribler_core.notifier import Notifier

# pylint: disable=redefined-outer-name, protected-access

@pytest.fixture
def notifier():
    return Notifier()


class DummyCallback:
    def __init__(self, side_effect=None):
        self.callback_has_been_called = False
        self.callback_has_been_called_with_args = None
        self.callback_has_been_called_with_kwargs = None
        self.side_effect = side_effect
        self.event = asyncio.Event()

    def callback(self, *args, **kwargs):
        self.callback_has_been_called_with_args = args
        self.callback_has_been_called_with_kwargs = kwargs
        self.callback_has_been_called = True
        if self.side_effect:
            raise self.side_effect()

        self.event.set()


@pytest.mark.asyncio
async def test_notifier_add_observer(notifier: Notifier):
    def callback():
        ...

    # test that add observer stores topics and callbacks as a set to prevent duplicates
    notifier.add_observer('topic', callback)
    notifier.add_observer('topic', callback)

    assert len(notifier.observers['topic']) == 1


@pytest.mark.asyncio
async def test_notifier_remove_nonexistent_observer(notifier: Notifier):
    # test that `remove_observer` don't crash in case of calling to remove non existed topic/callback
    notifier.remove_observer('nonexistent', lambda: None)
    assert not notifier.observers['nonexistent']


@pytest.mark.asyncio
async def test_notifier_remove_observer(notifier: Notifier):
    def callback1():
        ...

    def callback2():
        ...

    notifier.add_observer('topic', callback1)
    notifier.add_observer('topic', callback2)

    notifier.remove_observer('topic', callback1)
    assert notifier.observers['topic'] == {callback2: True}


@pytest.mark.timeout(1)
@pytest.mark.asyncio
async def test_notify(notifier: Notifier):
    # test that notify works as expected
    normal_callback = DummyCallback()

    notifier.add_observer('topic', normal_callback.callback)
    notifier.notify('topic', 'arg', kwarg='value')

    # wait for the callback
    await normal_callback.event.wait()
    assert normal_callback.callback_has_been_called
    assert normal_callback.callback_has_been_called_with_args == ('arg',)
    assert normal_callback.callback_has_been_called_with_kwargs == {'kwarg': 'value'}


@pytest.mark.asyncio
async def test_notify_with_exception(notifier: Notifier):
    # test that notify works as expected even if one of callbacks will raise an exception

    normal_callback = DummyCallback()
    side_effect_callback = DummyCallback(ValueError)

    notifier.add_observer('topic', side_effect_callback.callback)
    notifier.add_observer('topic', normal_callback.callback)
    notifier.add_observer('topic', side_effect_callback.callback)

    notifier.notify('topic')

    # wait
    await asyncio.sleep(1)

    assert normal_callback.callback_has_been_called
    assert side_effect_callback.callback_has_been_called


@pytest.mark.asyncio
async def test_notify_call_soon_threadsafe_with_exception(notifier: Notifier):
    notifier.logger = Mock()
    notifier._loop = Mock(call_soon_threadsafe=Mock(side_effect=RuntimeError))

    notifier.add_observer('topic', lambda: ...)
    notifier.notify('topic')

    notifier.logger.warning.assert_called_once()

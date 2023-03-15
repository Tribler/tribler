import asyncio
from unittest.mock import MagicMock

import pytest

from tribler.core.utilities.notifier import Notifier, NotifierError


# pylint: disable=unused-argument


def test_add_remove_observer():
    notifier = Notifier()

    # A topic should be callable
    with pytest.raises(TypeError, match=r"^'topic' is not a callable object$"):
        notifier.add_observer('topic', lambda x: x)

    def topic1(x: int):
        pass

    # An observer should be callable as well
    with pytest.raises(TypeError, match=r"^'observer' is not a callable object$"):
        notifier.add_observer(topic1, "observer")

    def observer1():
        pass

    # Topic and observer functions should have the same number of arguments
    with pytest.raises(TypeError, match=r'^Cannot add observer <function .*> to topic "topic1": '
                                        r'the callback signature \(\) does not match the topic signature \(x: int\)$'):
        notifier.add_observer(topic1, observer1)

    def observer2(x):
        pass

    # Topic and observer functions should have the same argument types
    with pytest.raises(TypeError, match=r'^Cannot add observer <function .*> to topic "topic1": '
                                        r'the callback signature \(x\) does not match the topic signature \(x: int\)$'):
        notifier.add_observer(topic1, observer2)

    def observer3(x: str):
        pass

    # Topic and observer functions should have the same argument types
    with pytest.raises(TypeError, match=r'^Cannot add observer <function .*> to topic "topic1": '
                                        r'the callback signature \(x: str\) '
                                        r'does not match the topic signature \(x: int\)$'):
        notifier.add_observer(topic1, observer3)

    def observer4(y: int):
        pass

    # Topic and observer functions should have the same argument names
    with pytest.raises(TypeError, match=r'^Cannot add observer <function .*> to topic "topic1": '
                                        r'the callback signature \(y: int\) '
                                        r'does not match the topic signature \(x: int\)$'):
        notifier.add_observer(topic1, observer4)

    def observer5(x: int, y: int):
        pass

    # Topic and observer functions should have the same number of arguments
    with pytest.raises(TypeError, match=r'^Cannot add observer <function .*> to topic "topic1": '
                                        r'the callback signature \(x: int, y: int\) '
                                        r'does not match the topic signature \(x: int\)$'):
        notifier.add_observer(topic1, observer5)

    def observer6(x: int = None):
        pass

    # Topic and observer functions should have the same argument defaults
    with pytest.raises(TypeError, match=r'^Cannot add observer <function .*> to topic "topic1": '
                                        r'the callback signature \(x: int = None\) '
                                        r'does not match the topic signature \(x: int\)$'):
        notifier.add_observer(topic1, observer6)

    async def async1(x: int):
        pass

    # Topic and observer cannot be async functions
    with pytest.raises(TypeError, match=r'^Topic cannot be a coroutine function. Got: <function .*>$'):
        notifier.add_observer(async1, topic1)

    with pytest.raises(TypeError, match=r'^Observer cannot be a coroutine function. Got: <function .*>$'):
        notifier.add_observer(topic1, async1)

    with pytest.raises(TypeError, match=r'^Topic and observer cannot be the same function. Got: <function .*>$'):
        notifier.add_observer(topic1, topic1)

    def observer7(x: int):
        pass

    with pytest.raises(TypeError, match=r"^`synchronous` option may be True, False or None. Got: 1$"):
        notifier.add_observer(topic1, observer7, synchronous=1)

    with pytest.raises(TypeError, match=r"^synchronous=False option cannot be specified "
                                        r"for a notifier without an event loop$"):
        notifier.add_observer(topic1, observer7, synchronous=False)

    assert not notifier.topics_by_name
    assert not notifier.topics
    assert not notifier.generic_observers
    assert not notifier.interceptors

    # add first observer to topic1
    notifier.add_observer(topic1, observer7)

    assert notifier.topics_by_name == {'topic1': topic1}
    assert notifier.topics == {topic1: {observer7: True}}

    # adding the same observer the second time should change nothing
    notifier.add_observer(topic1, observer7)
    assert notifier.topics == {topic1: {observer7: True}}

    def observer8(x: int):
        pass

    # add second observer to topic1
    notifier.add_observer(topic1, observer8)
    assert notifier.topics == {topic1: {observer7: True, observer8: True}}

    # generic observers and interceptors were not added
    assert not notifier.generic_observers
    assert not notifier.interceptors

    def topic2(x: int):
        pass

    def observer9(x: int):
        pass

    # no exception when removing an observer from non-registered topic
    notifier.remove_observer(topic2, observer7)

    # no exception when removing a non-registered observer
    notifier.remove_observer(topic1, observer9)
    # we still has two observers for topic1 topic
    assert notifier.topics == {topic1: {observer7: True, observer8: True}, topic2: {}}

    # remove the first observer from the topic1 topic
    notifier.remove_observer(topic1, observer7)
    assert notifier.topics == {topic1: {observer8: True}, topic2: {}}

    # remove last observer from the topic1 topic
    notifier.remove_observer(topic1, observer8)
    assert notifier.topics == {topic1: {}, topic2: {}}


def test_two_topics_with_the_same_name():
    notifier = Notifier()

    def topic1(x: int):
        pass

    def observer1(x: int):
        pass

    notifier.add_observer(topic1, observer1)

    def topic1(x: int):  # pylint: disable=function-redefined  # try to define another topic with the same name
        pass

    def observer2(x: int):
        pass

    with pytest.raises(NotifierError, match='^Cannot register topic <.*topic1.*> because topic name topic1 '
                                            'is already taken by another topic <.*topic1.*>$'):
        notifier.add_observer(topic1, observer2)


def test_notify():
    def topic_a(a: int, b: str):
        pass

    def topic_b(x: int):
        pass

    calls = []

    def observer_a1(a: int, b: str):
        calls.append(('a1', a, b))

    def observer_a2(a: int, b: str):
        calls.append(('a2', a, b))

    def observer_b1(x: int):
        calls.append(('b1', x))

    def generic_1(*args, **kwargs):
        calls.append((('generic1',) + args + (repr(kwargs),)))

    def generic_2(*args, **kwargs):
        calls.append((('generic2',) + args + (repr(kwargs),)))

    notifier = Notifier()
    notifier.add_observer(topic_a, observer_a1)  # add an observer
    notifier.add_observer(topic_a, observer_a1)  # adding the same observer multiple times should affect nothing
    notifier.add_generic_observer(generic_1)  # add a generic observer

    with pytest.raises(TypeError):
        notifier[topic_a](123)

    assert calls == []

    notifier[topic_a](1, 'aaa')

    assert calls == [('generic1', topic_a, 1, 'aaa', '{}'), ('a1', 1, 'aaa')]
    calls.clear()

    notifier.add_observer(topic_a, observer_a2)  # add a second observer to the same topic
    notifier.add_observer(topic_b, observer_b1)  # observer to a different topic
    notifier.add_generic_observer(generic_2)  # a second generic observer

    notifier[topic_a](2, 'bbb')

    assert calls == [('generic1', topic_a, 2, 'bbb', '{}'), ('generic2', topic_a, 2, 'bbb', '{}'), ('a1', 2, 'bbb'),
                     ('a2', 2, 'bbb')]
    calls.clear()

    notifier[topic_b](x=111)

    assert calls == [('generic1', topic_b, "{'x': 111}"), ('generic2', topic_b, "{'x': 111}"), ('b1', 111)]
    calls.clear()

    notifier.logger.warning = MagicMock()
    notifier.notify_by_topic_name('non_existent_topic', x=1, y=2)
    notifier.logger.warning.assert_called_once_with('Topic with name `non_existent_topic` not found')

    notifier.notify_by_topic_name('topic_b', x=111)

    assert calls == [('generic1', topic_b, "{'x': 111}"), ('generic2', topic_b, "{'x': 111}"), ('b1', 111)]
    calls.clear()

    notifier.remove_observer(topic_b, observer_b1)
    notifier.remove_generic_observer(generic_1)

    notifier[topic_b](222)

    assert calls == [('generic2', topic_b, 222, '{}')]


async def test_notify_async(event_loop):
    def topic_a(a: int, b: str):
        pass

    def topic_b(x: int):
        pass

    calls = []

    def observer_a1(a: int, b: str):
        calls.append(('a1', a, b))

    def observer_a2(a: int, b: str):
        calls.append(('a2', a, b))

    def observer_b1(x: int):
        calls.append(('b1', x))

    def generic_1(*args, **kwargs):
        calls.append((('generic1',) + args + (repr(kwargs),)))

    def generic_2(*args, **kwargs):
        calls.append((('generic2',) + args + (repr(kwargs),)))

    notifier = Notifier(loop=event_loop)
    notifier.add_observer(topic_a, observer_a1)  # add an observer
    notifier.add_observer(topic_a, observer_a1)  # adding the same observer multiple times should affect nothing
    notifier.add_generic_observer(generic_1)  # add a generic observer

    # An attempt to add the same observer with different `synchronous` option value should raise an error
    with pytest.raises(NotifierError, match=r'^Cannot register the same observer '
                                            r'with a different value of `synchronous` option$'):
        notifier.add_observer(topic_a, observer_a1, synchronous=True)

    with pytest.raises(TypeError):
        notifier[topic_a](123)

    assert calls == []

    notifier[topic_a](1, 'aaa')

    await asyncio.sleep(0.1)

    assert set(calls) == {('generic1', topic_a, 1, 'aaa', '{}'), ('a1', 1, 'aaa')}
    calls.clear()

    notifier.add_observer(topic_a, observer_a2)  # add a second observer to the same topic
    notifier.add_observer(topic_b, observer_b1)  # observer to a different topic
    notifier.add_generic_observer(generic_2)  # a second generic observer

    notifier[topic_a](2, 'bbb')

    await asyncio.sleep(0.1)

    assert set(calls) == {('generic1', topic_a, 2, 'bbb', '{}'), ('generic2', topic_a, 2, 'bbb', '{}'),
                          ('a1', 2, 'bbb'), ('a2', 2, 'bbb')}
    calls.clear()

    notifier[topic_b](x=111)

    await asyncio.sleep(0.1)

    assert set(calls) == {('generic1', topic_b, "{'x': 111}"), ('generic2', topic_b, "{'x': 111}"), ('b1', 111)}
    calls.clear()

    notifier.remove_observer(topic_b, observer_b1)
    notifier.remove_generic_observer(generic_1)

    notifier[topic_b](222)

    await asyncio.sleep(0.1)

    assert set(calls) == {('generic2', topic_b, 222, '{}')}


async def test_notify_with_exception(event_loop):
    # test that notify works as expected even if one of callbacks will raise an exception

    def topic(x: int):
        pass

    calls = []

    def observer1(x: int):
        calls.append(('observer1', x))

    def observer2(x: int):
        calls.append(('observer2', x))
        raise ZeroDivisionError

    def observer3(x: int):
        calls.append(('observer3', x))

    notifier = Notifier()  # First, let's create a notifier without a loop specified

    notifier.add_observer(topic, observer1)
    notifier.add_observer(topic, observer2)
    notifier.add_observer(topic, observer3)

    notifier[topic](123)

    # when notifier is created without specifying a loop, it processes notifications synchronously
    assert calls == [('observer1', 123), ('observer2', 123), ('observer3', 123)]
    calls.clear()

    notifier = Notifier(loop=event_loop)  # Now, let's create a notifier tied to a loop

    notifier.add_observer(topic, observer1)
    notifier.add_observer(topic, observer2)
    notifier.add_observer(topic, observer3)

    notifier[topic](123)

    # when notifier tied to a loop, it processes notifications asynchronously
    assert calls == []

    await asyncio.sleep(0.1)

    # now notifications should be processed
    assert set(calls) == {('observer1', 123), ('observer2', 123), ('observer3', 123)}


def test_notify_call_soon_threadsafe_with_exception(event_loop):
    notifier = Notifier(loop=event_loop)

    notifier.logger = MagicMock()
    notifier.loop = MagicMock(call_soon_threadsafe=MagicMock(side_effect=RuntimeError))

    def topic1(x: int):
        pass

    def observer1(x: int):
        pass

    notifier.add_observer(topic1, observer1)
    notifier[topic1](123)

    notifier.logger.warning.assert_called_once()

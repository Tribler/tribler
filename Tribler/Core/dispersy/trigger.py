"""
The Trigger module provides the objects that sit and wait for incoming messages.  Each message that
was successfully processed may 'trigger' one of the Trigger objects defined in this module.

Triggers allow us to wait for something, for instance, when a message is received out of sequence it
is delayed until the previous message in the sequence is successfully processed.  Hence, processing
this previous message will trigger the processing of the delayed message.

@author: Boudewijn Schoon
@organization: Technical University Delft
@contact: dispersy@frayja.com
"""

from re import compile as expression_compile

if __debug__:
    from dprint import dprint

class Trigger(object):
    def extend(self):
        """
        Try to extend this trigger.

        Before making a new Trigger, we first try to extend an existing one.  If we can extend one,
        it can be much cheaper.

        Must return True when the extend was successfull.  Otherwise, returns False.
        """
        raise NotImplementedError()

    def on_messages(self, messages):
        """
        Called with a received message.

        Must return True to keep the trigger available.  Hence, returning False will remove the
        trigger.
        """
        raise NotImplementedError()

    def on_timeout(self):
        raise NotImplementedError()

class TriggerCallback(Trigger):
    def __init__(self, pattern, response_func, response_args, max_responses):
        """
        Receiving a message matching PATTERN triggers a call to RESPONSE_FUNC.

        PATTERN is a python regular expression string.

        RESPONSE_FUNC is called when PATTERN matches the incoming message footprint.  The first
        argument is the sender address, the second argument is the incoming message, following this
        are optional values from RESPONSE_ARGS.

        RESPONSE_ARGS is an optional tuple containing arguments passed to RESPONSE_ARGS.

        MAX_RESPONSES is a number.  Once MAX_RESPONSES messages are received no further calls are
        made to RESPONSE_FUNC.

        When a timeout is received and MAX_RESPONSES has not yet been reached, RESPONSE_FUNC is
        immediately called.  The first argument will be ('', -1), the second will be None, following
        this are the optional values from RESPONSE_FUNC.
        """
        assert isinstance(pattern, str)
        assert hasattr(response_func, "__call__")
        assert isinstance(response_args, tuple)
        assert isinstance(max_responses, int)
        assert max_responses > 0
        if __debug__:
            self._debug_pattern = pattern
            dprint("create new trigger for one callback")
            dprint(pattern)
        self._match = expression_compile(pattern).match
        self._response_func = response_func
        self._response_args = response_args
        self._responses_remaining = max_responses

    def extend(self):
        """
        We can never extend this Trigger because of the responses_remaining property.
        """
        return False

    def on_messages(self, messages):
        assert isinstance(messages, list)
        assert len(messages) > 0
        for message in messages:
            # if __debug__:
            #     if self._responses_remaining > 0:
            #         dprint("Does it match? ", bool(self._responses_remaining > 0 and self._match(message.footprint)))
            #         dprint("Expression: ", self._debug_pattern)
            #         dprint(" Footprint: ", message.footprint)
            if self._responses_remaining > 0 and self._match(message.footprint):
                if __debug__: dprint("match footprint for one callback")
                self._responses_remaining -= 1
                # note: this callback may raise DelayMessage, etc
                self._response_func(message, *self._response_args)

        # False to remove the Trigger
        return self._responses_remaining > 0

    def on_timeout(self):
        if self._responses_remaining > 0:
            if __debug__: dprint("timout on trigger with one callback", level="warning")
            self._responses_remaining = 0
            # note: this callback may raise DelayMessage, etc
            self._response_func(None, *self._response_args)

class TriggerPacket(Trigger):
    def __init__(self, pattern, callback, packets):
        """
        Receiving a message matching PATTERN triggers a call to the on_incoming_packet method with
        PACKETS.

        PATTERN is a python regular expression string.

        CALLBACK is called when PATTERN matches the incoming message footprint.  The only argument
        is PACKETS.

        PACKETS is a list containing (address, packet) tuples.  These packets are effectively
        delayed until a message matching PATTERN was received.

        When a timeout is received this Trigger is removed and PACKETS are lost.
        """
        if __debug__:
            assert isinstance(pattern, str)
            assert hasattr(callback, "__call__")
            assert isinstance(packets, list)
            assert len(packets) > 0
            for packet in packets:
                assert isinstance(packet, tuple)
                assert len(packet) == 2
                assert isinstance(packet[0], tuple)
                assert len(packet[0]) == 2
                assert isinstance(packet[0][0], str)
                assert isinstance(packet[0][1], int)
                assert isinstance(packet[1], str)
        if __debug__: dprint("create new trigger for ", len(packets), " packets")
        self._pattern = pattern
        self._match = expression_compile(pattern).match
        self._callback = callback
        self._packets = packets

    def extend(self, pattern, packets):
        """
        When this trigger has the same pattern we will extend with packets and return True.
        """
        if __debug__:
            assert isinstance(pattern, str)
            assert isinstance(packets, list)
            assert len(packets) > 0
            for packet in packets:
                assert isinstance(packet, tuple)
                assert len(packet) == 2
                assert isinstance(packet[0], tuple)
                assert len(packet[0]) == 2
                assert isinstance(packet[0][0], str)
                assert isinstance(packet[0][1], int)
                assert isinstance(packet[1], str)
        if pattern == self._pattern:
            self._packets.extend(packets)
            if __debug__: dprint("extend existing trigger with ", len(packets), " packets (now has ", len(self._packets), " packets)")
            return True
        else:
            return False

    def on_messages(self, messages):
        assert isinstance(messages, list)
        assert len(messages) > 0
        if self._match:
            for message in messages:
                # if __debug__:
                #     dprint("Does it match? ", bool(self._match and self._match(message.footprint)), " for ", len(self._packets), " waiting packets")
                #     dprint("Expression: ", self._pattern)
                #     dprint(" Footprint: ", message.footprint)
                if self._match(message.footprint):
                    # set self._match to None to avoid this regular expression again
                    self._match = None

                    if __debug__: dprint("match footprint for ", len(self._packets), " waiting packets")
                    self._callback(self._packets)
                    # False to remove the Trigger, because we handled the Trigger
                    return False
                else:
                    # True to keep the Trigger, because we did not handle the Trigger yet
                    return True
        else:
            # False to remove the Trigger, because the Trigger timed-out
            return False

    def on_timeout(self):
        if self._match:
            if __debug__: dprint("timeout on trigger with ", len(self._packets), " packets", level="warning")
            self._match = None

class TriggerMessage(Trigger):
    def __init__(self, pattern, callback, messages):
        """
        Receiving a message matching PATTERN triggers a call to the on_incoming_message message with
        ADDRESS and MESSAGE.

        PATTERN is a python regular expression string.

        CALLBACK is called when PATTERN matches the incoming message footprint.  As an argument it
        receives MESSAGES.

        MESSAGES is a list with Message.Implementation instances.  These messages are effectively
        delayed until a message matching PATTERN is received.

        When a timeout is received this Trigger is removed MESSAGES are lost.
        """
        if __debug__:
            from message import Message
        assert isinstance(pattern, str)
        assert hasattr(callback, "__call__")
        assert isinstance(messages, list)
        assert len(messages) > 0
        assert not filter(lambda x: not isinstance(x, Message.Implementation), messages)
        if __debug__:
            dprint("create new trigger for ", len(messages), " messages")
            dprint("pattern: ", pattern)
        self._pattern = pattern
        self._match = expression_compile(pattern).match
        self._callback = callback
        self._messages = messages

    def extend(self, pattern, messages):
        """
        When this trigger has the same pattern we will extend with packets and return True.
        """
        if __debug__:
            from message import Message
        assert isinstance(pattern, str)
        assert isinstance(messages, list)
        assert len(messages) > 0
        assert not filter(lambda x: not isinstance(x, Message.Implementation), messages)
        if pattern == self._pattern:
            self._messages.extend(messages)
            if __debug__: dprint("extend existing trigger with ", len(messages), " messages (now has ", len(self._messages), " messages")
            return True
        else:
            return False

    def on_messages(self, messages):
        assert isinstance(messages, list)
        assert len(messages) > 0
        if self._match:
            for message in messages:
                # if __debug__:
                #     dprint("Does it match? ", bool(self._match and self._match(message.footprint)), " for ", len(self._messages), " waiting messages")
                #     dprint("Expression: ", self._pattern)
                #     dprint(" Footprint: ", message.footprint)
                if self._match(message.footprint):
                    # set self._match to None to avoid this regular expression again
                    self._match = None

                    if __debug__: dprint("match footprint for ", len(self._messages), " waiting messages")
                    self._callback(self._messages)
                    # False to remove the Trigger, because we handled the Trigger
                    return False
                else:
                    # True to keep the Trigger, because we did not handle the Trigger yet
                    return True
        else:
            # False to remove the Trigger, because the Trigger timed-out
            return False

    def on_timeout(self):
        if self._match:
            if __debug__: dprint("timeout on trigger with ", len(self._messages), " messages", level="warning")
            self._match = None

from functools import wraps

from ipv8.lazy_community import lazy_wrapper
from ipv8.messaging.lazy_payload import VariablePayload


def make_protocol_decorator(protocol_attr_name):
    """
    A decorator factory that generates a lazy_wrapper-analog decorator for a specific IPv8 protocol.

    IPv8 has `lazy_wrapper` decorator that can be applied to a community methods to handle deserialization
    of incoming IPv8 messages. It cannot be used in classes that are not instances of Community.

    make_prococol_decorator generates a similar decorator to a protocol class that is not a community,
    but used inside a community. A protocol should be an attribute of a community, and you need to specify
    the name of this attribute when calling make_protocol_decorator.

    Example of usage:

    >>> from ipv8.community import Community
    >>> message_handler = make_protocol_decorator('my_protocol')
    >>> class MyProtocol:
    ...     @message_handler(VariablePayload1)
    ...     def on_receive_message1(self, peer, payload):
    ...         ...
    ...     @message_handler(VariablePayload2)
    ...     def on_receive_message2(self, peer, payload):
    ...         ...
    >>> class MyCommunity(Community):
    ...     def __init__(self, *args, **kwargs):
    ...         super().__init__()
    ...         self.my_protocol = MyProtocol(...)  # the name should be the same as in make_protocol_decorator
    ...
    """

    def protocol_decorator(packet_type):
        def actual_decorator(func):
            def inner(community, peer, payload):
                # IPv8 always calls a registered packet handler with a Community instance as a first argument.
                # In order to call the protocol method we need to replace the community with the protocol instance.
                # We try to find the protocol instance in the community. It should be stored in the attribute
                # that name is specified in the `protocol_atr_name` parameter of the decorator's factory.
                protocol = getattr(community, protocol_attr_name, None)
                if not protocol:
                    raise TypeError(f'The {community.__class__.__name__} community '
                                    f'does not have the `{protocol_attr_name}` attribute!')

                return func(protocol, peer, payload)

            lazy_wrapped = lazy_wrapper(packet_type)(inner)

            @wraps(func)
            def outer(protocol, peer, payload):
                if isinstance(payload, bytes):
                    # The function was called by IPv8 for processing an incoming message.
                    # Let's use the lazy_wrapper machinery to deserialize the payload and call the decorated function.
                    if not hasattr(protocol, 'community'):
                        raise TypeError('The protocol instance should have a `community` attribute')

                    return lazy_wrapped(protocol.community, peer, payload)

                if isinstance(payload, VariablePayload):
                    # The function is called manually (for example, in tests) and the payload is already deserialized.
                    # Let's call the function directly, no further preprocessing is necessary.
                    return func(protocol, peer, payload)

                raise TypeError(f'Incorrect payload type: {payload.__class__.__name__}')

            return outer

        return actual_decorator

    return protocol_decorator

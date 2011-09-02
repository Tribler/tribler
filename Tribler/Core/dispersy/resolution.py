from meta import MetaObject

class Resolution(MetaObject):
    class Implementation(MetaObject.Implementation):
        @property
        def footprint(self):
            return "Resolution"

    def setup(self, message):
        """
        Setup is called after the meta message is initially created.
        """
        if __debug__:
            from message import Message
        assert isinstance(message, Message)

    def generate_footprint(self):
        return "Resolution"

class PublicResolution(Resolution):
    """
    PublicResolution allows any member to create a message.
    """
    class Implementation(Resolution.Implementation):
        pass

class LinearResolution(Resolution):
    """
    LinearResolution allows only members that have a specific permission to create a message.
    """
    class Implementation(Resolution.Implementation):
        pass

class DynamicResolution(Resolution):
    """
    DynamicResolution allows the resolution policy to change.

    A special dispersy-dynamic-settings message needs to be created and distributed to change the
    resolution policy.  Currently the policy can dynamically switch between either PublicResolution
    and LinearResolution.
    """
    class Implementation(Resolution.Implementation):
        def __init__(self, meta, policy):
            """
            Create a DynamicResolution.Implementation instance.

            This object will contain the resolution policy used for a single message.  This message
            must use one of the available policies defined in the associated meta_message object.
            """
            assert isinstance(policy, (PublicResolution.Implementation, LinearResolution.Implementation))
            assert policy.meta in meta._policies
            super(DynamicResolution.Implementation, self).__init__(meta)
            self._policy = policy

        @property
        def default(self):
            return self._meta._default

        @property
        def policies(self):
            return self._meta._policies

        @property
        def policy(self):
            return self._policy

    def __init__(self, *policies):
        """
        Create a DynamicResolution instance.

        The DynamicResolution allows the resolution policy to change by creating and distributing a
        dispersy-dynamic-settings message.  The availabe policies is given by POLICIES.

        The first policy will be used by default until a dispersy-dynamic-settings message is
        received that changes the policy.

        Warning!  The order of the given policies is -very- important.  Each policy is assigned a
        number based on the order (0, 1, ... etc) and this number is used by the
        dispersy-dynamic-settings message to change the policies.

        @param *policies: A list with available policies.
        @type *policies: (Resolution, ...)
        """
        assert isinstance(policies, tuple)
        assert 0 < len(policies) < 255
        assert not filter(lambda x: not isinstance(x, (PublicResolution, LinearResolution)), policies)
        self._policies = policies

    @property
    def default(self):
        """
        Returns the default policy, i.e. policies[0].
        @rtype Resolution
        """
        return self._policies[0]

    @property
    def policies(self):
        """
        Returns a tuple containing all available policies.
        @rtype (Resolution, ...)
        """
        return self._policies

    def setup(self, message):
        if __debug__:
            assert message.undo_callback, "a message with DynamicResolution policy must have an undo callback"
        for policy in self._policies:
            policy.setup(message)

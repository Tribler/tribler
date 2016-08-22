from Tribler.Test.Community.AllChannel.test_allchannel_community import TestAllChannelCommunity


class TestAllChannelCompatibility(TestAllChannelCommunity):

    """When the backward compatibility flag
        has been disabled, the community should
        still pass all of the tests.
    """

    def setUp(self):
        super(TestAllChannelCompatibility, self).setUp()
        self.community1.compatibility_mode = False
        self.community2.compatibility_mode = False

# We don't want this class to run all of the
# original TestAllChannelCommunity tests again.
del TestAllChannelCommunity

from Tribler.Test.Community.Channel.test_channel_community import TestChannelCommunity


class TestChannelCompatibility(TestChannelCommunity):

    """When the backward compatibility flag
        has been disabled, the community should
        still pass all of the tests.
    """

    def setUp(self):
        super(TestChannelCompatibility, self).setUp()
        self.community1.compatibility_mode = False
        self.community2.compatibility_mode = False

# We don't want this class to run all of the
# original TestChannelCommunity tests again.
del TestChannelCommunity

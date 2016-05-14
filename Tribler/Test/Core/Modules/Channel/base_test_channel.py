from Tribler.Test.Core.base_test import TriblerCoreTest, MockObject


class BaseTestChannel(TriblerCoreTest):

    def setUp(self, annotate=True):
        """
        Setup some classes and files that are used by the tests in this module.
        """
        super(BaseTestChannel, self).setUp(annotate=annotate)

        self.fake_session = MockObject()
        self.fake_session.get_state_dir = lambda: self.session_base_dir
        self.fake_session.add_observer = lambda a, b, c: False

        fake_notifier = MockObject()
        fake_notifier.add_observer = lambda a, b, c, d: False
        fake_notifier.notify = lambda a, b, c, d: False
        self.fake_session.notifier = fake_notifier

        self.fake_channel_community = MockObject()
        self.fake_channel_community.get_channel_id = lambda: 42
        self.fake_channel_community.cid = 'a' * 20
        self.fake_channel_community.get_channel_name = lambda: "my fancy channel"

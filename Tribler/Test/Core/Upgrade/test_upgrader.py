from __future__ import absolute_import

from twisted.internet.defer import Deferred, inlineCallbacks

from Tribler.Core.Upgrade.upgrade import TriblerUpgrader
from Tribler.Core.simpledefs import NTFY_STARTED, NTFY_UPGRADER_TICK
from Tribler.Test.Core.Upgrade.upgrade_base import AbstractUpgrader
from Tribler.Test.tools import trial_timeout


class TestUpgrader(AbstractUpgrader):

    @inlineCallbacks
    def setUp(self):
        yield super(TestUpgrader, self).setUp()
        self.upgrader = TriblerUpgrader(self.session)

    def test_run(self):
        """
        Test the run method of the upgrader
        """
        def check_should_upgrade():
            self.upgrader.failed = True
            return True, False
        self.upgrader.session.config.get_upgrader_enabled = lambda: True
        self.upgrader.check_should_upgrade_database = check_should_upgrade

        self.upgrader.run()
        self.assertTrue(self.upgrader.notified)

    @trial_timeout(10)
    def test_update_status_text(self):
        test_deferred = Deferred()

        def on_upgrade_tick(subject, changetype, objectID, status_text):
            self.assertEqual(status_text, "12345")
            test_deferred.callback(None)

        self.session.notifier.add_observer(on_upgrade_tick, NTFY_UPGRADER_TICK, [NTFY_STARTED])
        self.upgrader.update_status("12345")
        return test_deferred

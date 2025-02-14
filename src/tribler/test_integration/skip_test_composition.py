import itertools
import unittest

from ipv8.test.base import TestBase

from tribler.core.session import Session
from tribler.test_unit.mocks import MockTriblerConfigManager
from tribler.tribler_config import DEFAULT_CONFIG


@unittest.skip("35 minute test (1023 cases): run this once in a while, not by default")
class TestSessionComposition(TestBase):
    """
    An integration test for different Session compositions by users.
    """

    MAX_TEST_TIME = 3600

    def setUp(self) -> None:
        """
        Setup all possible subpairings of config settings.
        """
        super().setUp()

        self.config = MockTriblerConfigManager()
        self.config.set("ipv8/logger/level", "ERROR")
        self.config.set("ipv8/interfaces", [{"interface": "UDPIPv4", "ip": "127.0.0.1", "port": 0}])

        targets = []
        for entry, value in DEFAULT_CONFIG.items():
            if isinstance(value, dict) and "enabled" in value:
                targets.append(entry)
                self.config.set(f"{entry}/enabled", True)  # Start all on
        self.config_pairings = []
        for i in range(1, len(targets)):
            for t in itertools.combinations(targets, i):
                if t:
                    self.config_pairings.append(t)

    def reset_config(self) -> None:
        """
        Reset all enabled values to "True" in the config.
        """
        for entry, value in DEFAULT_CONFIG.items():
            if isinstance(value, dict) and "enabled" in value:
                self.config.set(f"{entry}/enabled", True)

    async def test_compositions(self) -> None:
        """
        Check if all compositions are able to launch without crashing.
        """
        for target in self.config_pairings:
            with self.subTest(target=target):
                self.reset_config()
                for entry in target:
                    self.config.set(f"{entry}/enabled", False)
                session = Session(self.config)
                await session.start()
                session.shutdown_event.set()
                await session.shutdown()

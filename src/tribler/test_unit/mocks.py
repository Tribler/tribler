from tribler.tribler_config import TriblerConfigManager


class MockTriblerConfigManager(TriblerConfigManager):
    """
    A memory-based TriblerConfigManager.
    """

    def write(self) -> None:
        """
        Don't actually write to any file.
        """

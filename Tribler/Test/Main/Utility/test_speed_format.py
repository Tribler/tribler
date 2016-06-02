from Tribler.Test.test_as_server import AbstractServer
from Tribler.Main.Utility.utility import speed_format

Unit = 1024
KB = Unit
MB = KB * Unit
GB = MB * Unit
TB = GB * Unit
PB = TB * Unit
EB = PB * Unit


class TriblerMainUtilitySpeedFormat(AbstractServer):

    def test_speed_format_bytes(self):
        result = speed_format(Unit * 0.5)
        self.assertEqual("0.5 KB/s", result)

    def test_speed_format_kilo_bytes(self):
        result = speed_format(12 * KB)
        self.assertEqual("12.0 KB/s", result)

    def test_speed_format_more_kilo_bytes(self):
        result = speed_format(123 * KB)
        self.assertEqual("123 KB/s", result)

    def test_speed_format_almost_mega_byte(self):
        result = speed_format(1 * MB - 2 * KB)
        self.assertEqual("1.0 MB/s", result)

    def test_speed_format_mega_byte(self):
        result = speed_format(12 * MB)
        self.assertEqual("12.0 MB/s", result)

    def test_speed_format_more_mega_bytes(self):
        result = speed_format(123 * MB)
        self.assertEqual("123 MB/s", result)

    def test_speed_format_almost_giga_byte(self):
        result = speed_format(1 * GB - 2 * MB)
        self.assertEqual("1.0 GB/s", result)

    def test_speed_format_giga_byte(self):
        result = speed_format(12 * GB)
        self.assertEqual("12.0 GB/s", result)

    def test_speed_format_more_giga_bytes(self):
        result = speed_format(123 * GB)
        self.assertEqual("123 GB/s", result)

    def test_speed_format_almost_terra_byte(self):
        result = speed_format(1 * TB - 2 * GB)
        self.assertEqual("1.0 TB/s", result)

    def test_speed_format_terra_byte(self):
        result = speed_format(12 * TB)
        self.assertEqual("12.0 TB/s", result)

    def test_speed_format_more_terra_bytes(self):
        result = speed_format(123 * TB)
        self.assertEqual("123.0 TB/s", result)

    def test_speed_format_none(self):
        result = speed_format(None)
        self.assertEqual("", result)

    def test_speed_format_negative_mega_byte(self):
        result = speed_format(-12 * MB)
        self.assertEqual("-12.0 MB/s", result)

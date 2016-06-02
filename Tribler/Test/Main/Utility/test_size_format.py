from Tribler.Test.test_as_server import AbstractServer
from Tribler.Main.Utility.utility import size_format

Unit = 1024
KB = Unit
MB = KB * Unit
GB = MB * Unit
TB = GB * Unit
PB = TB * Unit
EB = PB * Unit


class TriblerMainUtilitySizeFormat(AbstractServer):

    def test_size_format_bytes(self):
        result = size_format(123)
        self.assertEqual("0.12 KB", result)

    def test_size_format_kilo_bytes(self):
        result = size_format(123 * KB)
        self.assertEqual("123.00 KB", result)

    def test_size_format_mega_bytes(self):
        result = size_format(123 * MB)
        self.assertEqual("123.00 MB", result)

    def test_size_format_giga_bytes(self):
        result = size_format(123 * GB)
        self.assertEqual("123.00 GB", result)

    def test_size_format_terra_bytes(self):
        result = size_format(123 * TB)
        self.assertEqual("123.00 TB", result)

    def test_size_format_bytes_textonly(self):
        # this one is an odd one out, the textonly option returns Byte as unit instead of B
        result = size_format(123, textonly=True, showbytes=True)
        self.assertEqual("Byte", result)

    def test_size_format_kilo_bytes_textonly(self):
        result = size_format(123 * KB, textonly=True)
        self.assertEqual("KB", result)

    def test_size_format_bytes_labelonly(self):
        # this one is regular again as opposed to the textonly version
        result = size_format(123, labelonly=True, showbytes=True)
        self.assertEqual("B", result)

    def test_size_format_kilo_bytes_labelonly(self):
        result = size_format(123 * KB, labelonly=True)
        self.assertEqual("KB", result)

    def test_size_format_bytes_showbytes(self):
        result = size_format(123, showbytes=True)
        self.assertEqual("123 B", result)

    def test_size_format_kilo_bytes_showbytes(self):
        result = size_format(123 * KB, showbytes=True)
        # This might not be what one expects, however currently the input has to be smaller than KB to show as bytes
        self.assertEqual("123.00 KB", result)

    def test_size_format_bytes_textonly_showbytes(self):
        result = size_format(123, textonly=True, showbytes=True)
        self.assertEqual("Byte", result)

    def test_size_format_kilo_bytes_labelonly_showbytes(self):
        result = size_format(123 * KB, labelonly=True, showbytes=True)
        self.assertEqual("KB", result)

    def test_size_format_terra_bytes_stopearly(self):
        result = size_format(123 * TB, stopearly="B")
        self.assertEqual("135239930216448 B", result)

    def test_size_format_terra_bytes_stopearly_byte(self):
        result = size_format(123 * TB, stopearly="Byte")
        self.assertEqual("135239930216448 B", result)

    def test_size_format_terra_bytes_stopearly_kb(self):
        result = size_format(123 * TB, stopearly="KB")
        self.assertEqual("132070244352.00 KB", result)

    def test_size_format_terra_bytes_stopearly_mb(self):
        result = size_format(123 * TB, stopearly="MB")
        self.assertEqual("128974848.00 MB", result)

    def test_size_format_terra_bytes_stopearly_gb(self):
        result = size_format(123 * TB, stopearly="GB")
        self.assertEqual("125952.00 GB", result)

    def test_size_format_bytes_size(self):
        result = size_format(123, rawsize=True, showbytes=True)
        self.assertEqual(123, result)

    def test_size_format_kilo_bytes_size(self):
        result = size_format(123 * KB, rawsize=True)
        self.assertEqual(123, result)

    def test_size_format_mega_bytes_size(self):
        result = size_format(123 * MB, rawsize=True)
        self.assertEqual(123, result)

    def test_size_format_giga_bytes_size(self):
        result = size_format(123 * GB, rawsize=True)
        self.assertEqual(123, result)

    def test_size_format_terra_bytes_size(self):
        result = size_format(123 * TB, rawsize=True)
        self.assertEqual(123, result)

    def test_size_format_giga_bytes_truncate_0(self):
        result = size_format(123.123 * GB, truncate=0)
        self.assertEqual("123 GB", result)

    def test_size_format_giga_bytes_truncate_1(self):
        result = size_format(123.123 * GB, truncate=1)
        self.assertEqual("123.1 GB", result)

    def test_size_format_giga_bytes_truncate_2(self):
        result = size_format(123.123 * GB, truncate=2)
        self.assertEqual("123.12 GB", result)

    def test_size_format_giga_bytes_no_label(self):
        result = size_format(123.123 * GB, applylabel=False)
        self.assertEqual("123.12", result)

    def test_size_format_negative(self):
        result = size_format(-123 * MB)
        self.assertEqual("-123.00 MB", result)

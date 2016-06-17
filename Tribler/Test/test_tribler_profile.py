import os
import tempfile

from Tribler.Main.tribler_profiler import run_tribler_with_yappi
from Tribler.Test.test_as_server import AbstractServer


class TestTriblerProfile(AbstractServer):
    def test_profile_yappi_environment_set(self):
        temp_dir = tempfile.mkdtemp()
        os.environ['YAPPI_OUTPUT_DIR'] = temp_dir

        def a_simple_loop():
            for _ in range(0, 10):
                pass

        run_tribler_with_yappi(a_simple_loop)
        self.assertTrue(os.path.exists(os.path.join(temp_dir, 'yappi.callgrind')))

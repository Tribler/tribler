import unittest

from Tribler.community.privatesearch.oneswarm.OverlayManager import RandomnessManager

class TestRandomness(unittest.TestCase):
    def setUp(self):
        self.randomness = RandomnessManager()

    def tearDown(self):
        del self.randomness

    def test_deterministic_random(self):
        val1 = self.randomness.getDeterministicRandomInt(1l)
        val2 = self.randomness.getDeterministicRandomInt(2l)
        val3 = self.randomness.getDeterministicRandomInt(2l)

        assert val2 == val3, (val2, val3)
        assert val1 != val2, (val1, val2)

    def test_deterministic_next(self):
        val1 = self.randomness.getDeterministicNextInt(1l, 0, 5)
        val2 = self.randomness.getDeterministicNextInt(2l, 0, 5)
        val3 = self.randomness.getDeterministicNextInt(2l, 0, 5)

        assert val2 == val3, (val2, val3)
        assert val1 != val2, (val1, val2)

        assert 0 <= val1 < 5, val1
        assert 0 <= val2 < 5, val2

    def test_secretbytes(self):
        randomness2 = RandomnessManager()
        assert self.randomness.getSecretBytes() != randomness2.getSecretBytes()

if __name__ == "__main__":
    unittest.main()

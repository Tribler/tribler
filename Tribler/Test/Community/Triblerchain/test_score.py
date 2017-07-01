"""
This module tests the calculation of the node score.
"""
from unittest import TestCase

from Tribler.community.triblerchain.score import calculate_score, BOUNDARY_VALUE


class TestScore(TestCase):
    """
    Test the score calculation.
    """
    def test_calculate_score_below(self):
        """
        Validate whether the lower boundary works.
        """
        self.assertEqual(0, calculate_score(0, BOUNDARY_VALUE + 1))

    def test_calculate_score_above(self):
        """
        Validate whether the upper boundary works.
        """
        self.assertEqual(1, calculate_score(BOUNDARY_VALUE + 1, 0))

    def test_calculate_score_between(self):
        """
        Validate whether the calculation within the boundary works.
        """
        self.assertEqual(0.75, calculate_score(BOUNDARY_VALUE / 2, 0))

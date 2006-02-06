import os
import unittest
from sets import Set

from Tribler.BuddyCast.buddycast import BuddyCast

class TestBuddyCast(unittest.TestCase):
    """ 
    Testing buddycast includes two steps:
        1. Test buddycast algorithm
        2. Test buddycast communication functionalities
    Here we can only test step 1.
    """
    
    def setUp(self):
        pass
    
    def tearDown(self):
        pass
    
    def test_algorithm(self):
        pass    
    
    
    
def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestBuddyCast))
    
    return suite

    
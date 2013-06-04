import unittest

if __name__ == 'Tribler.Test.TUPT.test_TUPT':
    all_tests = unittest.TestLoader().discover('.',pattern='test*.py')
    unittest.TextTestRunner().run(all_tests)
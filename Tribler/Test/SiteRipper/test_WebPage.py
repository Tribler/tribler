import unittest
from Tribler.SiteRipper.WebPage import WebPage

class TestWebPage(unittest.TestCase):

    def test_getURLName(self):
        #Act
        result = WebPage.getURLName('google.nl_.html')
        #Assert
        self.assertEqual('http://www.google.nl/', result)

if __name__ == '__main__':
    unittest.main()
    
    
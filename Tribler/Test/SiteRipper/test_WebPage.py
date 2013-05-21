import unittest
from Tribler.SiteRipper.WebPage import WebPage

class TestWebPage(unittest.TestCase):

    def test_GetURLName(self):
        #Act
        result = WebPage.GetURLName('google.nl_.html')
        #Assert
        self.assertEqual('http://www.google.nl/', result)
        
    def test_GetFileNameRemoveHTTP(self):
        #Arrange
        testURL = 'http://google.com'
        #Act
        result = WebPage.GetFileName(testURL)
        #Assert
        self.assertEqual('google.com', result)
    
    def test_GetFileNameRemoveWWW(self):
        #Arrange
        testURL = 'http://www.google.com'
        #Act
        result = WebPage.GetFileName(testURL)
        #Assert
        self.assertEqual('google.com', result)
    
    def test_GetFileNameReplaceSlash(self):
        #Arrange
        testURL = 'http://www.google.com/test'
        #Act
        result = WebPage.GetFileName(testURL)
        #Assert
        self.assertEqual('google.com_test', result)
        
    def test_GetTarName(self):
        #Arrange
        testURL = 'http://www.google.com/test'
        #Act
        result = WebPage.GetTarName(testURL)
        #Assert
        self.assertEqual('google.com_test.tar.gz', result)

if __name__ == '__main__':
    unittest.main()
    
    
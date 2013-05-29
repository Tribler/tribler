import unittest

from Tribler.TUPT.Parser.ParserControl import ParserControl
from Tribler.TUPT.Parser.ParserControl import NoParserFoundException
from Tribler.TUPT.Parser.IParserPlugin import IParserPlugin
from Tribler.TUPT.Movie import Movie

from Tribler.Test.TUPT.test_StubPluginManager import PluginManagerStub

class TestParserControl(unittest.TestCase):
    '''Test class to test the ParserControl.'''
    
    def test_HasParser_NoPlugin(self):
        '''Test to HasParser when it has No Plugin. Should return false'''
        #Arrange        
        parserControl = ParserControl(PluginManagerStub(False))
        #Act
        result = parserControl.HasParser("url.com")
        #Assert
        self.assertFalse(result)
        
    def test_HasParser_HasPlugin(self):
        '''Test to HasParser when it has No Plugin. Should return false'''
        #Arrange        
        parserControl = ParserControl(PluginManagerStub(False))
        #Act
        result = parserControl.HasParser("something.com")
        #Assert
        self.assertTrue(result)       
        
    def test_ParseWebsite_NoResult(self):
        '''Test ParseWebsite and no result is found'''
        #Arrange
        parserControl = ParserControl(PluginManagerStub(False))
        #Act
        result = parserControl.ParseWebsite("something.com", 'NaN')
        #Assert
        self.assertEqual(None, result)
    
    def test_ParseWebsite_Result(self):
        '''Test ParseWebsite and a result is found'''
        #Arrange
        parserControl = ParserControl(PluginManagerStub(True))
        #Act
        result = parserControl.ParseWebsite("something.com", 'NaN')
        #Assert
        self.assertEqual('TestMovie', result.dictionary['title'])
    
    def test_ParseWebsite_NoParserFoundException(self):
        '''Test ParseWebsite to throw an exception when no parser is available'''
        #Arrange
        parserControl = ParserControl(PluginManagerStub(True))
        #Act and Assert
        with self.assertRaises(NoParserFoundException):
            result = parserControl.ParseWebsite("url.com", 'NaN')
        

    
    
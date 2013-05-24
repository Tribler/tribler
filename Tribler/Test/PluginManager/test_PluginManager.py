import unittest
import os

from yapsy.IPlugin import IPlugin

from Tribler.PluginManager.PluginManager import PluginManager

class TestPluginManager(unittest.TestCase):
    '''Test class to test PluginManager'''

    def test_LoadPlugin(self):
        '''Test loading and interacting with a plugin'''
        #Arrange
        manager = PluginManager()
        manager.OverwritePluginsFolder(os.getcwd())
        manager.RegisterCategory("TestPlugin1", IPlugin)
        manager.LoadPlugins()
        #Act
        plugins = manager.GetPluginsForCategory("TestPlugin1")
        #Assert     
        assert len(plugins)==1
        assert plugins[0].identifier == "UNIT_TEST_1_TESTPLUGIN"
           
if __name__ == '__main__':
    unittest.main()
    
    
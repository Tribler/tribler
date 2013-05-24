from yapsy.IPlugin import IPlugin

class TestPlugin(IPlugin):
    
    identifier = "UNIT_TEST_1_TESTPLUGIN"

    def repeat(self, number):
        return number
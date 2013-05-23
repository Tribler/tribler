from yapsy.IPlugin import IPlugin as yIPlugin

class IStubPlugin(yIPlugin):
    """Provide a stubbed plugin for testing purposes
    """
    
    def activate():
    	pass
    	
    def deactivate():
    	pass
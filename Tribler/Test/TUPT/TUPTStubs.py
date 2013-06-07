import time

from Tribler.TUPT.Parser.IParserPlugin import IParserPlugin
from Tribler.TUPT.Movie import Movie
from Tribler.TUPT.TorrentFinder.IMovieTorrentDef import IMovieTorrentDef
from Tribler.TUPT.TorrentFinder.ITorrentFinderPlugin import ITorrentFinderPlugin

class PluginManagerStub():
        
    def GetPluginDescriptorsForCategory(self, category):
        return []
    
    def GetPluginFolder(self):
        return "NaN"
 
class PluginStub:
    
    def __init__(self):
        self.plugin_object = self
        self.details = PluginDetailsStub()
 
class PluginDetailsStub():

    def getfloat(self, section, option):
        return 1.0
 
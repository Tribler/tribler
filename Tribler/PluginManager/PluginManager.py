import os

from yapsy.PluginManager import PluginManager as yPluginManager

from Tribler.Core.Session import Session 

class PluginManager:
    """Manager for user plug-ins.
        Plug-ins are to be placed in the folder:
        /%appdata%/.Tribler/plug-ins/%category%/
        For every registered category.
        
        For example, one could register a 'Fish' category,
        which would require users to put their plug-ins in the
        /%appdata%/.Tribler/plug-ins/Fish/ folder.
    """
    
    __yapsyManager = None           #Yapsy's Plugin Manager (back-end)
    
    __pluginsFolder = None          #The /.Tribler/plug-ins folder
    
    __categoryFolders = None        #Dictionary of categoryname -> categoryfolder  
    __categoryInterfaces = None     #Dictionary of categoryname -> IPlugin interface
    
    __singleton = None              #Singleton accessor, if claimed
    
    @staticmethod
    def GetInstance():
        return PluginManager.__singleton
    
    def RegisterAsSingleton(self):
        """Register this PluginManager as the only one in the system
        """
        PluginManager.__singleton = self
    
    def __init__(self):
        self.__yapsyManager = yPluginManager()
        
        profileFolder = Session.get_default_state_dir()
        self.__pluginsFolder = profileFolder + os.sep + 'plug-ins'
        
        self.__categoryFolders = {}
        self.__categoryInterfaces = {}
    
    def __CategoryFolder(self, categoryName):    
        return self.__pluginsFolder + os.sep + categoryName
    
    def OverwritePluginsFolder(self, folder):
        """By default we store plug-ins in Triblers profile folder.
            If you want to overwrite this (for testing for example) use
            this method
        """
        self.__pluginsFolder = folder
    
    def RegisterCategory(self, categoryName, interface):
        """Register a category for loading with LoadPlugins()
            Returns True if a category was created
            Returns False if the plug-in directory could not be found
        """
        if os.path.exists(self.__CategoryFolder(categoryName)):
            self.__categoryFolders[categoryName] = self.__CategoryFolder(categoryName)
            self.__categoryInterfaces[categoryName] = interface
            return True
        return False
        
    def GetCategories(self):
        """Return all registered categories
        """
        return self.__yapsyManager.getCategories()
    
    def CategoryExists(self, categoryName):
        """Return True if and only if categoryName is a successfully registered
            category name.
        """
        return categoryName in self.GetCategories()
        
    def LoadPlugins(self):
        """Loads plugins from registered categories
            Folder structure is /%appdata%/.Tribler/plug-ins/%category%/
        """
        self.__yapsyManager.setPluginPlaces(self.__categoryFolders.values())
        self.__yapsyManager.setCategoriesFilter(self.__categoryInterfaces)
        self.__yapsyManager.collectPlugins()
        
    def GetPluginsForCategory(self, categoryName):
        """Returns all plug-in objects for a certain category
        """
        out = []
        if not self.CategoryExists(categoryName):
            return out
        for pluginWrapper in self.__yapsyManager.getPluginsOfCategory(categoryName):
            out.append(pluginWrapper.plugin_object)
        return out
    
    def GetAllPluginDescriptors(self):
        """Returns all the description objects for loaded plug-ins.
        """
        return self.__yapsyManager.getAllPlugins()
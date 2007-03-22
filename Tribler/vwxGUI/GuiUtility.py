import wx
from wx import xrc
from bgPanel import *
import updateXRC
from Tribler.Dialogs.abcfileframe import TorrentDataManager
from Tribler.utilities import *

DEBUG = True

    
class GUIUtility:
    __single = None

    def __init__(self, utility = None, params = None):
        if GUIUtility.__single:
            raise RuntimeError, "GUIUtility is singleton"
        GUIUtility.__single = self 
        # do other init
        self.guiObjects = {}
        self.xrcResource = None
        self.utility = utility
        self.params = params
        self.data_manager = TorrentDataManager.getInstance(self.utility)
        self.data_manager.register(self.updateFun, 'all')
            
    def getInstance(*args, **kw):
        if GUIUtility.__single is None:
            GUIUtility(*args, **kw)
        return GUIUtility.__single
    getInstance = staticmethod(getInstance)
    
    def report(self, object):
        name = object.__class__.__name__
        try:
            instanceName = object.GetName()
        except:
            instanceName = ''
            
        self.guiObjects[(name, instanceName)] = object
        if DEBUG:
            print '%s reported' % name
        self.checkAllLoaded()
        
    def checkAllLoaded(self):
        if DEBUG:
            print self.guiObjects.keys()
        if len(self.guiObjects) == 5:
            self.initGUI()
            
    
    def request(self, name):
        if name == 'standardGrid':
            name = 'torrentGrid'
        obj = self.guiObjects.get((name, name))
        if obj:
            return obj
        else:
            if DEBUG:
                print "GUIUtility could not offer object %s.\nIt has only %s" % (name, [obj.__class__.__name__ for obj in self.guiObjects.values()])
            return None
        
    def getCategories(self):
        return ['aap', 'noot', 'mies']
  
    def setCategory(self, cat):
        print 'Category set to %s' % cat
        
    def buttonClicked(self, event):
        "One of the buttons in the GUI has been clicked"
        obj = event.GetEventObject()
        if DEBUG:
            print 'Button clicked'
        
        try:
            name = obj.GetName()
        except:
            print 'Error: Could not get name of buttonObject: %s' % obj
        if name == 'mainButtonFiles':
            self.standardFilesOverview()
        elif name == 'mainButtonPersons':
            self.standardPersonsOverview()
        elif name == 'mainButtonProfile':
            self.standardProfileOverview()
        elif name == 'mainButtonLibrary':
            self.standardLibraryOverview()
        elif name == 'mainButtonFriends':
            self.standardFriendsOverview()
        elif name == 'mainButtonMessages':
            self.standardMessagesOverview()
        else:
            print 'A button was clicked, but no action is defined for: %s' % name
                
        
    def standardFilesOverview(self):
        torrentList = self.reloadData()
        overview = self.request('standardOverview')
        overview.setMode('filesMode', torrentList)
        
    def standardPersonsOverview(self):
        personsList = self.reloadData()
        overview = self.request('standardOverview')
        overview.setMode('personsMode', personsList)
        

    def reloadData(self):
        
        # load content category
        self.categorykey = 'all'
        self.data = self.data_manager.getCategory(self.categorykey)
        self.filtered = []
        for torrent in self.data:
            if torrent.get('status') == 'good' or torrent.get('myDownloadHistory'):
                self.filtered.append(torrent)
        
        self.filtered = sort_dictlist(self.filtered, 'swarmsize', 'decrease')
        print self.filtered
        return self.filtered
        
    def updateFun(self, torrent, operate):    
        print "Updatefun called"
        
    def initGUI(self):
        "This function initializes all gui tak"
        if DEBUG:
            print 'Init business logic'
            print self.guiObjects
        # Do stuff like:
        # - loading first mode
        # - set detailpanel data
        # - init other stuff
        
    
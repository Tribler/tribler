import wx
from wx import xrc
from bgPanel import *
import updateXRC

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
        if DEBUG:
            print 'Button clicked'
            print event;
        obj = event.GetEventObject()
        try:
            name = obj.GetName()
            overview = self.request('standardOverview')
            if name == 'tribler_topButton0':
                overview.setMode('torrentMode')
            elif name == 'tribler_topButton1':
                overview.setMode('personsMode')
                
        except:
            pass
    
    def initGUI(self):
        "This function initializes all gui tak"
        if DEBUG:
            print 'Init business logic'
            print self.guiObjects
        # Do stuff like:
        # - loading first mode
        # - set detailpanel data
        # - init other stuff
        
    
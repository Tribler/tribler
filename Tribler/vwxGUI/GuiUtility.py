import wx
from wx import xrc
from tribler_topButton import *
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
        self.utility = utility
        self.params = params
            
    def getInstance(*args, **kw):
        if GUIUtility.__single is None:
            GUIUtility(*args, **kw)
        return GUIUtility.__single
    getInstance = staticmethod(getInstance)
    
    def report(self, object):
        name = object.__class__.__name__
        self.guiObjects[name] = object
        if DEBUG:
            print '%s reported' % name
    
    def request(self, name):
        if name == 'standardGrid':
            name = 'torrentGrid'
        obj = self.guiObjects.get(name)
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
        print 'Button clicked';
        print event;
    
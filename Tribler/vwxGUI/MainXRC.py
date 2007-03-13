import wx
from wx import xrc
from tribler_topButton import *
from bgPanel import *
import updateXRC

DEBUG = True

class MyApp(wx.App):
    def OnInit(self):
        self.res = xrc.XmlResource("MyFrame.xrc")
        self.InitFrame()
        return True
    
    def InitFrame(self):
        try:
            self.frame = self.res.LoadFrame(None, "MyFrame")
        except:
            pass
        #self.panel = xrc.XRCCTRL(self.frame, 'sw118c')
        #print self.panel.GetChildren()
        #print self.panel
        
        self.SetTopWindow(self.frame)
        self.frame.Show(1)
        

def main():
    updateXRC.main(None)
    app = MyApp(0)
    app.MainLoop()
if __name__ == '__main__':
    main()
    
    
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
        obj = self.guiObjects.get(name)
        if obj:
            return obj
        else:
            if DEBUG:
                print "GUIUtility could not offer object %s.\nIt has only %s" % (name, self.guiObjects)
            return None
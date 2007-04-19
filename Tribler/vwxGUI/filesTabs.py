import wx, os, sys
import wx.xrc as xrc

from Tribler.vwxGUI.GuiUtility import GUIUtility
from wx.lib.stattext import GenStaticText as StaticText

class filesTabs(wx.Panel):
    """
    StandardTab shows the content categories and delegates the ContentFrontPanel
    to load the right torrent data in the gridPanel
    """

    def __init__(self, *args):
        if len(args) == 0:
            pre = wx.PrePanel()
            # the Create step is done by XRC.
            self.PostCreate(pre)
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)
        else:
            wx.Panel.__init__(self, args[0], args[1], args[2], args[3])
            self._PostInit()
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    

    def _PostInit(self):
         
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.categories = self.guiUtility.getCategories()
        self.addComponents()
        #self.SetBackgroundColour(wx.GREEN)
        self.SetMinSize((-1, 30))
        self.Show()
        self.Refresh()
        self.Update()
        
    def addComponents(self):
        self.Show(False)
        self.SetBackgroundColour(wx.WHITE)
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        self.unselFont = wx.Font(10, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName="Verdana")
        self.selFont = wx.Font(10, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, faceName="Verdana")
        self.orderUnselFont = wx.Font(10, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL, faceName="Verdana")
        self.orderSelFont = wx.Font(10, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_BOLD, faceName="Verdana")
        
        # Categories
        self.catSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        for cat in self.categories:
            catPanel = wx.Panel(self, -1, size=wx.Size(50,50))
            catPanel.SetBackgroundColour(wx.Colour(212, 208, 200))
            catSizer = wx.BoxSizer(wx.HORIZONTAL)
            label = StaticText(catPanel,-1,cat.title())
            label.Bind(wx.EVT_LEFT_UP, self.mouseAction)
            label.SetFont(self.unselFont)
            catSizer.Add(label, 0, wx.LEFT|wx.RIGHT, 15)
            catPanel.SetSizer(catSizer)
            catPanel.SetAutoLayout(True)
            catPanel.Layout()
            self.catSizer.Add(catPanel, 0, wx.LEFT|wx.RIGHT|wx.TOP, 4)
            if cat == self.categories[0]:
                self.setSelected(label)
                self.lastSelected = label      
            
        self.SetSizer(self.catSizer);
        self.SetAutoLayout(1);
        self.Show(True)
        self.Layout()
        self.Refresh(True)
        self.Update()
        self.Enable()
           
    def mouseAction(self, event):
         
        obj = event.GetEventObject()
        #print 'Clicked on %s' % obj.GetLabel()
        if obj == self.lastSelected:
            return
        self.setSelected(obj)
        if self.lastSelected:
            self.setUnselected(self.lastSelected)
        self.guiUtility.setCategory(obj.GetLabel())
        self.lastSelected = obj
        
       
            
    def setSelected(self, obj):
        obj.SetFont(self.selFont)
        
    
    def setUnselected(self, obj):
        obj.SetFont(self.unselFont)
        
        

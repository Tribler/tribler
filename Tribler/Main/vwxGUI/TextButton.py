import wx, os, sys
from traceback import print_exc
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
#from wx.lib.stattext import GenStaticText

DEBUG = False

class TextButton(wx.Panel):
    """
    Button that changes the image shown if you move your mouse over it.
    It redraws the background of the parent Panel, if this is an imagepanel with
    a variable self.bitmap.
    """

    def __init__(self, *args, **kw):
        self.selected = False
        self.colours = [wx.Colour(102,102,102), wx.WHITE]
        if len(args) == 0:
            pre = wx.PrePanel() 
            # the Create step is done by XRC. 
            self.PostCreate(pre) 
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate) 
        else:
            wx.Panel.__init__(self, *args, **kw) 
            self._PostInit()     
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True

    def _PostInit(self):
        # Do all init here
        self.guiUtility = GUIUtility.getInstance()
        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
        self.Bind(wx.EVT_LEFT_UP, self.ClickedButton)
        if '_' in self.GetName():
            label = self.GetName()[:self.GetName().find('_')]
        else:
            label = self.GetName()
        
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.labelobj = wx.StaticText(self, -1, label)
        self.labelobj.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
        self.labelobj.Bind(wx.EVT_LEFT_UP, self.ClickedButton)

        
        self.sizer.Add(self.labelobj, 1, wx.ALIGN_LEFT|wx.LEFT|wx.RIGHT, 5)
        #self.SetLabel('  '+label)
        self.SetMinSize((60,-1))
        #self.SetSize(75,18)
        self.SetBackgroundColour(self.colours[int(self.selected)])    
        
        self.SetSizer(self.sizer)
        

        self.Refresh(True)
        self.Update()
        #self.Show()        
        
       
    def setSelected(self, sel):
        if sel != self.selected:
            self.selected = sel
            self.SetBackgroundColour(self.colours[int(sel)])
            self.Refresh()
#        print "<mluc> label:",self.GetLabel(),"and name:",self.GetName()
        
    def isSelected(self):
        return self.selected
        
    def mouseAction(self, event):
        event.Skip()
        if event.Entering() and not self.selected:
            #print 'TextButton: enter' 
            self.SetBackgroundColour(self.colours[1])
            self.Refresh()
        elif event.Leaving() and not self.selected:
            #print 'TextButton: leaving'
            self.SetBackgroundColour(self.colours[0])
            self.Refresh()

    def ClickedButton(self, event):
        name = self.GetName()
        event.Skip()
        #self.guiUtility.buttonClicked(event)
        self.guiUtility.detailsTabClicked(name)

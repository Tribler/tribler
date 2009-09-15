import wx
import os, sys


from Tribler.Main.vwxGUI.GuiUtility import GUIUtility

from Tribler.__init__ import LIBRARYNAME

class pageTitlePanel(wx.Panel):
    def __init__(self, *args,**kwds):
        if len(args) == 0:
            pre = wx.PrePanel()
            # the Create step is done by XRC.
            self.PostCreate(pre)
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)
        else:
            wx.Panel.__init__(self, *args)
            self._PostInit()
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True


    def _PostInit(self):
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility

        self.tl = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","5.0","tl2.png"))
        self.tr = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","5.0","tr2.png"))


        self.SetBackgroundColour((240, 240, 240)) # 240,240,240
        self.addComponents()


        if sys.platform != 'darwin':
            self.Show()
        self.roundCorners()
        self.Refresh()       

       
    def addComponents(self):
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)

        self.hSizer.Add((10,0), 0, 0, 0)


        self.pageTitle = wx.StaticText(self, -1, "File search", wx.Point(0,0), wx.Size(665, 20))
        self.pageTitle.SetForegroundColour((127, 127, 127)) # 127,127,127

        self.guiUtility.pageTitle = self.pageTitle

        self.hSizer.Add(self.pageTitle, 1, 0, 0)


        self.hSizer.Layout()
        self.SetSizer(self.hSizer)
        self.SetAutoLayout(True)


    def roundCorners(self):
        wx.EVT_PAINT(self, self.OnPaint)


    def OnPaint(self, event):
        dc = wx.PaintDC(self)
        dc.DrawBitmap(self.tl, 0, 0)
        dc.DrawBitmap(self.tr, 666, 0)


    def Initialize(self):
        self.SetBackgroundColour((240,240,240))
        self.pageTitle.SetForegroundColour((127,127,127))
        


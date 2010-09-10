# Written by Richard Gwin
import wx.html
import wx.xrc as xrc
import sys

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility

DEBUG = False

class SRstatusbar(wx.Panel):
    def __init__(self, *args, **kw):
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        
        self.elements = {}
        self.elementsName = ['help', \
                             'total_down', \
                             'total_up', \
                             'SRvalue', \
                             'firewallStatus14']

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
        for element in self.elementsName:
            xrcElement = xrc.XRCCTRL(self, element)
            if not xrcElement:
                print 'SRstatusbar: Error: Could not identify xrc element:',element
            self.elements[element] = xrcElement
        
        self.elements['help'].Bind(wx.EVT_LEFT_UP, self.helpClick)
 
    def helpClick(self,event=None):
        dlg = wx.Dialog(None, -1, self.utility.lang.get('sharing_reputation_information_title'), style=wx.DEFAULT_DIALOG_STYLE, size=(400,200))
        dlg.SetBackgroundColour(wx.WHITE)

        sizer = wx.FlexGridSizer(2,2)
        
        icon = wx.StaticBitmap(dlg, -1, wx.ArtProvider.GetBitmap(wx.ART_INFORMATION))
        sizer.Add(icon, 0, wx.TOP, 10)
        
        hwin = wx.html.HtmlWindow(dlg, -1, size = (350, 130))
        hwin.SetPage(self.utility.lang.get('sharing_reputation_information_message'))
        sizer.Add(hwin)
        
        sizer.Add((10,0))
        
        btn = wx.Button(dlg, wx.ID_OK, 'Ok')
        sizer.Add(btn, 0, wx.ALIGN_RIGHT, 5)
        
        border = wx.BoxSizer()
        border.Add(sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        dlg.SetSizerAndFit(border)
        dlg.ShowModal()
        dlg.Destroy()
        
    def set_reputation(self, reputation, down, up):
        if reputation < -0.33:
            self.elements['SRvalue'].SetForegroundColour((255,51,0))
            self.elements['SRvalue'].SetLabel("Poor")
        elif reputation < 0.33:
            self.elements['SRvalue'].SetForegroundColour(wx.BLACK)
            self.elements['SRvalue'].SetLabel("Average")
        else:
            self.elements['SRvalue'].SetForegroundColour((0,80,120))
            self.elements['SRvalue'].SetLabel("Good")
 
        if DEBUG:
            print >> sys.stderr , "SRstatusbar: My Reputation",reputation
        
        d = self.format_bytes(down * 1024.0) + ' Down'
        self.elements['total_down'].SetLabel(d)
        
        u = self.format_bytes(up * 1024.0) + ' Up'
        self.elements['total_up'].SetLabel(u)
        
        self.Layout()
        
    def onReachable(self,event=None):
        if not self.guiUtility.firewall_restart:
            self.elements['firewallStatus14'].setSelected(2)
            self.elements['firewallStatus14'].SetToolTipString('Port is working')
    
    def IsReachable(self):
        if not self.guiUtility.firewall_restart:
            return self.elements['firewallStatus14'].getSelected() == 2
        return False
    
    def format_bytes(self, bytes):
        if bytes < 1000:
            return '%d B' % bytes
        if bytes < 1024:
            return '%1.1f KB' % (bytes/1024.0)
        if bytes < 1022796:
            return '%d KB' % (bytes//1024)
        if bytes < 1048576:
            return '%1.1f MB' % (bytes//1048576.0)
        if bytes < 1047527425:
            return '%d MB' % (bytes//1048576)
        if bytes < 1073741824:
            return '%1.1f GB' % (bytes//1073741824.0)
        return '%d GB' % (bytes//1073741824)
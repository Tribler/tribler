import wx, os, sys
import wx.xrc as xrc

from Tribler.vwxGUI.GuiUtility import GUIUtility

#from Tribler.vwxGUI.filesGrid import filesGrid


class filesFilter(wx.Panel):
    """
    Panel with automatic backgroundimage control.
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
        # Do all init here
        self.SetBackgroundColour(wx.Colour(153,153,153))   
   
        #self.filesGrid = filesGrid()
        #self.filesGrid = self.filesGrid.filesGrid
        
        self.parent = None
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.detailPanel = None
        self.cols = 5
        self.items = 0
        self.currentData = 0
        self.addComponents()
        self.Show()
        self.initReady = True
            
        self.Refresh(True)
        self.Update()
        
        
    def addComponents(self):
        self.Show(False)
        
        #self.SetBackgroundColour(wx.BLUE)
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.filesFilter_Cat = {'video':'Video', 'videoclips':'Video clips','audio':'Audio','picture':'Pictures','document':'Documents','other':'Other','xxx':'XXX'}
        
        # filter 1 is making a selection                                                                                
        self.filter1 = wx.ComboBox(self,-1,'Video', wx.Point(8,3),wx.Size(120,21),self.filesFilter_Cat.values(), wx.CB_DROPDOWN|wx.CB_READONLY)
        #self.filter1 = wx.ComboBox(self,-1,'Video', wx.Point(8,3),wx.Size(120,21),['Video','VideoClips','Audio','Picture','Compressed','Document','Other','XXX'], wx.CB_DROPDOWN|wx.CB_READONLY)       
        self.filter1.SetFont(wx.Font(10,74,90,90,0,"Verdana"))
        self.filter1.SetBackgroundColour(wx.WHITE)
        self.filter1.Bind(wx.EVT_COMBOBOX, self.mouseAction)
        #self.filter1.Bind(wx.EVT_CHOICE, self.mouseAction)

        # filter 2 is reordering
        self.filter2 = wx.ComboBox(self,-1,'Popular',wx.Point(8,3),wx.Size(120,21),[r'Popular',r'Recommended',r'Creation date',r'Size',r'Etc.'], wx.CB_DROPDOWN|wx.CB_READONLY)
        self.filter2.SetFont(wx.Font(10,74,90,90,0,"Verdana"))
        self.filter2.SetBackgroundColour(wx.WHITE)        
        self.filter2.Bind(wx.EVT_COMBOBOX, self.mouseAction)
        
        self.hSizer.Add([8,33],0,wx.EXPAND|wx.FIXED_MINSIZE,2)
        self.hSizer.Add(self.filter1, 0, wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.hSizer.Add(self.filter2, 0, wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
                
        self.lastOrdering = self.filter1.GetString(0) + self.filter2.GetString(0)
        
        self.SetSizer(self.hSizer);
        self.SetAutoLayout(1);
        self.Layout();
        self.Refresh(True)
        self.Update()
        
    def mouseAction(self, event):
        print 'selected'
        print event
        print self.filter1.GetStringSelection()
        
        filter1String = self.filter1.GetStringSelection()
        filter2String = self.filter2.GetStringSelection()
        
        if filter1String + filter2String == self.lastOrdering:
            return
        
        if filter2String == self.filter2.GetString(0):
            filter2String = 'swarmsize'
            
        elif filter2String == self.filter2.GetString(1):
            filter2String = 'relevance'        
        
        self.guiUtility.standardFilesOverview(filter1String, filter2String)        
        self.lastOrdering = filter1String + filter2String
        

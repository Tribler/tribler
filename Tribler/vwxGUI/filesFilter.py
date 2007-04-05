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
        self.guiUtility.report(self)
        self.initReady = True
            
        self.Refresh(True)
        self.Update()
        
        
    def addComponents(self):
        self.Show(False)
        
        
        #self.SetBackgroundColour(wx.BLUE)
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # filter 1 is making a selection                                                                                
        self.filter1 = wx.Choice(self,-1,wx.Point(8,3),wx.Size(120,21),[r'Video',r'VideoClips',r'Audio',r'Picture',r'Compressed',r'Document',r'other',r'xxx'])
        self.filter1.SetFont(wx.Font(10,74,90,90,0,"Verdana"))
        self.filter1.SetBackgroundColour(wx.WHITE)
        self.filter1.Bind(wx.EVT_CHOICE, self.mouseAction)

        # filter 2 is reordering
        self.filter2 = wx.Choice(self,-1,wx.Point(8,3),wx.Size(120,21),[r'popular',r'recommended',r'etc.'])
        self.filter2.SetFont(wx.Font(10,74,90,90,0,"Verdana"))
        self.filter2.SetBackgroundColour(wx.WHITE)        
        self.filter2.Bind(wx.EVT_CHOICE, self.orderAction)
        
        self.hSizer.Add([8,33],0,wx.EXPAND|wx.FIXED_MINSIZE,2)
        self.hSizer.Add(self.filter1, 0, wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.hSizer.Add(self.filter2, 0, wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
                
        self.lastOrdering = self.filter2.GetString(0)
        #self.filesGrid = self.filesGrid.filesGrid
        
        self.SetSizer(self.hSizer);
        self.SetAutoLayout(1);
        self.Layout();
        self.Refresh(True)
        self.Update()
        
    def mouseAction(self, event):
        print 'selected'
        print event
        print self.filter1.GetStringSelection()
        filter1String = self.getFilterSelected()
        #filter2String = self.filter2.GetStringSelection()
        self.guiUtility.standardFilesOverview(filter1String)
        
    def orderAction(self, event):
        filter2String = self.filter2.GetStringSelection()

        print filter2String

        if filter2String == self.lastOrdering: 
   
            return
        
        if filter2String == self.filter2.GetString(0):
            print 'order on swarmsize'
            self.guiUtility.reorder('swarmsize')
            
        elif filter2String == self.filter2.GetString(1):
            print 'order on relevance'
            self.guiUtility.reorder('relevance')
                        
#        elif obj == self.myHistoryLabel:
#            self.parent.loadMyDownloadHistory()
#            obj.SetFont(self.selFont)
#            self.hideCategories(True)
#        
        
        #if self.lastOrdering:
        #    self.lastOrdering.SetFont(self.orderUnselFont)
        
        self.lastOrdering = filter2String
        
    def getFilterSelected(self):
        self.filter1Selected = self.filter1.GetStringSelection()
        return self.filter1Selected
    
        



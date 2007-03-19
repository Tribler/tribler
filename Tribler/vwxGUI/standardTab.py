from Tribler.vwxGUI.MainXRC import GUIUtility
from wx.lib.stattext import GenStaticText as StaticText

class standardTab(wx.Panel):
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
        self.guiUtility.report(self)
        self.utility = parent.utility
        self.parent = parent
        self.myHistorySelected = False
        self.categories = categories
        self.myHistory = myHistory
        self.addComponents()
        self.Centre()
        self.Show()

    def addComponents(self):
        self.Show(False)
        #self.SetMinSize((50,50))
        self.SetBackgroundColour(wx.Colour(197,220,241))
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        self.unselFont = wx.Font(10, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName="Verdana")
        self.selFont = wx.Font(10, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, faceName="Verdana")
        self.orderUnselFont = wx.Font(10, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL, faceName="Verdana")
        self.orderSelFont = wx.Font(10, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_BOLD, faceName="Verdana")
        
        
        # Order types
        self.orderSizer = wx.BoxSizer(wx.HORIZONTAL)
        # Removed ordering, because recommendation is not effective
                
#        label1 = wx.StaticText(self, -1, self.utility.lang.get('order_by')+': ')
#        label1.SetMinSize((100, -1))
#        self.orderSizer.Add(label1, 0, wx.LEFT|wx.RIGHT, 10)
        
        self.swarmLabel = StaticText(self, -1, self.utility.lang.get('swarmsize'))
        self.swarmLabel.SetToolTipString(self.utility.lang.get('swarmsize_tool'))
        self.swarmLabel.SetBackgroundColour(self.GetBackgroundColour())
        self.swarmLabel.SetFont(self.orderSelFont)
        self.orderSizer.Add(self.swarmLabel, 0, wx.LEFT|wx.RIGHT, 10)
        
        self.recommLabel = StaticText(self, -1, self.utility.lang.get('recommended'))
        self.recommLabel.SetBackgroundColour(self.GetBackgroundColour())
        self.recommLabel.SetFont(self.orderUnselFont)
        self.recommLabel.SetToolTipString(self.utility.lang.get('recommendation_tool'))
        self.orderSizer.Add(self.recommLabel, 1, wx.LEFT|wx.RIGHT, 10)
        
        self.myHistoryLabel = StaticText(self, -1, self.myHistory)
        self.myHistoryLabel.SetBackgroundColour(self.GetBackgroundColour())
        self.myHistoryLabel.SetFont(self.unselFont)
        self.myHistoryLabel.SetToolTipString(self.utility.lang.get('myhistory_tool'))
        self.orderSizer.Add(self.myHistoryLabel, 0, wx.LEFT|wx.RIGHT, 10)
        
        self.recommLabel.Bind(wx.EVT_LEFT_UP, self.orderAction)
        self.swarmLabel.Bind(wx.EVT_LEFT_UP, self.orderAction)
        self.myHistoryLabel.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        
        
        self.lastOrdering = self.swarmLabel
        
        
        # Categories
        self.catSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.vSizer.Add(self.catSizer, 0, BORDER_EXPAND, 0)
        
        self.vSizer.Add(self.orderSizer, 0, BORDER_EXPAND, 0)
        # Label that show category header:
#        label2 =wx.StaticText(self,-1,self.utility.lang.get('categories')+': ')
#        label2.SetMinSize((100, -1))
#        self.catSizer.Add(label2, 0, wx.LEFT|wx.RIGHT, 10)
        
        
        for cat in self.categories:
            label = StaticText(self,-1,cat.title())
            label.SetBackgroundColour(self.GetBackgroundColour())
            label.Bind(wx.EVT_LEFT_UP, self.mouseAction)
            label.SetFont(self.unselFont)
            self.catSizer.Add(label, 0, wx.LEFT|wx.RIGHT, 8)
            if cat.title() == 'Video':
                self.setSelected(label)
                self.lastSelected = label      
            
        
        self.SetSizer(self.vSizer);self.SetAutoLayout(1);self.Layout();
        self.Refresh()
        
    def orderAction(self, event):
        obj = event.GetEventObject()
        if obj == self.lastOrdering or self.myHistorySelected:
            return
        
        if obj == self.swarmLabel:
            self.parent.reorder('swarmsize')
            obj.SetFont(self.orderSelFont)
            
            
        elif obj == self.recommLabel:
            self.parent.reorder('relevance')
            obj.SetFont(self.orderSelFont)
                        
#        elif obj == self.myHistoryLabel:
#            self.parent.loadMyDownloadHistory()
#            obj.SetFont(self.selFont)
#            self.hideCategories(True)
#        
        
        if self.lastOrdering:
            self.lastOrdering.SetFont(self.orderUnselFont)
        self.lastOrdering = obj
        
    def mouseAction(self, event):
         
        obj = event.GetEventObject()
        #print 'Clicked on %s' % obj.GetLabel()
        if obj == self.lastSelected:
            return
        self.setSelected(obj)
        if self.lastSelected:
            self.setUnselected(self.lastSelected)
        self.parent.setCategory(obj.GetLabel())
        self.lastSelected = obj
        self.myHistorySelected = (obj == self.myHistoryLabel)
        self.deselectOrderings(self.myHistorySelected)
        
    def deselectOrderings(self, des):
        if des:
            self.lastOrdering.SetFont(self.orderUnselFont)
            
        else:
            self.lastOrdering.SetFont(self.orderSelFont)
            
    def setSelected(self, obj):
        obj.SetFont(self.selFont)
        self.orderSizer.Layout()
    
    def setUnselected(self, obj):
        obj.SetFont(self.unselFont)
        self.orderSizer.Layout()
        

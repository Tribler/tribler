import wx, os, sys
import wx.xrc as xrc

from Tribler.vwxGUI.GuiUtility import GUIUtility

#from Tribler.vwxGUI.filesGrid import filesGrid


class standardFilter(wx.Panel):
    """
    Panel with automatic backgroundimage control.
    """
    def __init__(self, filterData = []):
        self.filterData = filterData
        pre = wx.PrePanel()
        # the Create step is done by XRC.
        self.PostCreate(pre)
        self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)
        
        
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
        self.filters = []
        # filter 1 is making a selection
        for pullDownData in self.filterData:
            titles = [item[1] for item in pullDownData]
            filter = wx.ComboBox(self,-1,titles[0], wx.Point(8,3),wx.Size(120,21),titles, wx.CB_DROPDOWN|wx.CB_READONLY)
            filter.SetFont(wx.Font(10,74,90,90,0,"Verdana"))
            filter.SetBackgroundColour(wx.WHITE)
            filter.Bind(wx.EVT_COMBOBOX, self.mouseAction)
            self.filters.append(filter)
            self.hSizer.Add(filter, 0, wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
                
        self.hSizer.Add([8,33],0,wx.EXPAND|wx.FIXED_MINSIZE,2)
        
        self.SetSizer(self.hSizer);
        self.SetAutoLayout(1);
        self.Layout();
        self.Refresh(True)
        self.Update()
        
    def mouseAction(self, event):
        print 'selected'
        print self.filter1.GetStringSelection()
        
        filter1String = self.filter1.GetStringSelection()
        filter2String = self.filter2.GetStringSelection()
        
        if filter1String + filter2String == self.lastOrdering:
            return
        
        if filter2String == self.filter2.GetString(0):
            filter2String = 'swarmsize'
            
        elif filter2String == self.filter2.GetString(1):
            filter2String = 'relevance'        
        
        filterState = [filter.GetStringSelection() for filter in self.filters]
        
        if filterState != self.filterState:
            self.filterChanged(filterState)
            self.filterState = filterState
            
    def filterChanged(self, state):
        raise NotImplementedError('Method filterChanged should be subclassed')


class filesFilter(standardFilter):
    def __init__(self):
        filterData = [
                      [('video', 'Video Files'),
                       ('videoclips', 'VideoClips'),
                       ('audio', 'Audio'),
                       ('picture', 'Picture'),
                       ('compressed', 'Compressed'),
                       ('document','Document'),
                       ('other', 'Other'),
                       ('xxx', 'XXX')
                       ],
                       [('swarmsize', 'Popular'),
                        ('relevance','Recommended'),
                        ('','Creation date'),
                        ('size', 'Size'),
                        ('', 'Etc.')
                        ]
                      ]
        standardFilter.__init__(self, filterData = filterData)

    def filterChanged(self, state):
        self.guiUtility.filesFilterAction(state)
        
class personsFilter(standardFilter):
    pass

class libraryFilter(standardFilter):
    pass

class friendsFilter(standardFilter):
    pass


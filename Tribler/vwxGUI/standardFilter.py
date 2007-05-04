import wx, os, sys
import wx.xrc as xrc

from Tribler.vwxGUI.GuiUtility import GUIUtility
from traceback import print_exc
#from Tribler.vwxGUI.filesGrid import filesGrid


class standardFilter(wx.Panel):
    """
    Panel with automatic backgroundimage control.
    """
    def __init__(self, filterData = []):
        self.filterData = filterData
        self.filterState = None
        self.filters = []
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
        # filter 1 is making a selection
        for pullDownData in self.filterData:
            titles = [item[1] for item in pullDownData]
            try:
                if self.filterState is None:
                    self.filterState = []
                self.filterState.append(pullDownData[0][0])
            except:
                print 'standardFilter: Error getting default filterState, data: %s' % pullDownData
            filter = wx.ComboBox(self,-1,titles[0], wx.Point(8,3),wx.Size(180,21),titles, wx.CB_DROPDOWN|wx.CB_READONLY)
            filter.SetFont(wx.Font(10,74,90,90,0,"Verdana"))
#            filter.SetBackgroundColour(wx.WHITE)
            filter.Bind(wx.EVT_COMBOBOX, self.mouseAction)
            self.filters.append(filter)
            self.hSizer.Add(filter, 0, wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
                
        self.hSizer.Add([8,33],0,wx.EXPAND|wx.FIXED_MINSIZE,2)
        
        self.SetSizer(self.hSizer);
        self.SetAutoLayout(1);
        self.Layout();
        self.Refresh(True)
        self.Update()
        wx.CallAfter(self.mouseAction,[None])
        
    def mouseAction(self, event):
        
        filterIndex = [filter.GetSelection() for filter in self.filters]
        filterState = []
        for filterNum in range(len(self.filters)):
            filterState.append(self.filterData[filterNum][filterIndex[filterNum]][0])
            
        print "standardFilter: filterState is",filterState
        if filterState != self.filterState:
            self.filterChanged(filterState)
            self.filterState = filterState
            
    def filterChanged(self, state):
        try:
            self.guiUtility.standardOverview.filterChanged(state)
        except:
            print 'standardFilter: Error could not call standardOverview.filterChanged()'
            print_exc()

    def setSelectionToFilter(self,filterState):
        for j in range(len(filterState)):
            for i in range(len(self.filterData[j])):
                if filterState[j] == self.filterData[j][i][0]:
                    self.filters[j].SetSelection(i)
                    break
        self.filterState = filterState
    
    def getState(self):
        if self.filterState is None:
            return [self.filterData[0][0][0],self.filterData[1][0][0]]
        return self.filterState


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
                       ('xxx', 'XXX'),
                       ('search', 'Search Results')
                       ],
                       [(('content_name', 'increase'), 'Name'),
                        ('swarmsize', 'Popular'),
                        ('relevance','Recommended'),
                        ('date','Creation date'),
                        ('length', 'Size'),                        
                        #('tracker', 'Tracker'),
                        #('num_owners', 'Often received')
                        ]
                      ]
        standardFilter.__init__(self, filterData = filterData)
        
class personsFilter(standardFilter):
    def __init__(self):
        filterData = [
                      [('all', 'All'),
                       ('search', 'Search Results')
                       ],
                      [(('content_name','increase'), 'Name'),
                       ('similarity', 'Similar taste'),                        
                       ('last_seen', 'Recently connected'),                        
                      ]
                  ]
        standardFilter.__init__(self, filterData = filterData)
        
class libraryFilter(standardFilter):
    pass

class friendsFilter(standardFilter):
    def __init__(self):
        filterData = [
                      [('friends', 'All'),
                       ('search_friends', 'Search Results')
                       ],
                      [(('content_name','increase'), 'Name'),
                       ('similarity', 'Similar taste'),                        
                       ('last_seen', 'Recently connected'),                        
                      ]
                  ]
        standardFilter.__init__(self, filterData = filterData)


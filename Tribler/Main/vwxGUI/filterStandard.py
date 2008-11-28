import wx, os, sys
import wx.xrc as xrc

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from traceback import print_exc
from Tribler.Category.Category import Category
from Tribler.Main.vwxGUI.TextButton import *
from Tribler.Main.vwxGUI.TriblerStyles import TriblerStyles
from font import *

DEBUG = False

class filterStandard(wx.Panel):
    """
    Panel with automatic backgroundimage control.
    """
    def __init__(self, *args, **kw):
        
        self.initDone = False
        self.enabled = True
#        self.filterData =[[('all', 'All'), ('Video', 'Video Files'), ('VideoClips', 'Video Clips'), ('Audio', 'Audio'), ('Compressed', 'Compressed'), ('Document', 'Documents'), ('Picture', 'Pictures'),
#                           ('other', 'Other')]]
        self.filterData = []
        self.filterState = None
        self.filters = []
        self.visible = False
        

        if len(args) == 0: 
            pre = wx.PrePanel() 
            # the Create step is done by XRC. 
            self.PostCreate(pre) 
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate) 
        else:
            wx.Panel.__init__(self, *args, **kw) 
            self._PostInit()    



    def OnCreate(self, event):
#        print "<mluc> tribler_topButton in OnCreate"
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)        
        event.Skip()
        

        return True
    
    def _PostInit(self):
        # Do all init here
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        
        self.guiUtility.initFilterStandard(self)
        self.triblerStyles = TriblerStyles.getInstance()
#        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
#        self.Bind(wx.EVT_LEFT_UP, self.ClickedButton)
        self.SetMinSize((500, 160)) ##

        self.initDone = True
#        self.addComponents()
        self.Show()            
        self.Refresh()
        self.Layout()
        self.Update()
        
        
        
    def addComponents(self):
#        self.SetBackgroundColour(wx.BLUE)
        self.DestroyChildren()
        self.vSizer = wx.BoxSizer(wx.VERTICAL)        
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.vSizer.Add(self.hSizer, 0, wx.EXPAND, 0)

        
        i = 0
        for list in self.filterData:
            vSizer = wx.BoxSizer(wx.VERTICAL)        
            vSizer.Add([120,8],0,wx.FIXED_MINSIZE,0)
            
            titleText = wx.StaticText(self, -1, self.filterDataTitle[i])
            self.triblerStyles.setDarkText(titleText)
            vSizer.Add(titleText, 0, wx.EXPAND|wx.TOP, 1)             
            
            for title in list:        
                text = TextButtonFilter(self, name=title[1])                
                vSizer.Add(text, 0, wx.EXPAND|wx.TOP, 1)             
            self.hSizer.Add(vSizer, 0, wx.EXPAND|wx.LEFT, 10)
            
            i = i + 1
            
#            for title in list:
#                titles.append(title)    
##                titles = [item[1] for item in pullDownData]
#                print 'tb > titles2 = %s' % titles
    
#                try:
#                    if self.filterState is None:
#                        self.filterState = []
#                    self.filterState.append(pullDownData[0][0])
#                except:
#                    if DEBUG:
#                        print >>sys.stderr,'standardFilter: Error getting default filterState, data: %s' % pullDownData
#                    pass
        
##        self.vSizer1 = wx.BoxSizer(wx.VERTICAL)        
##        self.vSizer1.Add([120,1],0,wx.FIXED_MINSIZE,0)
##        for title in titles:
##            text = TextButtonFilter(self, name=title)                
###            text = wx.StaticText(self, -1, title)
##            self.vSizer1.Add(text, 0, wx.EXPAND|wx.TOP, 1)             
##        self.hSizer.Add(self.vSizer1, 0, wx.EXPAND|wx.LEFT, 10)     
                        
#        filter = wx.ComboBox(self,-1,titles[0], wx.DefaultPosition,wx.Size(160,10),titles, wx.FIXED_MINSIZE|wx.CB_DROPDOWN|wx.CB_READONLY)
        #filter = wx.Choice(self,-1, wx.Point(8,3),wx.Size(180,21),titles)
#        filter.SetFont(wx.Font(10,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
#            filter.SetBackgroundColour(wx.WHITE)
#        filter.Bind(wx.EVT_COMBOBOX, self.mouseAction)            
        self.filters.append(filter)
#        self.hSizer.Add(filter, 0, wx.FIXED_MINSIZE,0)
                
#        self.hSizer.Add([8,10],0,wx.EXPAND|wx.FIXED_MINSIZE,2)
        
        
        self.SetSizer(self.vSizer);
        self.SetAutoLayout(1);
        self.Layout()
        self.Refresh()
#        self.mouseAction()
#        wx.CallAfter(self.mouseAction,[None])

    def SetData(self, mode):
        if self.initDone == True:
            print 'tb > mode = %s' % mode
            if mode == 'libraryMode' or mode == 'filesMode' or mode == 'personsMode' or mode == 'friendsMode':
                if self.visible:
                    self.Show()
                self.guiUtility.advancedFiltering.Show()
            else:
                self.Hide()
                self.guiUtility.advancedFiltering.Hide()
             
            self.getFilterLists(mode)    
            self.addComponents()
        
    def getFilterLists(self, mode):
        self.filterDataTitle = []
        self.filterData = []
        if mode == 'filesMode':
            self.filterDataTitle.append(' filter on:')
            self.filterData.append([('all', 'All'), ('Video', 'Video Files'), ('VideoClips', 'Video Clips'), ('Audio', 'Audio'), ('Compressed', 'Compressed'), ('Document', 'Documents'), ('Picture', 'Pictures'),
                               ('other', 'Other')])
            self.filterDataTitle.append(' sort on:')
            self.filterData.append([('name', 'Name'), ('size', 'Size'), ('popularity', 'Popularity'), ('new', 'Age'), ('source', 'Source')])
            
        elif mode == 'libraryMode':
            self.filterDataTitle.append(' filter on:')
            self.filterData.append([('all', 'All'), ('Video', 'Video Files'), ('VideoClips', 'Video Clips'), ('Audio', 'Audio'), ('Compressed', 'Compressed'), ('Document', 'Documents'), ('Picture', 'Pictures'),
                               ('other', 'Other')])
            self.filterDataTitle.append(' sort on:')
            self.filterData.append([('name', 'Name'), ('progress', 'Progress'), ('eta', 'ETA')])
            
        elif mode == 'personsMode':
            self.filterDataTitle.append(' sort on:')
            self.filterData.append([('name', 'Name'), ('status', 'Status'), ('reputation', 'Reputation'), ('nfiles', 'Files discovered'), ('npeers', 'Persons discovered'), ('nprefs', 'Number of downloads')])
            
        elif mode == 'friendsMode':
            self.filterDataTitle.append(' type:')
            self.filterData.append([('name', 'Name'), ('status', 'Status'), ('reputation', 'Reputation'), ('nfiles', 'Files discovered'), ('npeers', 'Persons discovered'), ('nprefs', 'Number of downloads')])
        
        
    def mouseAction(self, event=''):

        #print >>sys.stderr,"standardFilter: mouseAction: event is",event
        filterIndex = []
        for filter in self.filters:
            idx = filter.GetSelection()
            if idx == -1:
                idx = 0
            filterIndex.append(idx)
        filterState = []
        for filterNum in range(len(self.filters)):
            filterState.append(self.filterData[filterNum][filterIndex[filterNum]][0])
            
        filterState.append(None) #replacement for old ordering filter
        if DEBUG:
            print >>sys.stderr,"standardFilter: filterState is",filterState,"old",self.filterState
        if filterState != self.filterState:
            self.filterChanged(filterState)
            self.filterState = filterState
            
    def filterChanged(self, state):
        try:
            mode = self.__class__.__name__[:-len('Filter')]
            if self.guiUtility.standardOverview.mode.startswith(mode):
                self.guiUtility.standardOverview.filterChanged(state, mode)
            elif DEBUG:
                print 'Warning: StandardOverview was in mode %s and we changed combo of %s' %  \
                    (self.guiUtility.standardOverview.mode, mode)
        except:
            if DEBUG:
                print >>sys.stderr,'standardFilter: Error could not call standardOverview.filterChanged()'
            print_exc()

    def setSelectionToFilter(self,filterState):
        try:
            for j in range(len(filterState)):
                for i in range(len(self.filterData[j])):
                    if filterState[j] == self.filterData[j][i][0]:
                        self.filters[j].SetSelection(i)
                        break
        except:
            pass
        self.filterState = filterState
    
    def getState(self):
        if self.filterState is None:
            state = []
            for i in xrange(len(self.filters)):
                state.append(self.filterData[i][0][0])
            return state
        return self.filterState


class filterFiles(filterStandard):
    
    def __init__(self, parent):
        nametuples = [('all', 'All')]
        nametuples += Category.getInstance().getCategoryNames()
        nametuples.append(('other', 'Other'))
        #nametuples.append(('search', 'Search Results'))

#        parent = None
        filterData = [
                       nametuples
#                       [(('content_name', 'increase'), 'Name'),
#                        ('swarmsize', 'Popular'),
#                        ('relevance','Recommended'),
#                        ('date','Creation date'),
#                        ('length', 'Size'),                        
#                        #('tracker', 'Tracker'),
#                        #('num_owners', 'Often received')
#                        ]
                      ]
        standardFilter.__init__(self, parent,filterData = filterData)
       
    def refresh(self):
        nametuples = [('all', 'All')]
        nametuples += Category.getInstance().getCategoryNames()
        nametuples.append(('other', 'Other'))
        self.filterData = [nametuples]
        #self._PostInit()
        self.addComponents()
        
#class personsFilter(standardFilter):
#    def __init__(self):
#        filterData = [
#                      [('all', 'All'),
#                       ('search', 'Search Results')
#                       ],
#                      [(('content_name','increase'), 'Name'),
#                       ('similarity', 'Similar taste'),                        
#                       ('last_connected', 'Recently connected'),                        
#                      ]
#                  ]
#        standardFilter.__init__(self, filterData = filterData)
#        
class filterLibrary(filterStandard):
    pass
#class friendsFilter(standardFilter):
#    def __init__(self):
#        filterData = [
#                      [('friends', 'All'),
#                       ('search_friends', 'Search Results')
#                       ],
#                      [(('content_name','increase'), 'Name'),
#                       ('similarity', 'Similar taste'),                        
#                       ('last_connected', 'Recently connected'),                        
#                      ]
#                  ]
#        standardFilter.__init__(self, filterData = filterData)



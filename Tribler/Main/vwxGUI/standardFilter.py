# Written by Jelle Roozenburg, Maarten ten Brinke 
# see LICENSE.txt for license information
import wx, os, sys
import wx.xrc as xrc

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from traceback import print_exc
from Tribler.Category.Category import Category
from Tribler.Main.vwxGUI.GridState import GridState
from font import *

DEBUG = False

class standardFilter(wx.Panel):
    """
    Panel with automatic backgroundimage control.
    """
    def __init__(self, filterData = []):
        self.filterData = filterData
        self.filterState = {}
        self.filters = {}
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.state = None
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
        self.parent = None
        self.detailPanel = None
        self.Show(False)
        self.addComponents()
        self.Show()
        self.initReady = True
            
        self.Refresh(True)
        self.Update()
        
        
    def addComponents(self):
        
        #self.SetBackgroundColour(wx.BLUE)
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        # Add Sizer
        self.hSizer.Add([20,10],0,wx.EXPAND|wx.FIXED_MINSIZE,0)        
        # filter 1 is making a selection
        for name, pullDownData in self.filterData:
            titles = [item[1] for item in pullDownData]
            try:
                #if self.filterState is None:
                #    self.filterState = {}
                self.filterState[name] = pullDownData[0][0]
            except:
                if DEBUG:
                    print >>sys.stderr,'standardFilter: Error getting default filterState, data: %s' % pullDownData
                raise
            filter = wx.ComboBox(self,-1,titles[0], wx.Point(8,3),wx.Size(160,21),titles, wx.CB_DROPDOWN|wx.CB_READONLY)
            #filter = wx.Choice(self,-1, wx.Point(8,3),wx.Size(180,21),titles)
            filter.SetFont(wx.Font(10,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
#            filter.SetBackgroundColour(wx.WHITE)
            filter.Bind(wx.EVT_COMBOBOX, self.mouseAction)
            self.filters[name] = filter
            self.hSizer.Add(filter, 0, wx.TOP|wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
                
        self.hSizer.Add([8,10],0,wx.EXPAND|wx.FIXED_MINSIZE,2)
        
        
        self.SetSizer(self.hSizer);
        self.SetAutoLayout(1);
        self.Layout();
        self.Refresh(True)
        self.Update()
        wx.CallAfter(self.mouseAction,[None])
        
    def mouseAction(self, event = None):
        filterState = {}
        #print >>sys.stderr,"standardFilter: mouseAction: event is",event
        for name, filter in self.filters.iteritems():
            idx = filter.GetSelection()
            if idx == -1:
                idx = 0
            values= [a[1] for a in self.filterData if a[0] == name][0]
            filterState[name] = values[idx][0]
            
        if DEBUG:
            print >>sys.stderr,"standardFilter: filterState is",filterState,"old",self.filterState
        if filterState != self.filterState or self.state is None:
            self.filterChanged(filterState)
            self.filterState = filterState
            
    def filterChanged(self, dict_state):
        try:
            self.state = GridState(self.mode,
                              dict_state.get('category'),
                              None)
            if DEBUG:
	            print >> sys.stderr,'standardFilter: %s returns %s' % (self.__class__.__name__, self.state)
            self.guiUtility.standardOverview.filterChanged(self.state)
        except:
            if DEBUG:
                print >>sys.stderr,'standardFilter: Error could not call standardOverview.filterChanged()'
            print_exc()

#    def setSelectionToFilter(self,filterState):
#        try:
#            for j in range(len(filterState)):
#                for i in range(len(self.filterData[j])):
#                    if filterState[j] == self.filterData[j][i][0]:
#                        self.filters[j].SetSelection(i)
#                        break
#        except:
#            pass
#        self.filterState = filterState
    
    def getState(self):
        # Arno, 2008-6-20: The state that mouseAction computers for libraryMode is not valid
        #if not self.state:
        #    self.mouseAction()
        return self.state

    

class filesFilter(standardFilter):
    def __init__(self):
        nametuples = [('all', 'All')]
        nametuples += Category.getInstance().getCategoryNames()
        nametuples.append(('other', 'Other'))
        #nametuples.append(('search', 'Search Results'))
        
        filterData = [['category', nametuples]]
                     
        standardFilter.__init__(self, filterData = filterData)
        self.mode = 'filesMode'
        
    def refresh(self):
        nametuples = [('all', 'All')]
        nametuples += Category.getInstance().getCategoryNames()
        nametuples.append(('other', 'Other'))
        self.filterData = [['category', nametuples]]
        #self._PostInit()
        self.addComponents()
        self.Show()
        self.filterChanged(self.filterState)
        

class libraryFilter(filesFilter):
    def __init__(self):
        filesFilter.__init__(self)
        self.mode = 'libraryMode'


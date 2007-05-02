import os, sys, wx
from Tribler.vwxGUI.GuiUtility import GUIUtility
from Tribler.vwxGUI.filesItemPanel import FilesItemPanel
from Tribler.vwxGUI.LibraryItemPanel import LibraryItemPanel
from Tribler.vwxGUI.PersonsItemPanel import PersonsItemPanel
from Tribler.vwxGUI.FriendsItemPanel import FriendsItemPanel
from Tribler.vwxGUI.SubscriptionsItemPanel import SubscriptionsItemPanel
from Tribler.Dialogs.ContentFrontPanel import ImagePanel, DetailPanel
from Tribler.Dialogs.GUIServer import GUIServer
from Tribler.Dialogs.MugshotManager import MugshotManager
from Tribler.utilities import *
from traceback import print_exc,print_stack

import wx, os, sys, math
import wx.xrc as xrc

DEBUG = True

        
class standardGrid(wx.Panel):
    """
    Panel which shows a grid with static number of columns and dynamic number
    of rows
    """
    def __init__(self, cols, orientation='horizontal'):
        self.initReady = False
        self.data = None
        self.cols = cols
        self.orientation = orientation
        pre = wx.PrePanel()
        # the Create step is done by XRC.
        self.PostCreate(pre)
        self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)
        
        self.guiserver = GUIServer.getInstance()
        self.mm = MugshotManager.getInstance()
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    

    def _PostInit(self):
        # Do all init here

        #self.SetSize((500,500))
        self.SetBackgroundColour(wx.BLACK)
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.detailPanel = None       
        #self.cols = 5
        self.items = 0
        self.currentData = 0
        self.currentRows = 0
        self.detailPanel = None
        
        self.panels = []
        self.currentData = 0
        self.Bind(wx.EVT_SIZE, self.onResize)
        
        self.addComponents()
        self.calculateRows()
        self.Show()
        self.Layout()
        self.Refresh()

        self.initReady = True
        if self.data:
            self.setData(self.data)
                
    def addComponents(self):
        self.Show(False)

        self.SetBackgroundColour(wx.WHITE)
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        
        self.SetSizer(self.vSizer);
        self.SetAutoLayout(1);
        #self.Layout();
        #self.Refresh(True)
        #self.Update()
        #print "vSizer: %s, Panel: %s"% (self.vSizer.GetSize(), self.GetSize())

    def refreshData(self):
        self.setData(self.data, resetPages = False)
        
    def getData(self):
        return self.data
    
    def setData(self, dataList, resetPages = True):
        
        if dataList is None:
            datalength = 0
        else:
            datalength = len(dataList)
        
        #print 'SetData called: init: %s, datalength: %d' % (self.initReady, datalength)
        
        self.data = dataList
        
        if not self.initReady:
            return
                
        if resetPages:
            self.currentData = 0
            if self.getStandardPager():
                self.standardPager.currentPage = 0
        self.refreshPanels()
        
        
    def updateItem(self, item, delete = False):
        "Add or update an item in the grid"
        
        # Get key to compare this item to others
        key = None
        for tempkey in ['infohash', 'permid', 'content_name']:
            if item.has_key(tempkey):
                key = tempkey
                break
        if not key:
            print 'standardGrid: Error, could not find key to compare item: %s' % item
            return
        
        i = find_content_in_dictlist(self.data, item, key)
        if i != -1:
            if not delete:
                self.data[i] = item
            else:
                self.data.remove(item)
        else:
            self.data.append(item)
        self.setData(self.data, resetPages = False)
        
    def refreshPanels(self):
        "Refresh TorrentPanels with correct data and refresh pagerPanel"
        if self.getStandardPager():
            self.standardPager.refresh()
                
        if self.data is None:
            self.clearAllData()
        else:
            for i in range(0, self.items):
                dataIndex = i+ self.currentData
                if dataIndex < len(self.data):
                    self.setDataOfPanel(i, self.data[dataIndex])
                else:
                    self.setDataOfPanel(i, None)
        
        self.updateSelection()
    
    def gridResized(self, rows):
        self.items = self.cols * rows
        self.refreshPanels()
        
    def setPageNumber(self, page):
        if not self.data:
            return
        old = self.currentData
        if self.items * page < len(self.data) and page>=0:
            self.currentData = self.items*page
        if old != self.currentData:
            self.refreshPanels()
        
    def getStandardPager(self):
        try:
            if self.standardPager:
                return True
        except:
            return False
        
    def setPager(self, pager):
        print 'setPager called: %s' % pager
        self.standardPager = pager
       
    def getSubPanel(self):
        raise NotImplementedError('Method getSubPanel should be subclassed')

    def setDataOfPanel(self, panelNumber, data):
        
        try:
            if self.orientation == 'vertical':
                hSizer = self.vSizer.GetItem(panelNumber%self.currentRows).GetSizer()
                panel = hSizer.GetItem(panelNumber/ self.currentRows).GetWindow()
            else:
                hSizer = self.vSizer.GetItem(panelNumber/self.cols).GetSizer()
                panel = hSizer.GetItem(panelNumber % self.cols).GetWindow()
            panel.setData(data)
        except:
            print >>sys.stderr,"contentpanel: Error: Could not set data in panel number %d, with %d cols" % (panelNumber, self.cols)
            print_exc(file=sys.stderr)
    
    def clearAllData(self):
        for i in range(0, self.items):
            self.setDataOfPanel(i, None)
            
    def onResize(self, event=None):        
        #print "event: %s" % event       
        self.calculateRows(event)
        if event:
            event.Skip()
        
    def updateSubPanelHeight(self):
        try:
            self.subPanelHeight = self.vSizer.GetItem(0).GetSizer().GetItem(0).GetWindow().GetSize()[1]
        except:
            #print 'Could not get subpanelheight'
            pass
        
    def calculateRows(self, event=None):
    
        size = self.GetSize()
        oldRows = self.currentRows
        self.updateSubPanelHeight()
        if size[1] < 50 or self.subPanelHeight == 0:
            self.currentRows = 0
            self.items = 0
        else:            
            self.currentRows = size[1] / self.subPanelHeight 
            if DEBUG:
                print >> sys.stderr, 'standardGrid: Height: %d, single panel is %d, so %d rows' % (size[1], self.subPanelHeight, self.currentRows)
            self.items = self.cols * self.currentRows
        
        if oldRows != self.currentRows: #changed
            if DEBUG:
                print >>sys.stderr,'contentpanel: Size updated to %d rows and %d columns, oldrows: %d'% (self.currentRows, self.cols, oldRows)
            
            self.updatePanel(oldRows, self.currentRows)
            self.gridResized(self.currentRows)
            
        
        
            
    
    def updatePanel(self, oldRows, newRows):
        # put torrent items in grid 
        if newRows > oldRows:
            for i in range(oldRows, newRows):
                hSizer = wx.BoxSizer(wx.HORIZONTAL)
                self.panels.append([])
                for panel in range(0, self.cols):
                    dataPanel = self.getSubPanel()
                    #dataPanel = wx.Panel(self, wx.ID_ANY)
                    self.panels[i].append(dataPanel)
                    #dataPanel.SetSize((-1, self.subPanelHeight))
                    hSizer.Add(dataPanel, 1, wx.ALIGN_CENTER|wx.ALL|wx.GROW, 0)
                self.vSizer.Add(hSizer, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 0)
        elif newRows < oldRows:
            #print "Destroying row %d up to %d" % (newRows, oldRows-1)
            for row in range(oldRows-1, newRows-1, -1):
                # Destroy old panels
                for col in range(self.cols-1, -1, -1): #destroy panels right to left
                    panel = self.panels[row][col]
                    panel.Destroy()
                    del self.panels[row][col]
                    
                assert self.panels[row] == [], 'We deleted all panels, still the row is %s' % self.panels[row]
                del self.panels[row]
                self.vSizer.Detach(row) # detach hSizer of the row
                
       
        
          
    
    def updateSelection(self):
        """Deselect all torrentPanels, but the one selected in detailPanel
        If no torrent is selected in detailPanel, let first in grid be selected
        """
        
        if not self.hasDetailPanel():
            return
        
        title = None
        
        if self.detailPanel.data!=None:
            id = self.detailPanel.getIdentifier()
            
        
        for row in self.panels:
            for pan in row:
                try:
                    panel_id = pan.getIdentifier()
                except:
                    panel_id = None
                    
                if panel_id != id or  panel_id is None:
                    #print 'item deselected2'
                    pan.deselect()
                else:
                    pan.select()
        
    def hasDetailPanel(self):
        if self.detailPanel:
            return True
        try:
            self.detailPanel = self.guiUtility.standardDetails
        except:
            pass
        return self.detailPanel != None
    


class filesGrid(standardGrid):
    def __init__(self):
        columns = 5
        self.subPanelHeight = 116 # This will be update after first refresh
        standardGrid.__init__(self, columns, orientation='horizontal')
        
    def getSubPanel(self):
        return FilesItemPanel(self)
    
class personsGrid(standardGrid):
    def __init__(self):
        columns = 6
        self.subPanelHeight = 116 # This will be update after first refresh
        standardGrid.__init__(self, columns, orientation='horizontal')
        
    def getSubPanel(self):
        return PersonsItemPanel(self)

class friendsGrid(standardGrid):
    def __init__(self):   
        columns = 2
        self.subPanelHeight = 36 # This will be update after first refresh
        standardGrid.__init__(self, columns, orientation='vertical')
        
    def getSubPanel(self):
        return FriendsItemPanel(self)
    
class libraryGrid(standardGrid):
    def __init__(self):
        columns = 1
        self.subPanelHeight = 40 # This will be update after first refresh
        standardGrid.__init__(self, columns, orientation='horizontal')
        
    def getSubPanel(self):
        return LibraryItemPanel(self)
    
class subscriptionsGrid(standardGrid):
    def __init__(self):
        columns = 1
        self.subPanelHeight = 30 # This will be update after first refresh
        standardGrid.__init__(self, columns, orientation='horizontal')
        
    def getSubPanel(self):
        return SubscriptionsItemPanel(self)

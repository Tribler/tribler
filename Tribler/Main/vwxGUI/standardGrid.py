import os, sys, wx, math
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.filesItemPanel import FilesItemPanel
from Tribler.Main.vwxGUI.LibraryItemPanel import LibraryItemPanel
from Tribler.Main.vwxGUI.PersonsItemPanel import PersonsItemPanel
from Tribler.Main.vwxGUI.FriendsItemPanel import FriendsItemPanel
from Tribler.Main.vwxGUI.ColumnHeader import ColumnHeaderBar
from Tribler.Main.vwxGUI.SubscriptionsItemPanel import SubscriptionsItemPanel
from Tribler.Main.Dialogs.GUIServer import GUIServer
from Tribler.Core.CacheDB.CacheDBHandler import SuperPeerDBHandler
from Tribler.Subscriptions.rss_client import TorrentFeedThread

from Tribler.Core.Utilities.utilities import *
from traceback import print_exc,print_stack

import wx.xrc as xrc
import web2

DEBUG = True
DEBUG_DOD = False
        
class standardGrid(wx.Panel):
    """
    Panel which shows a grid with static number of columns and dynamic number
    of rows
    """
    def __init__(self, cols, subPanelHeight, orientation='horizontal', viewmode = 'thumbnails'):
        self.initReady = False
        self.data = None
        self.dod = None
        self.detailPanel = None
        self.orientation = orientation
        self.subPanelClass = None
        self.items = 0 #number of items that are currently visible 
        self.currentData = 0 #current starting index in the list for visible items
        self.currentRows = 0
        self.sizeMode = 'auto'
        self.columnHeader = None
        self.topMargin = 5
        self.panels = []
        self.viewmode = viewmode
        pre = wx.PrePanel()
        # the Create step is done by XRC.
        self.PostCreate(pre)
        self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)
        if type(cols) == int:
            self.cols = cols
            self.columnTypes = None
            self.subPanelHeight = subPanelHeight
        else:
            self.columnTypes = cols
            self.subPanelHeights = subPanelHeight
            if self.viewmode == 'thumbnails':
                self.cols = cols[0]
                self.subPanelHeight = self.subPanelHeights[0]
            elif self.viewmode == 'list':
                self.cols = cols[1]
                self.subPanelHeight = self.subPanelHeights[1]
            else:
                raise Exception('unknown viewmode: %s' % self.viewmode)
                
            
            
        
        self.guiserver = GUIServer.getInstance()
        self.superpeer_db = SuperPeerDBHandler.getInstance()
        self.torrentfeed = TorrentFeedThread.getInstance()
        
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
        #self.cols = 5
        
        self.Bind(wx.EVT_SIZE, self.onResize)
        
        self.addComponents()
        self.calculateRows()
        if self.viewmode == 'list':
            self.toggleColumnHeaders(True)
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
        self.columnHeaderSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.columnHeaderSizer.Add((0,self.topMargin))
        self.vSizer.Add(self.columnHeaderSizer, 0, wx.ALL|wx.EXPAND, 0)
        self.SetSizer(self.vSizer);
        self.SetAutoLayout(1);
        #self.Layout();
        #self.Refresh(True)
        #self.Update()
        #print "vSizer: %s, Panel: %s"% (self.vSizer.GetSize(), self.GetSize())

    def onViewModeChange(self, event=None, mode = None):
        if not self.initReady:
            wx.CallAfter(self.onViewModeChange, event, mode)
            return
                         
        if not mode:
            if type(event.GetEventObject()) == wx.Choice:
                mode = event.GetEventObject().GetStringSelection()
            
        if self.viewmode != mode:
            self.viewmode = mode
            #oldcols = self.cols
            self.updatePanel(self.currentRows, 0)
            if mode == 'thumbnails':
                self.cols = self.columnTypes[0]
                self.subPanelHeight = self.subPanelHeights[0]
            elif mode == 'list':
                self.cols = self.columnTypes[1]
                self.subPanelHeight = self.subPanelHeights[1]
            self.currentRows = 0
            
            #self.updatePanel(0, self.currentRows)
            self.calculateRows()
            #self.updateCols(oldcols, self.cols)
            self.refreshData()
            self.toggleColumnHeaders(mode == 'list')
        
    def onSizeChange(self, event=None):
        if type(event.GetEventObject()) == wx.Choice:
            value = event.GetEventObject().GetStringSelection()
        else:
            value = event.GetEventObject().GetValue()
            
        self.sizeMode = value
        if value == 'auto':
            self.guiUtility.updateSizeOfStandardOverview()
            self.SetMinSize((-1, 20))
        else:
            try:
                wantedRows = int(value) / self.cols
                self.SetSize((-1, wantedRows * self.subPanelHeight))
                self.SetMinSize((-1, wantedRows * self.subPanelHeight))
                self.guiUtility.standardOverview.growWithGrid()
                self.guiUtility.standardOverview.Refresh()
            except:
                #print 'Exception!'
                
                raise
                
        
    def refreshData(self):
        self.setData(self.data, resetPages = False)
        

    def getData(self):
        return self.data


    def updateDod(self, item=None):
        if DEBUG or DEBUG_DOD:
            print >>sys.stderr,'standardGrid: WEB2.0 -> updateDod'
        #self.data = self.dod.getData()
        if item:
            self.data.append(item)
            wx.CallAfter(self.refreshData)
        
    
    def setData(self, dataList, resetPages = True):
        
        #if dataList is None:
            #datalength = 0
        #else:
            #datalength = len(dataList)
        
        if type(dataList) == list or dataList is None:
            print 'grid.setData: list'
            self.data = dataList
            
        elif dataList.isDod():
            #print 'grid.setData: dod'
            if self.dod != dataList:
                self.stopWeb2Search()

            self.data = dataList.getData()
            self.dod = dataList
            self.dod.register(self.updateDod)
            self.moreData()

        
        if not self.initReady:
            return
                
        if resetPages:
            self.currentData = 0
            if self.getStandardPager():
                self.standardPager.currentPage = 0
        self.refreshPanels()
        if DEBUG:
            print >>sys.stderr,'standardGrid: <mluc>start pos:',self.currentData,'columns:',self.cols,'rows:',self.currentRows,'items:',self.items

        self.Layout()
        
    def updateItem(self, item, delete = False, onlyupdate = False):
        "Add or update an item in the grid"
        
        if not item:
            return
        
        # Get key to compare this item to others
        key = None
        for tempkey in ['infohash', 'permid', 'content_name']:
            if item.has_key(tempkey):
                key = tempkey
                break
        if not key:
            if DEBUG:
                print >>sys.stderr,'standardGrid: Error, could not find key to compare item: %s' % item
            return
        #get the current data source
        if len(self.data)>0 and self.data[0].has_key("permid"):
            print >>sys.stderr,"\n*****************************************************\n\
*                   big problem                     *\n\
*     in torrentGrid, working on peer data!!!!!     *\n\
*                                                   *\n\
*****************************************************\n"
        i = find_content_in_dictlist(self.data, item, key)
        if i != -1:
            if not delete:
                self.data[i] = item
            else:
                self.data.remove(item)
        elif not onlyupdate:
            self.data.append(item)
        self.refreshData()
        
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

        self.moreData()
        
    def setPageNumber(self, page):
        if not self.data:
            return
        old = self.currentData
        if self.items * page < len(self.data) and page>=0:
            self.currentData = self.items*page
        if old != self.currentData:
            self.refreshPanels()

        self.moreData()
        
    def getStandardPager(self):
        try:
            if self.standardPager:
                return True
        except:
            return False
        
    def setPager(self, pager):
        if DEBUG:
            print >>sys.stderr,'standardGrid: setPager called: %s' % pager
        self.standardPager = pager
       
    def getSubPanel(self, keyfun=None):
        raise NotImplementedError('Method getSubPanel should be subclassed')

    def setDataOfPanel(self, panelNumber, data):
        if DEBUG:
            print 'Set data of panel %d with data: %s' % (panelNumber, data)
        try:
            if self.orientation == 'vertical':
                hSizer = self.vSizer.GetItem(panelNumber%self.currentRows+1).GetSizer()
                panel = hSizer.GetItem(panelNumber/ self.currentRows).GetWindow()
            else:
                hSizer = self.vSizer.GetItem(panelNumber/self.cols+1).GetSizer()
                panel = hSizer.GetItem(panelNumber % self.cols).GetWindow()
                
            panel.setData(data)
        except:
            if DEBUG:
                print >>sys.stderr,"standardGrid: Error: Could not set data in panel number %d, with %d cols" % (panelNumber, self.cols)
            print_exc()
    
    def clearAllData(self):
        for i in range(0, self.items):
            self.setDataOfPanel(i, None)
            
    def onResize(self, event=None):        
        #print "event: %s" % event       
        self.calculateRows(event)
        if event:
            event.Skip()
        
   
        
    def calculateRows(self, event=None):
    
        size = self.GetSize()
        oldRows = self.currentRows
        if self.columnHeader:
            columnHeaderHeight = self.columnHeader.GetSize()[1]
        else:
            columnHeaderHeight = self.topMargin
            
        
        if size[1] < 50 or self.subPanelHeight == 0:
            self.currentRows = 0
            self.items = 0
        else:            
            self.currentRows = (size[1] - columnHeaderHeight) / self.subPanelHeight 
            if DEBUG:
                print >> sys.stderr, 'standardGrid: Height: %d, single panel is %d, so %d rows' % (size[1], self.subPanelHeight, self.currentRows)
            self.items = self.cols * self.currentRows
        
        if oldRows != self.currentRows: #changed
            if DEBUG:
                print >>sys.stderr,'standardGrid: Size updated to %d rows and %d columns, oldrows: %d'% (self.currentRows, self.cols, oldRows)
            
            self.updatePanel(oldRows, self.currentRows)
            self.gridResized(self.currentRows)
            
        
        
    def updateCols(self, oldCols, newCols):
        self.items = newCols * self.currentRows
        if newCols > oldCols:
            numNew = newCols - oldCols
            for row in xrange(len(self.panels)):
                hSizer = self.vSizer.GetItem(row).GetSizer()
                for i in xrange(numNew):
                    dataPanel = self.getSubPanel(self.keyTypedOnGridItem)
                    self.subPanelClass = dataPanel.__class__
                    self.panels[row].append(dataPanel)
                    hSizer.Add(dataPanel, 1, wx.ALIGN_CENTER|wx.ALL|wx.GROW, 0)
        elif newCols < oldCols:
            numDelete = oldCols - newCols
            for row in self.panels:
                for i in xrange(numDelete):
                    panel = row[newCols]
                    panel.Destroy()
                    del row[newCols]
                    
        
    
    def updatePanel(self, oldRows, newRows):
        # put torrent items in grid 
        if newRows > oldRows:
            for i in range(oldRows, newRows):
                hSizer = wx.BoxSizer(wx.HORIZONTAL)
                self.panels.append([])
                for panel in range(0, self.cols):
                    dataPanel = self.getSubPanel(self.keyTypedOnGridItem)
                    self.subPanelClass = dataPanel.__class__
                    # add keylistener for arrow selection
                    #dataPanel.Bind(wx.EVT_KEY_UP, self.keyTypedOnGridItem)
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
                self.vSizer.Detach(row+1) # detach hSizer of the row
                # +1 compensated for columnheaders
                
       
        
          
    
    def updateSelection(self):
        """Deselect all torrentPanels, but the one selected in detailPanel
        If no torrent is selected in detailPanel, let first in grid be selected
        """
        
        try:
            #print 'standardGrid: update selection'
            if not self.hasDetailPanel():
                return
            
#            title = None
            
            id = self.detailPanel.getIdentifier()
            
            #print "standardGrid: updateSelection: detailsPanel has id",id,self.detailPanel
                
            number = 0
            rowIndex = 0
            for row in self.panels:
                colIndex = 0
                for pan in row:
                    try:
                        panel_id = pan.getIdentifier()
                        #print "standardGrid: updateSelection: panel has id",`panel_id`
                    except:
                        panel_id = None
                        
                    if panel_id is None or repr(panel_id) != repr(id):
                        #print 'item deselected2'
                        pan.deselect(rowIndex,colIndex)#number = number)
                    else:
                        pan.select(rowIndex,colIndex)
                    number += 1
                    colIndex += 1
                rowIndex += 1
        except:
            # I sometimes get UnicodeErrors here somewhere
            print_exc()

    def hasDetailPanel(self):
        if self.detailPanel:
            return True
        try:
            self.detailPanel = self.guiUtility.standardDetails
        except:
            pass
        return self.detailPanel is not None

    def moreData(self):

        if self.dod:
            needed = self.items * 3 + self.currentData # 3 -> load 2 pages in advance

            if needed > 0:
                if DEBUG:
                    print >>sys.stderr,"standardGrid: Web2.0: fetching total of", needed,"items"
                self.dod.request(needed)
    
    def __del__(self):
        if self.dod:
            self.dod.unregister(self.updateDod)
            self.dod.stop()
            
    def keyTypedOnGridItem(self, event):
        obj = event.GetEventObject()
        if DEBUG:
            print >>sys.stderr,'standardGrid: keyTyped: in %s' % obj.__class__.__name__
        while obj.__class__ != self.subPanelClass:
            obj = obj.GetParent()
        
        # Jelle: Turn of key navigation under windows. Windows already has a focus traversal policy and changes 
        # the focus of panel.
        if sys.platform == 'win32': 
            return
        
        if not obj.selected and sys.platform != 'win32':
            return

        keyCode = event.GetKeyCode()
        # Get coord of keytyped panel
        rowIndex = 0
        xpan = ypan = None
        for row in self.panels:
            colIndex = 0    
            for pan in row:
                if obj == pan:
                    (xpan, ypan) = colIndex, rowIndex
                    if DEBUG:
                        print >>sys.stderr,'standardGrid: keyTyped: found: %d, %d' % (colIndex, rowIndex)
                    break
                colIndex += 1
            rowIndex += 1
        if xpan == None:
            raise Exception('Could not find selected panel')
        xpanold = xpan
        ypanold = ypan
        if sys.platform != 'win32':
            if keyCode == wx.WXK_UP:
                ypan = max(0, ypan-1)
            elif keyCode == wx.WXK_DOWN:
                ypan = min(self.currentRows-1, ypan+1)
            elif keyCode == wx.WXK_LEFT:
                xpan = max(0, xpan -1)
            elif keyCode == wx.WXK_RIGHT:
                xpan = min(self.cols-1, xpan+1)
        else:
            if keyCode == wx.WXK_UP:
                if xpan == self.cols-1:
                    xpan = 0
                else:
                    xpan+=1
                    ypan = max(0, ypan-1)
            elif keyCode == wx.WXK_DOWN:
                if xpan == 0:
                    xpan = self.cols-1
                else:
                    xpan = xpan -1
                    ypan = min(self.currentRows-1, ypan+1)
        # Get data of new panel
        if DEBUG:
            print >>sys.stderr,'standardGrid: Old: %s, New: %s' % ((xpanold, ypanold), (xpan, ypan))
        if xpanold != xpan or ypanold != ypan or sys.platform =='win32':
            newpanel = self.panels[ypan][xpan]
            if newpanel.data != None:
                # select new panel
                #newpanel.SetFocus()
                self.guiUtility.selectData(newpanel.data)
        event.Skip()
                
    def getFirstPanel(self):
        try:
             hSizer = self.vSizer.GetItem(1).GetSizer()
             panel = hSizer.GetItem(0).GetWindow()
             return panel
        except:
            return None
        
    def toggleColumnHeaders(self, show):
        # show or hide columnheaders
        if bool(self.columnHeader) == show:
                return
        if show:
            panel = self.getFirstPanel()
            if panel:
                self.columnHeader = ColumnHeaderBar(self, panel)
                self.columnHeaderSizer.Detach(0)
                self.columnHeaderSizer.Add(self.columnHeader, 1, wx.EXPAND, 0)
                self.columnHeaderSizer.Layout()
        else:
            self.columnHeaderSizer.Detach(0)
            self.columnHeader.Destroy()
            self.columnHeader = None
            self.columnHeaderSizer.AddSpacer(5)
            self.columnHeaderSizer.Layout()
        self.vSizer.Layout()
    
    def stopWeb2Search(self):
        if self.dod:
            self.dod.unregister(self.updateDod)
            self.dod.stop()
            
class filesGrid(standardGrid):
    def __init__(self):
#        columns = 5
#        self.subPanelHeight = 108 # This will be update after first refresh
        columns = (5, 1)
        subPanelHeight = (5*22, 22)
        standardGrid.__init__(self, columns, subPanelHeight, orientation='horizontal')
        
    def getSubPanel(self, keyfun):
        return FilesItemPanel(self, keyfun)

    
class personsGrid(standardGrid):
    def __init__(self):
        columns = (6, 1)
        subPanelHeight = (5*22, 22)
        standardGrid.__init__(self, columns, subPanelHeight, orientation='horizontal')
        
    def getSubPanel(self, keyfun):
        return PersonsItemPanel(self, keyfun)

class friendsGrid(standardGrid):
    def __init__(self):   
        columns = (1,1)
        subPanelHeight = (22,22) # This will be update after first refresh
        standardGrid.__init__(self, columns, subPanelHeight, orientation='vertical', viewmode='list')
        
    def getSubPanel(self, keyfun):
        return FriendsItemPanel(self, keyfun)
    
class libraryGrid(standardGrid):
    def __init__(self):
        columns = (1,1)
        subPanelHeight = (22, 22) # This will be update after first refresh
        standardGrid.__init__(self, columns, subPanelHeight, orientation='horizontal', viewmode='list')
            
    def getSubPanel(self, keyfun):
        return LibraryItemPanel(self, keyfun)
    
class subscriptionsGrid(standardGrid):
    def __init__(self):
        columns = 1
        subPanelHeight = 22 # This will be update after first refresh
        standardGrid.__init__(self, columns, subPanelHeight, orientation='horizontal')
        
    def getSubPanel(self, keyfun):
        return SubscriptionsItemPanel(self, keyfun)

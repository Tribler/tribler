import os, sys, wx
from Tribler.vwxGUI.MainXRC import GUIUtility
from Tribler.Dialogs.ContentFrontPanel import ImagePanel, DetailPanel, TorrentPanel
from Tribler.utilities import *
from traceback import print_exc

import wx, os, sys, math
import wx.xrc as xrc

DEBUG = True

class torrentGrid(wx.Panel):
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

        #self.SetSize((500,500))
        self.SetBackgroundColour(wx.BLACK)
        self.parent = None
        self.guiUtility = GUIUtility.getInstance()
        self.guiUtility.report(self)
        self.utility = self.guiUtility.utility
        self.detailPanel = DetailPanel(self, self.utility)
        self.cols = 2
        self.items = 0
        self.data = {}
        self.currentData = 0
        
        self.addComponents()
        self.Centre()
        self.Show()
        
        
    def addComponents(self):
        self.Show(False)
        
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        
        self.staticGrid = StaticGridPanel(self, self.cols)
        self.vSizer.Add(self.staticGrid, 1, wx.ALL, 1)
        self.pagerPanel = PagerPanel(self)
        self.vSizer.Add(self.pagerPanel, 0, wx.ALL, 1)
        
        self.SetSizer(self.vSizer);
        self.SetAutoLayout(1);
        self.Layout();
        self.Refresh()
        #print "vSizer: %s, Panel: %s"% (self.vSizer.GetSize(), self.GetSize())

    def setData(self, dataList, resetPages = True):
        #print 'SetData by thread: %s' % threading.currentThread()
        self.data = dataList
        if resetPages:
            self.currentData = 0
            self.pagerPanel.currentPage = 0
        self.refreshPanels()
        
        
    def refreshPanels(self):
        "Refresh TorrentPanels with correct data and refresh pagerPanel"
        self.pagerPanel.refresh()
                
        if self.data == None:
            self.staticGrid.clearAllData()
        else:
            for i in range(0, self.items):
                dataIndex = i+ self.currentData
                if dataIndex < len(self.data):
                    self.staticGrid.setData(i, self.data[dataIndex])
                else:
                    self.staticGrid.setData(i, None)
        
        self.staticGrid.updateSelection()
    
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
            
       
 


class StaticGridPanel(wx.Panel):
    """
    A panel that shows subpanels with a static column count
    and a rowcount dependend on the size of the StaticGridPanel
    
    """
    def __init__(self, parent, cols):
        wx.Panel.__init__(self, parent, -1, size=wx.DefaultSize)
        #self.SetSize((500,500))
        
        self.parent = parent
        self.detailPanel = parent.detailPanel
        self.cols = cols
        self.currentRows = 0
        self.subPanelHeight = 100 # This will be update after first refresh
        
        self.panels = []
        self.currentData = 0
        self.Bind(wx.EVT_SIZE, self.onResize)
        
        self.addComponents()
        self.Centre()
        self.Show()
        self.Layout();
        self.Refresh()
        #print "vSizer: %s, Panel: %s"% (self.vSizer.GetSize(), self.GetSize())
        
        
    def addComponents(self):
        self.Show(False)
        self.SetBackgroundColour(wx.WHITE)
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        self.calculateRows()
        self.SetSizer(self.vSizer);
        self.SetAutoLayout(1);
        

    def setData(self, panelNumber, data):
        try:
            hSizer = self.vSizer.GetItem(panelNumber%self.currentRows).GetSizer()
            panel = hSizer.GetItem(panelNumber/ self.currentRows).GetWindow()
            
            panel.setData(data)
        except:
            print >>sys.stderr,"contentpanel: Error: Could not set data in panel number %d, with %d cols" % (panelNumber, self.cols)
            print_exc(file=sys.stderr)
    
    def clearAllData(self):
        for i in range(0, self.items):
            self.setData(i, None)
            
    def onResize(self, event=None):
        
        #print ".",
        self.calculateRows()
        if event:
            event.Skip()
        
    def updateSubPanelHeight(self):
        try:
            self.subPanelHeight = self.vSizer.GetItem(0).GetSizer().GetItem(0).GetWindow().GetSize()[1]
        except:
            #print 'Could not get subpanelheight'
            pass
        
    def calculateRows(self):
    
        size = self.GetSize()
        oldRows = self.currentRows
        self.updateSubPanelHeight()
        if size[1] < 50 or self.subPanelHeight == 0:
            self.currentRows = 0
            self.items = 0
        else:
            self.currentRows = size[1] / self.subPanelHeight
            self.items = self.cols * self.currentRows
        
        if oldRows != self.currentRows: #changed
            if DEBUG:
                print >>sys.stderr,'contentpanel: Size updated to %d rows and %d columns, oldrows: %d'% (self.currentRows, self.cols, oldRows)
            
            self.updatePanel(oldRows, self.currentRows)
            self.parent.gridResized(self.currentRows)
            
    def updatePanel(self, oldRows, newRows):
        #
        if newRows > oldRows:
            for i in range(oldRows, newRows):
                hSizer = wx.BoxSizer(wx.HORIZONTAL)
                self.panels.append([])
                for panel in range(0, self.cols):
                    dataPanel = TorrentPanel(self)
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
        
        title = None
        # Select first item
        if not self.detailPanel.data:
            try:
                firstItem = self.panels[0][0].data
                if firstItem:
                    self.detailPanel.setData(firstItem)
                    title = self.detailPanel.data.get('content_name')
            except:
                pass
        
        if self.detailPanel.data:
            title = self.detailPanel.data.get('content_name')

            
        
        for row in self.panels:
            for pan in row:
                try:
                    paneltitle = pan.data['content_name']
                except:
                    paneltitle = None
                    
                if paneltitle != title or paneltitle == None:
                    pan.deselect()
                else:
                    pan.select()
        

class GridPanel(wx.Panel):
    """
    GridPanel adds paging functionality (a PagerPanel) to the StaticGridPanel.
    Use setData() and setPageNumber() for content selection.
    """
    def __init__(self, parent, cols):
        wx.Panel.__init__(self, parent, -1, size=wx.DefaultSize)
        #self.SetSize((500,500))
        #self.SetBackgroundColour(wx.RED)
        self.parent = parent
        self.detailPanel = parent.detailPanel
        self.utility = parent.utility
        self.cols = cols
        self.items = 0
        self.data = None
        self.currentData = 0
        
        self.addComponents()
        self.Centre()
        self.Show()
        
        
    def addComponents(self):
        self.Show(False)
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        
        self.staticGrid = StaticGridPanel(self, self.cols)
        self.vSizer.Add(self.staticGrid, 1, BORDER_EXPAND, 1)
        self.pagerPanel = PagerPanel(self)
        self.vSizer.Add(self.pagerPanel, 0, BORDER_EXPAND, 1)
        
        self.SetSizer(self.vSizer);
        self.SetAutoLayout(1);
        self.Layout();
        self.Refresh()
        #print "vSizer: %s, Panel: %s"% (self.vSizer.GetSize(), self.GetSize())

    def setData(self, dataList, resetPages = True):
        #print 'SetData by thread: %s' % threading.currentThread()
        self.data = dataList
        if resetPages:
            self.currentData = 0
            self.pagerPanel.currentPage = 0
        self.refreshPanels()
        
        
    def refreshPanels(self):
        "Refresh TorrentPanels with correct data and refresh pagerPanel"
        self.pagerPanel.refresh()
                
        if self.data == None:
            self.staticGrid.clearAllData()
        else:
            for i in range(0, self.items):
                dataIndex = i+ self.currentData
                if dataIndex < len(self.data):
                    self.staticGrid.setData(i, self.data[dataIndex])
                else:
                    self.staticGrid.setData(i, None)
        
        self.staticGrid.updateSelection()
    
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
            



class PagerPanel(wx.Panel):
    def __init__(self, parent, numPages=10):
        wx.Panel.__init__(self, parent, -1)

        self.beginPage = 0
        self.currentPage = 0
        self.numPages = numPages
        self.totalPages = 0
        self.totalItems = 0
        self.itemsPerPage = 0
        self.currentDots = [None, None]
        
        self.utility = parent.utility
        self.pageNumbers = []
        self.staticGrid = parent.staticGrid
        self.parent = parent
        self.SetMinSize((50, self.GetCharHeight()))
        self.addComponents()
        self.Centre()
        self.Show()

    def addComponents(self):
        self.SetBackgroundColour(wx.WHITE)
        self.normalFont = wx.Font(8,74,90,90,0,"Arial")
        self.boldFont  = wx.Font(10,74,90,wx.BOLD,1,"Arial")
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.number = wx.StaticText(self,-1,"",wx.Point(3,111),wx.Size(49,13))
        self.number.SetLabel('0 %s' % self.utility.lang.get('item')+'s')
        self.number.SetFont(self.normalFont)
        self.hSizer.Add(self.number, 3, wx.ALL, 0)
        
        # left arrows
#        self.leftPages = ImagePanel(self)
#        self.leftPages.SetBitmap(wx.Bitmap("prev2.gif",wx.BITMAP_TYPE_GIF))
#        self.hSizer.Add(self.leftPages, 0, BORDER_EXPAND, 0)
        self.left = ImagePanel(self)
        self.left.SetBackgroundColour(wx.WHITE)
        self.left.SetBitmap("left.png")
        self.left.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        self.hSizer.Add(self.left, 0, wx.LEFT|wx.RIGHT, 10)
        
        #page numbers
        self.refreshPageNumbers()
        
        
        self.right = ImagePanel(self)
        self.right.SetBackgroundColour(wx.WHITE)
        self.right.SetBitmap("right.png")
        self.right.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        self.hSizer.Add(self.right, 0, wx.LEFT|wx.RIGHT, 10)
        
       
        
        self.hSizer.SetMinSize((50,50))
        self.SetSizer(self.hSizer);self.SetAutoLayout(1);self.Layout();
        self.Refresh()
   
   
    def refreshPageNumbers(self):
        
        # Update beginPage (first page number on screen)
        if self.currentPage >= self.beginPage+self.numPages:
            self.beginPage +=1
        
        self.beginPage = max(0, min(self.totalPages-self.numPages, self.beginPage))
        if self.currentPage <= self.beginPage-1:
                self.beginPage = max(0, self.beginPage - 1)
                
        rightDots = self.beginPage+self.numPages < self.totalPages
        leftDots = self.beginPage != 0
        self.setPageNumbers(self.beginPage, min(self.numPages,self.totalPages) , self.currentPage, leftDots, rightDots)
        self.parent.setPageNumber(self.currentPage)
        
        
    def setPageNumbers(self, begin, number, current, leftDots, rightDots):
        """
        Put the right numbers in the pagefield. If necessary, create new statictexts.
        Highlight current page number
        """
        
        #print 'Begin %d, number %d, current %d' % (begin, number, current)
        
        refresh = False
        # Guarantee right amount of statictexts
        currentPageNumber = len(self.pageNumbers)
        if number > currentPageNumber:
            while (len(self.pageNumbers) < number):
                text = StaticText(self, -1, "")
                text.SetBackgroundColour(self.GetBackgroundColour())
                text.Bind(wx.EVT_LEFT_UP, self.mouseAction)
                self.pageNumbers.append(text)
                self.hSizer.Insert(len(self.pageNumbers)+1, text, 0, wx.LEFT|wx.RIGHT, 10)
            refresh = True
        elif number < currentPageNumber:
            for i in range(number, currentPageNumber):
                self.hSizer.Detach(self.pageNumbers[i])
                self.pageNumbers[i].Destroy()
                #self.pageNumbers[i].Show(False)
            self.pageNumbers = self.pageNumbers[:number]
            refresh = True
          
        # Manage dots before and after page numbers
        if rightDots and not self.currentDots[1]:
            dots = wx.StaticText(self, -1, "...")
            extra =  int(bool(self.currentDots[0]))
            
            self.hSizer.Insert(len(self.pageNumbers)+2+extra, dots, 0, wx.LEFT|wx.RIGHT, 2)
            self.currentDots[1] = dots
            refresh = True
        
        if not rightDots and self.currentDots[1]:
            self.hSizer.Detach(self.currentDots[1])
            self.currentDots[1].Destroy()
            self.currentDots[1] = None
            refresh = True
        
        if leftDots and not self.currentDots[0]:
            dots = wx.StaticText(self, -1, "...")
            
            self.hSizer.Insert(2, dots, 0, wx.LEFT|wx.RIGHT, 2)
            self.currentDots[0] = dots
            refresh = True
        
        if not leftDots and self.currentDots[0]:
            self.hSizer.Detach(self.currentDots[0])
            self.currentDots[0].Destroy()
            self.currentDots[0] = None
            refresh = True
            
        
        if refresh:
            self.hSizer.Layout()
            self.Refresh()
            self.Show(True)
            
        #print '%d statictexts' % (len(self.pageNumbers))
        # Put right numbers in statictexts
        page = begin
        for panel in self.pageNumbers:
            panel.SetLabel(str(page+1))
            if page == current:
                
                panel.SetFont(self.boldFont)
            else:
                panel.SetFont(self.normalFont)
            page+=1
    
    def refresh(self):
        "Called by Grid if size or data changes"
        self.totalItems = len(self.parent.data)
        self.itemsPerPage = self.parent.items
        
        # if dummy item "Searching for content is shown, do not count it as content
        if self.totalItems == 1 and self.parent.data[0].get('content_name','no_name') == self.utility.lang.get('searching_content'):
            self.totalItems = 0
        
        
        if self.itemsPerPage == 0:
            self.totalPages = 0
        else:
            self.totalPages = int(math.ceil(self.totalItems/float(self.itemsPerPage)))

            
        category = 'test_cat'
        self.number.SetLabel('%d %s %s%s / %d %s%s' % (self.totalItems, category.lower(), self.utility.lang.get('item'), getPlural(self.totalItems), self.totalPages, self.utility.lang.get('page'), getPlural(self.totalPages)))
        
        if self.currentPage >= self.totalPages:
            self.currentPage = max(self.totalPages -1, 0)
        self.refreshPageNumbers()

#    def imageClicked(self, event):
#        obj = event.GetEventObject()
#        self.mouseAction(obj, event)
#        
    def mouseAction(self, event):
        
        obj = event.GetEventObject()
        
        old = self.currentPage
        #print '%s did mouse' % obj
        if obj == self.left:
            self.currentPage = max(0, self.currentPage-1)
        elif obj == self.right:
            self.currentPage = min(self.totalPages-1, self.currentPage+1)
        elif obj in self.pageNumbers:
            index = self.pageNumbers.index(obj)
            self.currentPage = self.beginPage+index
        else:
            event.Skip()
            return
        
        self.refreshPageNumbers()
        

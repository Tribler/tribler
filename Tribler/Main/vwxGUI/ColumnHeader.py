import wx, sys
from Tribler.Main.vwxGUI.bgPanel import ImagePanel
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility

from Tribler.Main.vwxGUI.TriblerStyles import TriblerStyles
from Tribler.Main.vwxGUI.standardFilter import filesFilter


class ColumnHeader(wx.Panel):
    
    bitmapOrderUp = 'upSort'
    bitmapOrderDown = 'downSort'
    
    def __init__(self, parent, title, picture, order, tip, sorting, reverse, component, dummy):        
        wx.Panel.__init__(self, parent, -1)
        self.type = None
        self.triblerStyles = TriblerStyles.getInstance()
        self.unselectedColour = self.triblerStyles.sortingColumns(1)
        self.selectedColour = self.triblerStyles.sortingColumns(2)        
        self.dummy = dummy
        self.component = component

        self.addComponents(title, picture, tip, component)
        if component == None:
#            print '1. component = None'
            self.setOrdering(order)
            
        self.sorting = sorting
        if reverse:
            self.reverse = True
        else:
            self.reverse = False
        
        
    def addComponents(self, title, picture, tip, component):
        self.SetBackgroundColour(self.unselectedColour)
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.text = None
        self.icon = None
        self.title = title

        print >>sys.stderr,"ColumnHeader: picture is",picture

        if self.component == None or self.component == 'comboboxSort':
            if picture:
                self.icon = ImagePanel(self)
                self.icon.setBitmapFromFile(picture)
                self.icon.setBackground(self.unselectedColour)
                self.hSizer.Add(self.icon, 0, wx.TOP,1 )
            if title:
                if not picture:
                    self.hSizer.Add([10,5],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
                self.text = wx.StaticText(self, -1, title)
                self.triblerStyles.setDarkText(self.text)
                self.hSizer.Add(self.text, 1, wx.TOP, 3)            
            
            self.dummy = self.dummy or (not picture and not title)
            if picture == None and title == None:
                raise Exception('No text nor an icon in columnheader')
            
            if False:
                self.sortIcon = ImagePanel(self)
                self.sortIcon.setBackground(self.unselectedColour)
                self.sortIcon.Hide()
                self.hSizer.Add(self.sortIcon, 0, wx.TOP, 1)            
                self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
            else:
                self.sortIcon = None
    
            # 2.8.4.2 return value of GetChildren changed
            wl = [self]
            for c in self.GetChildren():
                wl.append(c)
            for element in wl:
                ##element.Bind(wx.EVT_LEFT_UP, self.clicked)
                ##element.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
                element.SetToolTipString(tip)
        
        elif self.component == 'comboboxFilter':            
            self.sortIcon = None
            #self.filesFilter = filesFilter(self)
            #self.hSizer.Add(self.filesFilter, 1, wx.BOTTOM, 0)      
            
        self.SetSizer(self.hSizer)
        self.SetAutoLayout(True)
        self.hSizer.Layout()
        
    def setText(self, t):
        self.text.SetLabel(t)
        
    def setOrdering(self, type):
        # up, down or none
        #print 'Set ordering to %s' % type
        self.type = type
        if self.component == None:
            if type == 'up':
                self.sortIcon.setBitmapFromFile(self.bitmapOrderUp)
                self.setColour(self.selectedColour)
                if not self.sortIcon.IsShown():
                    self.sortIcon.Show()
            elif type == 'down':
                self.sortIcon.setBitmapFromFile(self.bitmapOrderDown)
                self.setColour(self.selectedColour)
                if not self.sortIcon.IsShown():
                    self.sortIcon.Show()
            else:
                if self.sortIcon:
                    self.sortIcon.setBitmapFromFile(self.bitmapOrderDown)
                    self.sortIcon.Hide()
                self.setColour(self.unselectedColour)
        
        self.GetSizer().Layout()
    
    def clicked(self, event):
        if self.dummy:
            return
        if not self.type or self.type == 'up':
            newType = 'down'
        elif self.type == 'down':
            newType = 'up'
        self.setOrdering(newType)
        self.GetParent().setOrdering(self, newType)
        
        
        
    def mouseAction(self, event):
        event.Skip()
        if self.type:
            return
        colour = None
        if event.Entering():
            colour = self.selectedColour

        elif event.Leaving():
            if sys.platform == 'win32':
                position = event.GetPosition()
                for i in xrange(2):
                    position[i]+=event.GetEventObject().GetPosition()[i]
                    position[i]-=self.GetPosition()[i]
                size = self.GetSize()

                if position[0]<0 or position[0]>=size[0] or position[1]<0 or position[1]>=size[1]:
                    colour = self.unselectedColour
            else:
                colour = self.unselectedColour
        if colour:
            self.setColour(colour)
            
        
    def setColour(self, colour):
        for element in [self, self.icon, self.sortIcon, self.text]:
            if element:
                if element.__class__ == ImagePanel:
                    element.setBackground(colour)
                element.SetBackgroundColour(colour)
        self.Refresh()
                
class ColumnHeaderBar(wx.Panel):
    
    def __init__(self, parent, itemPanel):
#        print 'itemPanel = %s' % itemPanel
        self.itemPanel = itemPanel
        wx.Panel.__init__(self, parent, -1)
        self.columns = []
        self.dynamicColumnName = None
        self.guiUtility = GUIUtility.getInstance()
        self.addComponents()
        #self.SetMinSize((-1,30))
        self.Show(True)
        
    def addComponents(self):
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        #self.hSizer.Add([0,20],0,wx.FIXED_MINSIZE,0)
        self.triblerStyles = TriblerStyles.getInstance()
#        self.filesFilter = filesFilter()
#        self.filesFilter = testFilter(self)
#        print 'filesFilter = %s' % self.filesFilter
#        self.filesFilter.SetSize((30,20))
        
        columns = self.itemPanel.getColumns()
        currentSorting = self.guiUtility.standardOverview.getSorting()
        comboboxSortChoices = []
        #print 'currentSorting: %s' % str(currentSorting)
        for dict in columns:
#            colours = (wx.Colour(203,203,203), wx.Colour(223,223,223))
            if (type(currentSorting) == str and currentSorting == dict['sort'] or
                type(currentSorting) == tuple and currentSorting[0] == dict['sort']):
                if (len(currentSorting) == 2 and currentSorting[1] == 'increase') ^ dict.get('reverse', False):
                    beginorder = 'up'
                else:
                    beginorder = 'down'
            else:
                beginorder = None
            header = ColumnHeader(self, dict.get('title'), dict.get('pic'), beginorder, dict['tip'], dict['sort'], dict.get('reverse'), dict.get('component'), dict.get('dummy', False))
            self.columns.append(header)            
            
            if dict.get('component') != 'comboboxSort' :
                self.hSizer.Add(header, dict.get('weight',0), wx.EXPAND|wx.BOTTOM, 0)

                if columns.index(dict) != len(columns)-1:
                    line = wx.StaticLine(self,-1,wx.DefaultPosition, ((0,0)), wx.LI_VERTICAL)
                    self.SetBackgroundColour(self.triblerStyles.sortingColumns(2))
                    self.hSizer.Add(line, 0, wx.LEFT|wx.RIGHT|wx.EXPAND, 0)
                    if dict.get('width'):
                        header.SetSize((dict['width']+6, -1))
                        header.SetMinSize((dict['width']+6, -1))
                else:
                    if dict.get('width'):
                        header.SetSize((dict['width']+3, -1))
                        header.SetMinSize((dict['width']+3, -1))
                    
            else:
                header.Hide()
                comboboxSortChoices.append(header.title)

        
#        print comboboxSortChoices[0]
        if len(comboboxSortChoices) != 0:
            self.extraSorting = wx.ComboBox(self,-1,comboboxSortChoices[0], wx.DefaultPosition,wx.Size(70,10),comboboxSortChoices, wx.FIXED_MINSIZE|wx.CB_DROPDOWN|wx.CB_READONLY)
            self.extraSorting.Bind(wx.EVT_COMBOBOX, self.extraSortingMouseaction)
            self.hSizer.Add(self.extraSorting, 0, wx.EXPAND|wx.BOTTOM, 0)
            self.dynamicColumnName = comboboxSortChoices[0]
#            print 'tb > comboboxSortChoices[0] = %s' % comboboxSortChoices[0]
        
#        self.dynamicColumnName = comboboxSortChoices[0].sorting
#        self.extraSortingMouseaction(event='')
        
        #self.SetBackgroundColour(wx.Colour(100,100,100))
#        self.hSizer.Add(self.filesFilter, 0, wx.BOTTOM|wx.FIXED_MINSIZE, 0)
        self.hSizer.Layout()
        self.SetSizer(self.hSizer)
        self.SetAutoLayout(True)
        
    def setOrdering(self, column, ordering):
        for header in self.columns:
            if header != column:
                header.setOrdering(None)
        if ordering == 'up' and not column.reverse or ordering == 'down' and column.reverse:
            reverse = True
        else:
            reverse = False
        oldfilter = self.guiUtility.standardOverview.getFilter()
        if oldfilter:
            self.sorting = oldfilter.getState().copy()
        else:
            from Tribler.Main.vwxGUI.standardGrid import GridState
            self.sorting = GridState(self.guiUtility.standardOverview.mode, 'all', None) # peerview has no filter
        
        self.sorting.sort = column.sorting
        self.sorting.reverse = reverse
        self.guiUtility.standardOverview.filterChanged(self.sorting)
        
    def getSorting(self):
        return self.sorting
    
    def extraSortingMouseaction(self, event):
        selected = self.extraSorting.GetValue()
        selectedColumn = [c for c in self.columns if c.title == selected]
        self.dynamicColumnName = selectedColumn[0].sorting
        selectedColumn[0].clicked(event)
        
    def getCategoryCombo(self):
        for header in self.columns:
            try:
                return header.filesFilter
            except:
                pass
        return None
            
    
    
     

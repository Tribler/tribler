import wx
from Tribler.vwxGUI.bgPanel import ImagePanel
from Tribler.vwxGUI.GuiUtility import GUIUtility


class ColumnHeader(wx.Panel):
    
    bitmapOrderUp = 'upSort'
    bitmapOrderDown = 'downSort'
    
    def __init__(self, parent, title, picture, order, tip, sorting, colours):
        wx.Panel.__init__(self, parent, -1)
        self.type = None
        self.selectedColour = colours[0]
        self.unselectedColour = colours[1]
        self.addComponents(title, picture, tip)
        self.setOrdering(order)
        self.sorting = sorting
        
        
        
    def addComponents(self, title, picture, tip):
        self.SetBackgroundColour(self.unselectedColour)
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.text = None
        self.icon = None
        if title:
            self.hSizer.Add([15,5],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
            self.text = wx.StaticText(self, -1, title)
            self.hSizer.Add(self.text, 1, wx.TOP, 3)
        elif picture:
            self.icon = ImagePanel(self)
            self.icon.setBitmapFromFile(picture)
            self.icon.setBackground(self.unselectedColour)
            self.hSizer.Add(self.icon, 1, wx.ALL, 1)
        else:
            raise Exception('No text nor an icon in columnheader')
        self.sortIcon = ImagePanel(self)
        self.sortIcon.SetMinSize((20,20))
        self.sortIcon.setBackground(self.unselectedColour)
        self.sortIcon.Hide()
        self.hSizer.Add(self.sortIcon, 0, wx.ALL, 1)
        self.SetSizer(self.hSizer)
        self.SetAutoLayout(True)
        self.hSizer.Layout()
        for element in self.GetChildren()+[self]:
            element.Bind(wx.EVT_LEFT_UP, self.clicked)
            element.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
            element.SetToolTipString(tip)
        
    def setText(self, t):
        self.text.SetLabel(t)
        
    def setOrdering(self, type):
        # up, down or none
        #print 'Set ordering to %s' % type
        self.type = type
        if type == 'up':
            self.sortIcon.setBitmapFromFile(self.bitmapOrderUp)
            if not self.sortIcon.IsShown():
                self.sortIcon.Show()
        elif type == 'down':
            self.sortIcon.setBitmapFromFile(self.bitmapOrderDown)
            if not self.sortIcon.IsShown():
                self.sortIcon.Show()
        else:
            self.sortIcon.setBitmapFromFile(self.bitmapOrderDown)
            self.sortIcon.Hide()
        self.GetSizer().Layout()
    
    def clicked(self, event):
        if not self.type or self.type == 'down':
            newType = 'up'
        elif self.type == 'up':
            newType = 'down'
        self.setOrdering(newType)
        self.GetParent().setOrdering(self, newType)
        
    def mouseAction(self, event):
        event.Skip()
        colour = None
        if event.Entering():
            colour = self.selectedColour

        elif event.Leaving():
            colour = self.unselectedColour
        if colour:
            for element in [self, self.icon, self.sortIcon, self.text]:
                if element:
                    if element.__class__ == ImagePanel:
                        element.setBackground(colour)
                    element.SetBackgroundColour(colour)
            self.Refresh()
        
class ColumnHeaderBar(wx.Panel):
    
    
    def __init__(self, parent, itemPanel):
        self.itemPanel = itemPanel
        wx.Panel.__init__(self, parent, -1)
        self.columns = []
        self.guiUtility = GUIUtility.getInstance()
        self.addComponents()
        #self.SetMinSize((-1,30))
        self.Show(True)
        
    def addComponents(self):
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        columns = self.itemPanel.getColumns()
        for dict in columns:
            colours = (wx.Colour(203,203,203), wx.Colour(223,223,223))
            header = ColumnHeader(self, dict.get('title'), dict.get('pic'), dict.get('order'), dict['tip'], dict['sort'], colours)
            if dict.get('width'):
                header.SetSize((dict['width'], -1))
                header.SetMinSize((dict['width'], -1))
            self.hSizer.Add(header, dict.get('weight',0), wx.EXPAND|wx.BOTTOM, 0)
            self.columns.append(header)
            if columns.index(dict) != len(columns)-1:
                line = wx.StaticLine(self,-1,wx.DefaultPosition, wx.DefaultSize, wx.LI_VERTICAL)
                line.SetBackgroundColour(colours[0])
                self.hSizer.Add(line, 0, wx.LEFT|wx.RIGHT|wx.EXPAND, 3)
        
        #self.SetBackgroundColour(wx.Colour(100,100,100))
        self.hSizer.Layout()
        self.SetSizer(self.hSizer)
        self.SetAutoLayout(True)
        
    def setOrdering(self, column, ordering):
        for header in self.columns:
            if header != column:
                header.setOrdering(None)
        if ordering == 'up':
            self.sorting = (column.sorting, 'increase')
        else:
            self.sorting = (column.sorting, 'decrease')
        self.guiUtility.standardOverview.filterChanged([None, self.sorting])
        
    def getSorting(self):
        return self.sorting
    
    
     

import wx
from Tribler.vwxGUI.bgPanel import ImagePanel


class ColumnHeader(wx.Panel):
    
    bitmapOrderUp = 'up'
    bitmapOrderDown = 'down'
    
    def __init__(self, parent, title, picture, order, tip, colour):
        wx.Panel.__init__(self, parent, -1)
        self.colour = colour
        self.type = None
        self.addComponents(title, picture)
        self.setOrdering(order)
        self.SetToolTipString(tip)
        
        
        
    def addComponents(self, title, picture):
        self.SetBackgroundColour(self.colour)
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        if title:
            self.text = wx.StaticText(self, -1, title)
            self.hSizer.Add(self.text, 1, wx.ALL, 1)
        elif picture:
            self.icon = ImagePanel(self)
            self.icon.setBitmapFromFile(picture)
            self.icon.setBackground(self.colour)
            self.hSizer.Add(self.icon, 1, wx.ALL, 1)
        else:
            raise Exception('No text nor an icon in columnheader')
        self.sortIcon = ImagePanel(self)
        self.sortIcon.SetMinSize((20,20))
        self.sortIcon.setBackground(self.colour)
        self.sortIcon.Hide()
        self.hSizer.Add(self.sortIcon, 0, wx.ALL, 1)
        self.SetSizer(self.hSizer)
        self.SetAutoLayout(True)
        self.hSizer.Layout()
        for element in self.GetChildren()+[self]:
            element.Bind(wx.EVT_LEFT_UP, self.clicked)
        
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
        
class ColumnHeaderBar(wx.Panel):
    
    
    def __init__(self, parent, itemPanel):
        self.itemPanel = itemPanel
        wx.Panel.__init__(self, parent, -1)
        self.columns = []
        self.addComponents()
        #self.SetMinSize((-1,30))
        self.Show(True)
        
    def addComponents(self):
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        columns = self.itemPanel.getColumns()
        for dict in columns:
            colour = wx.Colour(190,190,190)
            header = ColumnHeader(self, dict.get('title'), dict.get('pic'), dict.get('order'), dict['tip'], colour)
            if dict.get('width'):
                header.SetSize((dict['width'], -1))
                header.SetMinSize((dict['width'], -1))
            self.hSizer.Add(header, dict.get('weight',0), wx.ALL|wx.EXPAND, 0)
            self.columns.append(header)
            if columns.index(dict) != len(columns)-1:
                line = wx.StaticLine(self,-1,wx.DefaultPosition, wx.DefaultSize, wx.LI_VERTICAL)
                self.hSizer.Add(line, 0, wx.ALL|wx.EXPAND, 0)
        
        #self.SetBackgroundColour(wx.Colour(100,100,100))
        self.hSizer.Layout()
        self.SetSizer(self.hSizer)
        self.SetAutoLayout(True)
        
    def setOrdering(self, column, ordering):
        for header in self.columns:
            if header != column:
                header.setOrdering(None)
        
        
    
    
     
import wx
import sys

class ListHeader(wx.Panel):
    def __init__(self, parent, leftImg, rightImg, background, columns):
        wx.Panel.__init__(self, parent)
        self.parent = parent
        self.background = background
        self.SetBackgroundColour(background)
        self.columns = columns

        self.AddComponents(leftImg, rightImg, columns)
        
        self.sortedColumn = -1
        self.sortedDirection = False

    def AddComponents(self, leftImg, rightImg, columns):
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        if isinstance(leftImg, int):
            hSizer.AddSpacer((leftImg, -1))
        else:
            cornerTL_image = wx.Image(leftImg, wx.BITMAP_TYPE_ANY)
            cornerTL = wx.StaticBitmap(self, -1, wx.BitmapFromImage(cornerTL_image))
            hSizer.Add(cornerTL)
        
        self.AddColumns(hSizer, self, columns)
        
        if isinstance(rightImg, int):
            hSizer.AddSpacer((rightImg, -1))
        else:
            cornerTR_image = wx.Image(rightImg, wx.BITMAP_TYPE_ANY)            
            cornerTR = wx.StaticBitmap(self, -1, wx.BitmapFromImage(cornerTR_image))
            hSizer.Add(cornerTR)
        
        self.SetSizer(hSizer)
        
    def AddColumns(self, sizer, parent, columns):
        self.columnHeaders = []
        
        for i in xrange(len(columns)):
            if columns[i].get('name', '') != '':
                if columns[i]['width'] == wx.LIST_AUTOSIZE:
                    option = 1
                    size = wx.DefaultSize
                elif columns[i]['width'] == wx.LIST_AUTOSIZE_USEHEADER:
                    option = 0
                    size = wx.DefaultSize
                else:
                    option = 0
                    size = (columns[i]['width'],-1)
                     
                label = wx.StaticText(parent, i, columns[i]['name'], style = columns[i].get('style',0)|wx.ST_NO_AUTORESIZE, size = size)
                label.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
                label.SetToolTipString('Click to sort table by %s.'%columns[i]['name'])
                label.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
                sizer.Add(label, option, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)
                
                if columns[i]['width'] == wx.LIST_AUTOSIZE_USEHEADER:
                    columns[i]['width'] = label.GetBestSize()[0]
                    
                self.columnHeaders.append(label)
            else:
                spacer = sizer.Add((columns[i]['width'], -1), 0, wx.LEFT|wx.RIGHT, 3)
                self.columnHeaders.append(spacer)
                
                
        self.scrollBar = sizer.AddSpacer((0,0))
        self.scrollBar.Show(False)
        self.scrollBar.sizer = sizer
    
    def ResizeColumn(self, column, width):
        item = self.columnHeaders[column]
        if item.GetSize()[0] != width:
            if getattr(item, 'SetSize', None):
                item.SetSize((width, -1))
            else:
                item.SetSpacer((width, -1))
            self.scrollBar.sizer.Layout()

    def SetSpacerRight(self, right):
        if right > 0:
            dirty = False
            if self.scrollBar.GetSize()[0] != right:
                self.scrollBar.SetSpacer((right, 0))
                dirty = True
            if not self.scrollBar.IsShown():
                self.scrollBar.Show(True)
                dirty = True
            
            if dirty:
                self.scrollBar.sizer.Layout()
        else:
            if self.scrollBar.IsShown():
                self.scrollBar.Show(False)
                self.scrollBar.sizer.Layout()
    
    def OnMouse(self, event):
        if event.Entering() or event.Moving():
            label = event.GetEventObject()
            if not getattr(label, 'selected', False):
                font = label.GetFont()
                
                #Niels: Underline not working on Linux, using italic instead
                if sys.platform == 'linux2': 
                    font.SetStyle(wx.ITALIC)
                else:
                    font.SetUnderlined(True)
                label.SetFont(font)
                
                label.selected = True
                
                for column in self.columnHeaders:
                    if column != label and isinstance(column, wx.StaticText):
                        column.selected = False
                        font = column.GetFont()
                        if sys.platform == 'linux2':
                            font.SetStyle(wx.NORMAL)
                        else:
                            font.SetUnderlined(False)
                        column.SetFont(font)
                
        elif event.Leaving():
            label = event.GetEventObject()
            if getattr(label, 'selected', False):
                font = label.GetFont()
                
                if sys.platform == 'linux2':
                    font.SetStyle(wx.NORMAL)
                else:
                    font.SetUnderlined(False)
                label.SetFont(font)
                
                label.selected = False
        
        elif event.LeftUp():
            self.OnClick(event)
            
        event.Skip() #Allow for windows button hovering
    
    def OnClick(self, event):
        if event.Id == self.sortedColumn:
            self.sortedDirection = not self.sortedDirection
        else:
            self.sortedColumn = event.Id
            self.sortedDirection = self.columns[event.Id].get('sortAsc',False)
            
        self.GetParent().OnSort(event.Id, self.sortedDirection)
    
    def Reset(self):
        pass
        
class TitleHeader(ListHeader):
    def __init__(self, parent, leftImg, rightImg, background, columns, font_increment = 2, fontweight = wx.FONTWEIGHT_BOLD):
        self.font_increment = font_increment
        self.fontweight = fontweight
        ListHeader.__init__(self, parent, leftImg, rightImg, background, columns)
    
    def AddColumns(self, sizer, parent, columns):
        vSizer = wx.BoxSizer(wx.VERTICAL)

        self.title = wx.StaticText(self)
        font = self.title.GetFont()
        font.SetPointSize(font.GetPointSize() + self.font_increment)
        font.SetWeight(self.fontweight)
        self.title.SetFont(font)
        
        titlePanel = self.GetTitlePanel(self)
        subtitlePanel = self.GetSubTitlePanel(self)
        righttitlePanel = self.GetRightTitlePanel(self)
        
        if titlePanel:
            subSizer = wx.BoxSizer(wx.HORIZONTAL)
            subSizer.Add(self.title, 0, wx.RIGHT, 3)
            subSizer.Add(titlePanel, 0, wx.ALIGN_CENTER_VERTICAL)
            titlePanel = subSizer
        else:
            titlePanel = self.title

        if subtitlePanel:
            subSizer = wx.BoxSizer(wx.VERTICAL)
            subSizer.Add(titlePanel, 0, wx.BOTTOM, 3)
            subSizer.Add(subtitlePanel)
            subtitlePanel = subSizer
        else:
            subtitlePanel = titlePanel
        
        if righttitlePanel:
            subSizer = wx.BoxSizer(wx.HORIZONTAL)
            subSizer.Add(subtitlePanel, 0, wx.RIGHT, 3)
            subSizer.Add(righttitlePanel, 1)
            righttitlePanel = subSizer
        else:
            righttitlePanel = subtitlePanel
        
        vSizer.Add(righttitlePanel, 0, wx.EXPAND|wx.ALL, 3)
        if len(columns) > 0:
            hSizer = wx.BoxSizer(wx.HORIZONTAL)
            ListHeader.AddColumns(self, hSizer, self, columns)
            vSizer.Add(hSizer, 0, wx.EXPAND)
        
        sizer.Add(vSizer, 1, wx.EXPAND)
    
    def GetTitlePanel(self, parent):
        pass
    def GetSubTitlePanel(self, parent):
        pass
    def GetRightTitlePanel(self, parent):
        pass
    
    def SetTitle(self, title):
        self.Freeze()
        self.title.SetLabel(title)
        self.Layout()
        self.Thaw()

class SubTitleHeader(TitleHeader):
    def GetSubTitlePanel(self, parent):
        self.subtitle = wx.StaticText(parent)
        return self.subtitle

    def SetSubTitle(self, subtitle):
        self.subtitle.SetLabel(subtitle)
        
class ButtonHeader(TitleHeader):
    def GetRightTitlePanel(self, parent):
        self.play = wx.Button(parent, -1, "Play")
        self.resume = wx.Button(parent, -1, "Resume")
        self.stop = wx.Button(parent, -1, "Stop")
        self.delete = wx.Button(parent, -1, "Delete")

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.AddStretchSpacer()
        hSizer.Add(self.play)
        hSizer.Add(self.resume)
        hSizer.Add(self.stop)
        hSizer.Add(self.delete)
        self.SetStates(False, False, False, False)
        return hSizer

    def SetEvents(self, play, resume, stop, delete):
        self.play.Bind(wx.EVT_BUTTON, play)
        self.resume.Bind(wx.EVT_BUTTON, resume)
        self.stop.Bind(wx.EVT_BUTTON, stop)
        self.delete.Bind(wx.EVT_BUTTON, delete)
        
    def SetStates(self, play, resume, stop, delete):
        self.play.Enable(play)
        self.resume.Enable(resume)
        self.stop.Enable(stop)
        self.delete.Enable(delete)
        
        if play:
            self.play.SetToolTipString('Click to start the playback of this torrent in the player.')
        else:
            self.play.SetToolTip(None)

        if resume:
            self.resume.SetToolTipString('Click to start downloading/seeding this torrent.')
        else:
            self.resume.SetToolTip(None)

        if stop:
            self.stop.SetToolTipString('Click to stop downloading/seeding this torrent.')
        else:
            self.stop.SetToolTip(None)
        
        if delete:
            self.delete.SetToolTipString('Click to remove this torrent from your library.')
        else:
            self.delete.SetToolTip(None)
        
class MyChannelHeader(SubTitleHeader):
    def __init__(self, parent, leftImg, rightImg, background, columns):
        TitleHeader.__init__(self, parent, leftImg, rightImg, background, columns)
        self.SetTitle('My Channel')
    
    def GetTitlePanel(self, parent):
        self.name = wx.StaticText(parent)
        return self.name
        
    def SetName(self, name):
        self.name.SetLabel('( %s\'s Channel )'%name)
        
    def SetNrTorrents(self, nr, nr_favorites):
        subtitle = ''
        if nr == 1:
            subtitle = 'Sharing '+str(nr)+' .torrent'
        else:
            subtitle = 'Sharing '+str(nr)+' .torrents'
            
        if nr_favorites == 0:
            subtitle += ', but not marked as a favorite yet.'
        elif nr_favorites == 1:
            subtitle += ' and 1 Tribler user marked it as one of its favorites.'
        else:
            subtitle += ' and '+str(nr_favorites)+' Tribler users marked it as one of their favorites.'
        self.SetSubTitle(subtitle)
    
    def AddColumns(self, sizer, parent, columns):
        SubTitleHeader.AddColumns(self, sizer, parent, [])

class SearchHeader(TitleHeader):
    def GetTitlePanel(self, parent):
        self.filteredResults = wx.StaticText(parent)
        return self.filteredResults
    
    def GetRightTitlePanel(self, parent):
        self.filter = wx.SearchCtrl(parent)
        self.filter.SetDescriptiveText('Filter results')
        self.filter.Bind(wx.EVT_TEXT, self.OnKey)
        self.filter.SetMinSize((150,-1))
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.AddStretchSpacer()
        hSizer.Add(self.filter, 0, wx.ALIGN_CENTER_VERTICAL)
        return hSizer

    def GetSubTitlePanel(self, parent):
        self.ff = wx.StaticText(parent)
        self.ff.SetToolTipString('Click to toggle Family Filter.')
        self.ff.Bind(wx.EVT_LEFT_UP,self.toggleFamilyFilter)
        return self.ff
    
    def SetFF(self, family_filter):
        if family_filter:
            self.ff.SetLabel('Family Filter is ON')
        else:
            self.ff.SetLabel('Family Filter is OFF')
        
    def toggleFamilyFilter(self, event):
        self.parent.toggleFamilyFilter()
    
    def FilterCorrect(self, regex_correct):
        pass
    def SetNrResults(self, nr = None):
        if nr:
            self.filteredResults.SetLabel('( %d after applying the filter )'%nr)
        else:
            self.filteredResults.SetLabel('')
        self.Layout()
    
    def OnKey(self, event):
        self.parent.OnFilter(self.filter.GetValue().strip())
    
    def Reset(self):
        TitleHeader.Reset(self)
        
        self.filter.Clear()
        self.filteredResults.SetLabel('')

class ChannelHeader(SearchHeader):
    def GetRightTitlePanel(self, parent):
        hSizer = SearchHeader.GetRightTitlePanel(self, parent)
        self.back = wx.Button(parent, wx.ID_BACKWARD, "Go back")
        hSizer.Add(self.back, 0, wx.LEFT, 5)
        return hSizer

    def GetTitlePanel(self, parent):
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.subtitle = wx.StaticText(parent)
        hSizer.Add(self.subtitle)
        hSizer.Add(SearchHeader.GetTitlePanel(self, parent))
        return hSizer
    
    def SetSubTitle(self, subtitle):
        self.subtitle.SetLabel('( %s )'%subtitle)
        
    def SetEvents(self, back):
        self.back.Bind(wx.EVT_BUTTON, back)

class PlayerHeader(TitleHeader):
    def __init__(self, parent, leftImg, rightImg, background, columns, minimize, maximize):
        self.minimize = minimize
        self.maximize = maximize
        TitleHeader.__init__(self, parent, leftImg, rightImg, background, columns)
        self.SetTitle('Player')
        
        self.ShowMinimized(False)
    
    def GetRightTitlePanel(self, parent):
        self.minimize = wx.StaticBitmap(self, -1, wx.BitmapFromImage(wx.Image(self.minimize, wx.BITMAP_TYPE_ANY)))
        self.maximize = wx.StaticBitmap(self, -1, wx.BitmapFromImage(wx.Image(self.maximize, wx.BITMAP_TYPE_ANY)))
        
        self.minimize.Bind(wx.EVT_LEFT_UP, self.OnClick)
        self.maximize.Bind(wx.EVT_LEFT_UP, self.OnClick)
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.AddStretchSpacer()
        hSizer.Add(self.minimize)
        hSizer.Add(self.maximize)
        return hSizer
    
    def OnClick(self, event):
        if self.minimize.IsShown():
            self.parent.OnMinimize()
        else:
            self.parent.OnMaximize()
        
    def ShowMinimized(self, minimized):
        self.minimize.Show(minimized)
        self.maximize.Show(not minimized)
        
        self.title.Show(minimized)
        self.Layout()
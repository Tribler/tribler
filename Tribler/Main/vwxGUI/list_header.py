# Written by Niels Zeilemaker, Egbert Bouman
from Tribler.Main.vwxGUI.widgets import MinMaxSlider, LinkStaticText, NativeIcon, LinkText, BetterText as StaticText, _set_font
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Category.Category import Category
from Tribler.Core.Search.Bundler import Bundler
from Tribler.Core.CacheDB.sqlitecachedb import forceDBThread
from Tribler.Core.CacheDB.SqliteCacheDBHandler import BundlerPreferenceDBHandler, UserEventLogDBHandler

from __init__ import SEPARATOR_GREY, FILTER_GREY
import sys
import wx
import os
from Tribler.Main.vwxGUI import DEFAULT_BACKGROUND, warnWxThread
from Tribler.Main.Utility.GuiDBTuples import Channel, Playlist
from Tribler.Main.vwxGUI.list_body import FixedListBody
from Tribler.community.channel.community import ChannelCommunity
from Tribler.Main.Utility.GuiDBHandler import startWorker
from Tribler.Main.vwxGUI.list_item import ColumnsManager, TorrentListItem, ChannelListItem, LibraryListItem, ChannelListItemNoButton, PlaylistItemNoButton, PlaylistItem

DEBUG = False


class ListHeaderIcon:
    __single = None

    def __init__(self):
        if ListHeaderIcon.__single:
            raise RuntimeError("ListHeaderIcon is singleton")
        ListHeaderIcon.__single = self
        self.icons = {}

    def getInstance(*args, **kw):
        if ListHeaderIcon.__single is None:
            ListHeaderIcon(*args, **kw)
        return ListHeaderIcon.__single
    getInstance = staticmethod(getInstance)

    @warnWxThread
    def getBitmaps(self, parent, background):
        assert isinstance(background, wx.Colour), "we require a wx.colour object here"
        if not isinstance(background, wx.Colour):
            background = wx.Brush(background).GetColour()

        key = background.Get()
        if key not in self.icons:
            self.icons[key] = self.__createBitmap(parent, background, 'arrow')
        return self.icons[key]

    @warnWxThread
    def __createBitmap(self, parent, background, type, flag=0):
        if DEBUG:
            print >> sys.stderr, "Creating new sorting bitmaps", parent, background, type
        nativeIcon = NativeIcon.getInstance()
        down = nativeIcon.getBitmap(parent, type, background, flag)

        img = down.ConvertToImage()
        up = img.Rotate90().Rotate90().ConvertToBitmap()

        empty = wx.EmptyBitmap(up.GetWidth(), up.GetHeight())
        dc = wx.MemoryDC(empty)
        dc.SetBackground(wx.Brush(background))
        dc.Clear()
        dc.SelectObject(wx.NullBitmap)
        del dc

        return [down, up, empty]


class ListHeader(wx.Panel):

    def __init__(self, parent, parent_list, columns, radius=0, spacers=[3, 3]):
        wx.Panel.__init__(self, parent)
        self.parent_list = parent_list
        self.columnHeaders = []

        self.columns = columns
        self.radius = radius

        self.sortedColumn = -1
        self.defaultSort = -1
        self.sortedDirection = False

        self.scrollBar = None
        self.SetForegroundColour(parent.GetForegroundColour())

        self.AddComponents(columns, spacers)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnResize)

    @warnWxThread
    def AddComponents(self, columns, spacers):
        hSizer = wx.BoxSizer(wx.HORIZONTAL)

        if self.radius + spacers[0] > 0:
            hSizer.AddSpacer((self.radius + spacers[0], 10))

        self.AddColumns(hSizer, self, columns)

        if self.radius + spacers[1] > 0:
            hSizer.AddSpacer((self.radius + spacers[1], 10))

        self.SetSizer(hSizer)

    @warnWxThread
    def AddColumns(self, sizer, parent, columns):
        selectedfont = self.GetFont()
        selectedfont.SetUnderlined(True)

        self.columnHeaders = []

        if len(columns) > 0:
            down, up, empty = ListHeaderIcon.getInstance().getBitmaps(self, self.GetBackgroundColour())
            for i in xrange(len(columns)):
                if columns[i].get('name', '') != '':
                    label = LinkText(parent, columns[i]['name'], fonts=[None, selectedfont], style=columns[i].get('style', 0) | wx.ST_NO_AUTORESIZE, parentsizer=sizer)
                    label.SetToolTipString('Click to sort table by %s.' % columns[i]['name'])
                    label.SetBackgroundColour(self.GetBackgroundColour())
                    label.column = i
                    label.Bind(wx.EVT_LEFT_UP, self.OnClick)

                    if i == 0:
                        sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.BOTTOM, 3)
                    else:
                        sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.TOP | wx.BOTTOM, 3)

                    if columns[i].get('defaultSorted', False):
                        if columns[i].get('sortAsc', False):
                            label.sortIcon = wx.StaticBitmap(self, -1, up)
                        else:
                            label.sortIcon = wx.StaticBitmap(self, -1, down)

                        self.sortedColumn = i
                        self.defaultSort = i
                    else:
                        label.sortIcon = wx.StaticBitmap(self, -1, empty)
                    sizer.Add(label.sortIcon, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 3)

                    if columns[i]['width'] == wx.LIST_AUTOSIZE_USEHEADER:
                        columns[i]['width'] = label.GetBestSize()[0] + down.GetWidth() + 3

                    elif columns[i]['width'] == wx.LIST_AUTOSIZE:
                        sizer.AddStretchSpacer()

                    else:
                        if isinstance(columns[i]['width'], basestring) and columns[i]['width'].endswith('em'):
                            test_string = 'T' * int(columns[i]['width'][:-2])
                            labelWidth = self.GetTextExtent(test_string)[0]
                            columns[i]['width'] = labelWidth + 3 + down.GetWidth()

                        remainingWidth = columns[i]['width'] - label.GetBestSize()[0] - down.GetWidth() - 3
                        if remainingWidth > 0:
                            sizer.AddSpacer((remainingWidth, 1))
                        else:
                            print >> sys.stderr, "LIST_HEADER: specified width is too small", columns[i]['name'], columns[i]['width'], remainingWidth
                            label.SetSize((label.GetBestSize()[0] + remainingWidth, -1))

                    self.columnHeaders.append(label)
                else:
                    spacer = sizer.Add((columns[i]['width'], -1), 0, wx.LEFT, 3)
                    self.columnHeaders.append(spacer)

        self.scrollBar = sizer.AddSpacer((0, 0))
        self.scrollBar.sizer = sizer

    @warnWxThread
    def ResizeColumn(self, column, width):
        changed = False
        item = self.columnHeaders[column]
        if isinstance(item, wx.Window):
            if item.GetSize()[0] != width:
                if getattr(item, 'sortIcon', False):
                    width -= (item.sortIcon.GetSize()[0] + 3)
                item.SetMinSize((width, -1))
                changed = True
        elif item.GetSpacer()[0] != width:
            item.SetSpacer((width, -1))

    @warnWxThread
    def OnClick(self, event):
        newColumn = event.GetEventObject().column

        if newColumn == self.sortedColumn:
            newDirection = not self.sortedDirection

            if newDirection == self.columns[newColumn].get('sortAsc', False):  # back to default, treat as off
                newColumn = -1
        else:
            newDirection = self.columns[newColumn].get('sortAsc', False)

        self.parent_list.OnSort(newColumn, newDirection)
        self._SetSortedIcon(newColumn, newDirection)

    def ShowSortedBy(self, column):
        direction = self.columns[column].get('sortAsc', False)
        self._SetSortedIcon(column, direction)

    @warnWxThread
    def _SetSortedIcon(self, newColumn, newDirection):
        down, up, empty = ListHeaderIcon.getInstance().getBitmaps(self, self.GetBackgroundColour())

        if self.sortedColumn != -1 and newColumn != self.sortedColumn:
            prevSort = self.columnHeaders[self.sortedColumn].sortIcon
            prevSort.SetBitmap(empty)
            prevSort.Refresh()

        if newColumn == -1 and self.defaultSort != -1:
            newColumn = self.defaultSort
            newDirection = self.columns[self.defaultSort].get('sortAsc', False)

        if newColumn != -1:
            newSort = self.columnHeaders[newColumn].sortIcon
            if newDirection:
                newSort.SetBitmap(up)
            else:
                newSort.SetBitmap(down)
            newSort.Refresh()

        self.sortedColumn = newColumn
        self.sortedDirection = newDirection

    def Reset(self):
        if self.defaultSort != -1:
            defaultDirection = self.columns[self.defaultSort].get('sortAsc', False)
        else:
            defaultDirection = False
        self._SetSortedIcon(self.defaultSort, defaultDirection)

    @warnWxThread
    def SetBackgroundColour(self, colour):
        self.backgroundBrush = wx.Brush(colour)
        colour = self.backgroundBrush.GetColour()

        down, up, empty = ListHeaderIcon.getInstance().getBitmaps(self, colour)
        for i in range(len(self.columnHeaders)):
            if getattr(self.columnHeaders[i], 'sortIcon', False):
                bitmap = self.columnHeaders[i].sortIcon

                if i == self.sortedColumn:
                    if self.sortedDirection:
                        bitmap.SetBitmap(up)
                    else:
                        bitmap.SetBitmap(down)
                else:
                    bitmap.SetBitmap(empty)
                bitmap.Refresh()

            if getattr(self.columnHeaders[i], 'SetBackgroundColour', False):
                self.columnHeaders[i].SetBackgroundColour(colour)
        return wx.Panel.SetBackgroundColour(self, colour)

    @warnWxThread
    def OnPaint(self, event):
        obj = event.GetEventObject()
        dc = wx.BufferedPaintDC(obj)
        dc.Clear()

        w, h = self.GetClientSize()
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(self.backgroundBrush)

        if self.radius > 0:
            dc.DrawRoundedRectangle(0, 0, w, 2 * self.radius, self.radius)
        dc.DrawRectangle(0, self.radius, w, h - self.radius)

    @warnWxThread
    def OnResize(self, event):
        self.Refresh()
        event.Skip()


class TitleHeader(ListHeader):

    def __init__(self, parent, parent_list, columns, font_increment=2, fontweight=wx.FONTWEIGHT_BOLD, radius=0, spacers=[3, 3]):
        self.font_increment = font_increment
        self.fontweight = fontweight

        ListHeader.__init__(self, parent, parent_list, columns, radius=radius, spacers=spacers)

    @warnWxThread
    def AddComponents(self, columns, spacers):
        vSizer = wx.BoxSizer(wx.VERTICAL)

        vSizer.AddSpacer((-1, 3))

        self.title = StaticText(self)
        _set_font(self.title, self.font_increment, self.fontweight)

        titlePanel = self.GetTitlePanel(self)
        subtitlePanel = self.GetSubTitlePanel(self)
        righttitlePanel = self.GetRightTitlePanel(self)
        belowPanel = self.GetBelowPanel(self)

        if titlePanel:
            subSizer = wx.BoxSizer(wx.HORIZONTAL)
            subSizer.Add(self.title)
            subSizer.Add(titlePanel, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL, 3)
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

        subSizer = wx.BoxSizer(wx.HORIZONTAL)
        subSizer.Add(subtitlePanel)
        if righttitlePanel:
            subSizer.Add(righttitlePanel, 1, wx.LEFT, 3)
        righttitlePanel = subSizer

        vSizer.Add(righttitlePanel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, self.radius + spacers[0])
        if belowPanel:
            vSizer.Add(belowPanel, 1, wx.EXPAND | wx.TOP, 3)

        vSizer.AddSpacer((-1, 3))

        if len(columns) > 0:
            hSizer = wx.BoxSizer(wx.HORIZONTAL)
            self.AddColumns(hSizer, self, columns)
            vSizer.Add(hSizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, self.radius + spacers[0])
        self.SetSizer(vSizer)

    def GetTitlePanel(self, parent):
        pass

    def GetSubTitlePanel(self, parent):
        pass

    def GetRightTitlePanel(self, parent):
        pass

    def GetBelowPanel(self, parent):
        pass

    @warnWxThread
    def SetTitle(self, title):
        if title != self.title.GetLabel():
            self.Freeze()

            self.title.SetLabel(title)
            self.title.Refresh()
            self.Layout()
            self.Thaw()

    @warnWxThread
    def SetToolTip(self, tooltip):
        self.title.SetToolTipString(tooltip)


class SearchHeaderHelper():

    @warnWxThread
    def GetTitlePanel(self, parent):
        self.afterFilter = wx.StaticText(parent)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.afterFilter)
        return hSizer

    @warnWxThread
    def SetSubTitle(self, label):
        if label != '':
            label = '( %s )' % label

        if getattr(self, 'subtitle', '') != label:
            self.afterFilter.SetLabel(label)
            self.subtitle = label

    @warnWxThread
    def GetRightTitlePanel(self, parent):
        self.filter = wx.SearchCtrl(parent)
        self.filter.SetDescriptiveText('Filter results')
        self.filter.Bind(wx.EVT_TEXT, self.OnKey)
        self.filter.SetMinSize((175, -1))

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.AddStretchSpacer()
        hSizer.Add(self.filter, 0, wx.ALIGN_CENTER_VERTICAL)
        return hSizer

    def FilterCorrect(self, regex_correct):
        pass

    @warnWxThread
    def OnKey(self, event):
        self.parent_list.GotFilter(self.filter.GetValue().strip())

    @warnWxThread
    def SetFiltered(self, nr):
        if nr:
            self.afterFilter.SetLabel('( Discovered %d after filter )' % nr)
        else:
            self.afterFilter.SetLabel(getattr(self, 'subtitle', ''))

    @warnWxThread
    def Reset(self):
        self.SetSubTitle('')
        self.filter.Clear()


class SubTitleHeader(TitleHeader):

    @warnWxThread
    def GetSubTitlePanel(self, parent):
        self.subtitle = StaticText(parent)
        return self.subtitle

    @warnWxThread
    def SetSubTitle(self, subtitle):
        if subtitle != self.subtitle.GetLabel():
            self.Freeze()

            self.subtitle.SetLabel(subtitle)
            self.subtitle.Refresh()

            self.Thaw()


class ManageChannelHeader(SubTitleHeader):

    def __init__(self, parent, parent_list):
        TitleHeader.__init__(self, parent, parent_list, [])
        self.nr_favorites = None

    @warnWxThread
    def SetName(self, name):
        self.SetTitle(name)

    @warnWxThread
    def SetNrTorrents(self, nr, nr_favorites=None):
        subtitle = ''
        if nr == 1:
            subtitle = 'Sharing %d torrent' % nr
        else:
            subtitle = 'Sharing %d torrents' % nr

        if nr_favorites:
            self.nr_favorites = nr_favorites
        else:
            nr_favorites = self.nr_favorites

        if nr > 0 and nr_favorites:
            if nr_favorites == 0:
                subtitle += ', but not marked as a favorite yet.'
            elif nr_favorites == 1:
                subtitle += ' and 1 Tribler user marked it as one of its favorites.'
            else:
                subtitle += ' and ' + str(nr_favorites) + ' Tribler users marked it as one of their favorites.'
        self.SetSubTitle(subtitle)

    def AddColumns(self, sizer, parent, columns):
        SubTitleHeader.AddColumns(self, sizer, parent, [])

    def Reset(self):
        SubTitleHeader.Reset(self)
        self.nr_favorites = None


class SearchHelpHeader(SearchHeaderHelper, TitleHeader):

    @warnWxThread
    def GetRightTitlePanel(self, parent):
        hSizer = SearchHeaderHelper.GetRightTitlePanel(self, parent)

        # filename = os.path.join(os.path.dirname(__file__), "images", "help.png")
        gui_utility = GUIUtility.getInstance()
        filename = os.path.join(gui_utility.vwxGUI_path, "images", "help.png")
        help = wx.StaticBitmap(parent, -1, wx.Bitmap(filename, wx.BITMAP_TYPE_ANY))
        help.Bind(wx.EVT_LEFT_UP, self.helpClick)
        help.SetCursor(wx.StockCursor(wx.CURSOR_HAND))

        hSizer.Add(help, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)

        return hSizer

    def GetSubTitlePanel(self, parent):
        pass

    @warnWxThread
    def helpClick(self, event=None):
        title = 'Search within results'
        html = """<p>
        <u>Search within results</u> allows you to filter a list with ease.<br>
        Typing a simple string, will allow you to filter items. <br>
        If you type 'ab', only items matching it will be shown:
        <ul>
            <li><b>AB</b>C</li>
            <li><b>ab</b>c</li>
            <li>d<b>ab</b>c</li>
        </ul>
        <hr>
        But you can specify more advanced queries. Search within results will additionally allow you to use regex and size filters.
        I.e.
        <ul>
            <li>'\d{4}' will show only items with a 4 digit number</li>
            <li>'size=100:200' will show items between 100 and 200 Mbytes</li>
            <li>'size=:200' will show items smaller than 200 Mbytes</li>
            <li>'size=100:' will show items larger than 100 Mbytes</li>
        </ul>
        <hr>
        Finally if you are in the Library you can filter items by state, i.e.
        <ul>
            <li>'state=completed' will show only items which are completed</li>
            <li>'state=active' will show items which currently are being downloaded or seeded</li>
            <li>'state=seeding' will show items which are seeding</li>
            <li>'state=downloading' will show items which are downloading</li>
            <li>'state=stopped' will show items which are stopped/paused and not completed</li>
            <li>'state=checking' will show items which are currently checking or scheduled to be checked</li>
        </ul>
        </p>"""

        dlg = wx.Dialog(GUIUtility.getInstance().frame, -1, title, style=wx.DEFAULT_DIALOG_STYLE, size=(500, 300))
        dlg.CenterOnParent()
        dlg.SetBackgroundColour(DEFAULT_BACKGROUND)

        sizer = wx.FlexGridSizer(2, 2)

        icon = wx.StaticBitmap(dlg, -1, wx.ArtProvider.GetBitmap(wx.ART_INFORMATION, wx.ART_MESSAGE_BOX))
        sizer.Add(icon, 0, wx.TOP, 10)

        hwin = wx.html.HtmlWindow(dlg, -1, size=(600, 400))
        hwin.SetPage(html)
        sizer.Add(hwin)

        sizer.Add((10, 0))

        btn = wx.Button(dlg, wx.ID_OK, 'Ok')
        sizer.Add(btn, 0, wx.ALIGN_RIGHT, 5)

        border = wx.BoxSizer()
        border.Add(sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        dlg.SetSizerAndFit(border)
        dlg.ShowModal()
        dlg.Destroy()

    @warnWxThread
    def Reset(self):
        SearchHeaderHelper.Reset(self)
        self.filter.Clear()


class BaseFilter(wx.Panel):

    def __init__(self, parent, parent_list, columns, spacers):
        wx.Panel.__init__(self, parent)

        self.spacers = spacers
        self.parent_list = parent_list
        self.columns = columns

        self.SetBackgroundColour(FILTER_GREY)
        self.SetForegroundColour(parent.GetForegroundColour())
        self.AddComponents(spacers)

    @warnWxThread
    def AddComponents(self, spacers):
        vSizer = wx.BoxSizer(wx.VERTICAL)

        self.filter_panel = self.GetFilterPanel(self)
        if self.filter_panel:
            vSizer.Add(self.filter_panel, 0, wx.EXPAND)
            self.filter_separator = wx.Panel(self, size=(-1, 1))
            self.filter_separator.SetBackgroundColour(SEPARATOR_GREY)
            vSizer.Add(self.filter_separator, 0, wx.EXPAND)

        self.SetSizer(vSizer)

    @warnWxThread
    def GetFilterPanel(self, parent):
        panel = wx.Panel(parent)
        panel.SetMinSize((-1, 25))
        panel.SetBackgroundColour(self.GetBackgroundColour())
        return panel

    def SetTitle(self, title):
        pass

    def SetSubTitle(self, subtitle):
        pass

    def SetStyle(self, style):
        pass

    def ShowSortedBy(self, sortedby):
        pass

    def SetAssociatedChannels(self, channels):
        pass

    def FilterCorrect(self, regex_correct):
        pass


class TorrentFilter(BaseFilter):

    def __init__(self, parent, parent_list, spacers=[10, 3], show_bundle=False):
        self.guiutility = GUIUtility.getInstance()
        self.torrentsearch_manager = self.guiutility.torrentsearch_manager

        self.bundlestates = [Bundler.ALG_MAGIC, Bundler.ALG_NAME, Bundler.ALG_NUMBERS, Bundler.ALG_SIZE, Bundler.ALG_OFF]
        self.bundlestates_str = {Bundler.ALG_NAME: 'Name',
                                 Bundler.ALG_NUMBERS: 'Numbers',
                                 Bundler.ALG_SIZE: 'Size',
                                 Bundler.ALG_MAGIC: 'Magic',
                                 Bundler.ALG_OFF: 'Off'}
        self.bundletexts = []
        self.bundle_db = BundlerPreferenceDBHandler.getInstance()
        self.uelog = UserEventLogDBHandler.getInstance()

        self.slider_minmax = (0, 0)
        self.slider_positions = (0, 0)
        self.conversion_factor = 1048576.0
        self.show_bundle = show_bundle
        self.SetBundleState(None)

        BaseFilter.__init__(self, parent, parent_list, ColumnsManager.getInstance().getColumns(TorrentListItem), spacers)

    @warnWxThread
    def GetFilterPanel(self, parent):
        panel = wx.Panel(parent)
        panel.SetMinSize((-1, 25))
        panel.SetBackgroundColour(self.GetBackgroundColour())
        panel.SetForegroundColour(self.GetForegroundColour())

        self.icon_down = NativeIcon.getInstance().getBitmap(self, 'arrow', self.GetBackgroundColour(), state=0)
        self.icon_right = self.icon_down.ConvertToImage().Rotate90(False).ConvertToBitmap()

        self.sortby_icon = wx.StaticBitmap(panel, -1, self.icon_right)
        self.sortby = LinkStaticText(panel, 'Sort by', None, font_colour=wx.BLACK)
        self.sortby.Bind(wx.EVT_LEFT_UP, self.OnPopupSort)

        if self.show_bundle:
            self.bundleby_icon = wx.StaticBitmap(panel, -1, self.icon_right)
            self.bundleby = LinkStaticText(panel, 'Bundle by', None, font_colour=wx.BLACK)
            self.bundleby.Bind(wx.EVT_LEFT_UP, self.OnPopupBundle)

        self.filetype_icon = wx.StaticBitmap(panel, -1, self.icon_right)
        self.filetype = LinkStaticText(panel, 'File type', None, font_colour=wx.BLACK)
        self.filetype.Bind(wx.EVT_LEFT_UP, self.OnPopupFileType)

        self.filesize_str = StaticText(panel, -1, 'File size:')
        self.filesize = MinMaxSlider(panel, -1)
        self.filesize.SetFormatter(self.guiutility.utility.size_format)

        self.search = wx.SearchCtrl(panel)
        self.search.SetDescriptiveText('Filter results')
        self.search.Bind(wx.EVT_TEXT, self.OnKey)
        if sys.platform == 'darwin':
            self.search.SetMinSize((175, 20))
        else:
            self.search.SetMinSize((175, -1))

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.AddSpacer((self.spacers[0], -1))
        hSizer.Add(self.sortby_icon, 0, wx.CENTER | wx.RIGHT, 3)
        hSizer.Add(self.sortby, 0, wx.CENTER)
        hSizer.AddSpacer((45, -1))
        if self.show_bundle:
            hSizer.Add(self.bundleby_icon, 0, wx.CENTER | wx.RIGHT, 3)
            hSizer.Add(self.bundleby, 0, wx.CENTER)
            hSizer.AddSpacer((45, -1))
        hSizer.Add(self.filetype_icon, 0, wx.CENTER | wx.RIGHT, 3)
        hSizer.Add(self.filetype, 0, wx.CENTER)
        hSizer.AddSpacer((45, -1))
        hSizer.Add(self.filesize_str, 0, wx.CENTER | wx.RIGHT, 10)
        hSizer.Add(self.filesize, 0, wx.CENTER)
        hSizer.AddStretchSpacer()
        hSizer.Add(self.search, 0, wx.CENTER)
        hSizer.AddSpacer((self.spacers[1], -1))
        self.filter_sizer = hSizer

        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(hSizer, 1, wx.EXPAND)
        panel.SetSizer(vSizer)
        return panel

    def OnPopupSort(self, event):
        sortcolumn = self.parent_list.list.sortcolumn if self.parent_list.list.sortcolumn != None else -1
        sortreverse = getattr(self.parent_list.list, 'sortreverse', False)

        menu = wx.Menu()
        itemid = wx.NewId()
        menu.AppendRadioItem(itemid, "Relevance")
        menu.Bind(wx.EVT_MENU, lambda x: self.parent_list.OnSort(-1, False), id=itemid)
        menu.Check(itemid, sortcolumn == -1)
        for index, column in enumerate(self.columns):
            if column.get('show', True):
                sortAsc = column.get('sortAsc', False)
                itemid = wx.NewId()
                menu.AppendRadioItem(itemid, column['name'])
                menu.Bind(wx.EVT_MENU, lambda x, index=index, sortAsc=sortAsc: self.parent_list.OnSort(index, sortAsc), id=itemid)
                menu.Check(itemid, sortcolumn == index)

        if len(self.columns) > 0:
            menu.AppendSeparator()
            itemid = wx.NewId()
            menu.AppendRadioItem(itemid, "Ascending").Enable(sortcolumn != -1)
            menu.Bind(wx.EVT_MENU, lambda x, col=sortcolumn: self.parent_list.OnSort(col, True), id=itemid)
            menu.Check(itemid, (sortcolumn >= 0 and sortreverse))
            itemid = wx.NewId()
            menu.AppendRadioItem(itemid, "Descending")
            menu.Bind(wx.EVT_MENU, lambda x, col=sortcolumn: self.parent_list.OnSort(col, False), id=itemid)
            menu.Check(itemid, (sortcolumn == -1) or (not sortreverse))

        ctrl = self.sortby_icon
        pos = wx.Point(ctrl.GetPosition().x, self.filter_panel.GetPosition().y + self.filter_panel.GetSize().y)
        self.PopupMenu(menu, pos)
        menu.Destroy()
        self.Layout()

    def OnPopupBundle(self, event):
        menu = wx.Menu()
        for state, state_str in self.bundlestates_str.iteritems():
            itemid = wx.NewId()
            menu.AppendRadioItem(itemid, state_str)
            menu.Bind(wx.EVT_MENU, lambda x, state=state: self.Rebundle(state), id=itemid)
            menu.Check(itemid, self.bundlestate == state)

        ctrl = self.bundleby_icon
        pos = wx.Point(ctrl.GetPosition().x, self.GetPosition().y + self.filter_panel.GetSize().y)
        self.PopupMenu(menu, pos)
        menu.Destroy()
        self.Layout()

    def OnPopupFileType(self, event):
        menu = wx.Menu()
        itemid = wx.NewId()
        menu.AppendRadioItem(itemid, "All")
        menu.Bind(wx.EVT_MENU, lambda x: self.CategoryFilter(''), id=itemid)
        menu.Check(itemid, not self.parent_list.categoryfilter)
        for _, filetype in Category.getInstance().getCategoryNames():
            if filetype != 'XXX':
                itemid = wx.NewId()
                menu.AppendRadioItem(itemid, filetype)
                menu.Bind(wx.EVT_MENU, lambda x, filetype=filetype: self.CategoryFilter(filetype), id=itemid)
                menu.Check(itemid, bool(self.parent_list.categoryfilter) and (filetype.lower() in self.parent_list.categoryfilter))

        ctrl = self.filetype_icon
        pos = wx.Point(ctrl.GetPosition().x, self.GetPosition().y + self.filter_panel.GetSize().y)
        self.PopupMenu(menu, pos)
        menu.Destroy()
        self.Layout()

    @warnWxThread
    def OnSlider(self, min_val, max_val):
        search = self.search.GetValue().strip()
        # Remove old filter
        if search.find("size=") > -1:
            try:
                start = search.find("size=") + 5
                end = search.find(" ", start)
                if end == -1:
                    end = len(search)
                search = search[:start - 5] + search[end:]
                search = search.strip()
            except:
                pass
        # Insert new filter
        if min_val <= max_val:
            if search:
                search += " "
            search += "size=%d:%d" % (min_val / self.conversion_factor, max_val / self.conversion_factor)
        self.search.SetValue(search)

    @warnWxThread
    def OnKey(self, event=None):
        search = self.search.GetValue().strip()
        self.parent_list.GotFilter(search)
        if event and search.find("size=") > -1:
            try:
                start = search.find("size=") + 5
                end = search.find(" ", start)
                if end == -1:
                    end = len(search)

                sizeStr = search[start:end]
                if sizeStr.find(":") > -1:
                    sizes = sizeStr.split(":")
                    if sizes[0] != '':
                        min_val = int(sizes[0])
                    if sizes[1] != '':
                        max_val = int(sizes[1])
                else:
                    min_val = max_val = int(sizeStr)
                self.slider_positions = (min_val * self.conversion_factor, max_val * self.conversion_factor)
                self.filesize.SetCurrentValues(*self.slider_positions)
            except:
                pass

    @warnWxThread
    def CategoryFilter(self, category):
        search = self.search.GetValue().strip()
        # Remove old filter
        if search.find("category=") > -1:
            try:
                start = search.find("category='") + 10
                end = search.find("'", start)
                if start != -1 and end != -1:
                    search = search[:start - 10] + search[end + 1:]
                    search = search.strip()
            except:
                pass
        # Insert new filter
        if category:
            if search:
                search += " "
            search += "category='%s'" % category
        self.search.SetValue(search)

    @warnWxThread
    def Reset(self):
        self.search.Clear()
        self.filesize.Reset()
        self.slider_minmax = (0, 0)
        self.slider_positions = (0, 0)

    def GetSliderMinMax(self):
        return self.slider_minmax

    @warnWxThread
    def SetSliderMinMax(self, length_min, length_max):
        if self.slider_minmax != (length_min, length_max):
            self.slider_minmax = (length_min, length_max)
            self.filesize.SetMinMax(length_min, length_max)
            min_val = max(self.slider_positions[0], length_min)
            max_val = min(self.slider_positions[1], length_max)
            self.filesize.SetCurrentValues(min_val, max_val)

    def Rebundle(self, newstate):
        curstate = self.bundlestate
        selectedByMagic = self.selected_bundle_mode if self.bundlestate == Bundler.ALG_MAGIC else -1

        def db_callback():
            self.SetBundleState(newstate)

            keywords = self.torrentsearch_manager.getSearchKeywords()[0]
            self.bundle_db.storePreference(keywords, newstate)
            query = ' '.join(keywords)

            selectedByMagicStr = ''
            if selectedByMagic != -1:
                selectedByMagicStr = self.bundlestates_str[selectedByMagic]

            self.uelog.addEvent(message="Bundler GUI: %s -> %s; %s -> %s; selectedByMagic %s (%s); q=%s"
                                % (curstate, newstate, self.bundlestates_str[curstate],
                                   self.bundlestates_str[newstate],
                                   selectedByMagic, selectedByMagicStr, query), type=3)

        startWorker(None, db_callback)

    @forceDBThread
    def SetBundleState(self, newstate, refresh=True):
        if newstate is None:
            auto_guess = self.guiutility.utility.read_config('use_bundle_magic')

            newstate = Bundler.ALG_OFF  # default
            keywords = self.torrentsearch_manager.getSearchKeywords()[0]
            if keywords != '':
                try:
                    stored_state = self.bundle_db.getPreference(keywords)
                except:
                    # if db interaction fails, ignore
                    stored_state = None

                local_override = stored_state is not None

                if local_override:
                    newstate = stored_state

                elif auto_guess:
                    newstate = Bundler.ALG_MAGIC

        self.bundlestate = newstate
        self.selected_bundle_mode = None

        self.torrentsearch_manager.setBundleMode(newstate, refresh)

    def SetSelectedBundleMode(self, selected_bundle_mode):
        if self.bundlestate == Bundler.ALG_MAGIC:
            self.selected_bundle_mode = selected_bundle_mode

    @warnWxThread
    def AddButton(self, btn_label, btn_handler):
        num_children = len(self.filter_sizer.GetChildren())
        if num_children < 2:
            return
        child = self.filter_sizer.GetItem(num_children - 3)
        child = child.GetWindow() if getattr(child, 'IsWindow', False) and child.IsWindow() else child
        if not isinstance(child, wx.Button):
            if btn_handler:
                btn = wx.Button(self.filter_panel, -1, btn_label)
                btn.Bind(wx.EVT_BUTTON, btn_handler)
                btn.SetMinSize((-1, 23))
                self.filter_sizer.Insert(num_children - 2, btn, 0, wx.CENTER | wx.RIGHT, 3)
                self.filter_sizer.Layout()
                self.Layout()
        else:
            btn = child
            if btn_handler:
                btn.SetLabel(btn_label)
                btn.Bind(wx.EVT_BUTTON, btn_handler)
            else:
                self.filter_sizer.Remove(btn)
                btn.Destroy()
                self.filter_sizer.Layout()


class SelectedChannelFilter(TorrentFilter):

    def __init__(self, *args, **kwargs):
        TorrentFilter.__init__(self, *args, **kwargs)
        self.columns = self.columns[:]
        for column in self.columns:
            if column['name'] == 'From':
                self.columns.remove(column)
                break

    @warnWxThread
    def AddComponents(self, spacers):
        self.SetBackgroundColour(wx.WHITE)
        TorrentFilter.AddComponents(self, spacers)
        self.search.SetDescriptiveText('Filter channel content')


class SelectedPlaylistFilter(TorrentFilter):

    @warnWxThread
    def AddComponents(self, spacers):
        TorrentFilter.AddComponents(self, spacers)
        self.search.SetDescriptiveText('Filter playlist content')


class ChannelFilter(BaseFilter):

    def __init__(self, parent, parent_list, spacers=[10, 3]):
        self.guiutility = GUIUtility.getInstance()
        self.channellist_manager = parent_list.GetManager()
        self.channel_categories = ["All", "Popular", "New", "Updated", "Mine"]

        BaseFilter.__init__(self, parent, parent_list, ColumnsManager.getInstance().getColumns(ChannelListItem), spacers)

    @warnWxThread
    def GetFilterPanel(self, parent):
        panel = wx.Panel(parent)
        panel.SetMinSize((-1, 25))
        panel.SetBackgroundColour(self.GetBackgroundColour())
        panel.SetForegroundColour(self.GetForegroundColour())

        self.icon_down = NativeIcon.getInstance().getBitmap(self, 'arrow', self.GetBackgroundColour(), state=0)
        self.icon_right = self.icon_down.ConvertToImage().Rotate90(False).ConvertToBitmap()

        self.sortby_icon = wx.StaticBitmap(panel, -1, self.icon_right)
        self.sortby = LinkStaticText(panel, 'Sort by', None, font_colour=wx.BLACK)
        self.sortby.Bind(wx.EVT_LEFT_UP, self.OnPopupSort)

        self.channeltype_icon = wx.StaticBitmap(panel, -1, self.icon_right)
        self.channeltype = LinkStaticText(panel, 'Channel type', None, font_colour=wx.BLACK)
        self.channeltype.Bind(wx.EVT_LEFT_UP, self.OnPopupChannelType)

        self.search = wx.SearchCtrl(panel)
        self.search.SetDescriptiveText('Filter channels')
        self.search.Bind(wx.EVT_TEXT, self.OnKey)
        if sys.platform == 'darwin':
            self.search.SetMinSize((175, 20))
        else:
            self.search.SetMinSize((175, -1))

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.AddSpacer((self.spacers[0], -1))
        hSizer.Add(self.sortby_icon, 0, wx.CENTER | wx.RIGHT, 3)
        hSizer.Add(self.sortby, 0, wx.CENTER)
        hSizer.AddSpacer((45, -1))
        hSizer.Add(self.channeltype_icon, 0, wx.CENTER | wx.RIGHT, 3)
        hSizer.Add(self.channeltype, 0, wx.CENTER)
        hSizer.AddStretchSpacer()
        hSizer.Add(self.search, 0, wx.CENTER)
        hSizer.AddSpacer((self.spacers[1], -1))
        self.filter_sizer = hSizer

        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(hSizer, 1, wx.EXPAND)
        panel.SetSizer(vSizer)
        return panel

    def OnPopupSort(self, event):
        sortcolumn = self.parent_list.list.sortcolumn if self.parent_list.list.sortcolumn != None else -1
        sortreverse = getattr(self.parent_list.list, 'sortreverse', False)

        menu = wx.Menu()
        for index, column in enumerate(self.columns):
            if column.get('show', True):
                sortAsc = column.get('sortAsc', False)
                sortDef = column.get('defaultSorted', False)
                sortcolumn = index if (sortcolumn == -1 and sortDef) else sortcolumn
                itemid = wx.NewId()
                menu.AppendRadioItem(itemid, column['name'])
                menu.Bind(wx.EVT_MENU, lambda x, index=index, sortAsc=sortAsc: self.parent_list.OnSort(index, sortAsc), id=itemid)
                menu.Check(itemid, sortcolumn == index)

        if len(self.columns) > 0:
            menu.AppendSeparator()
            itemid = wx.NewId()
            menu.AppendRadioItem(itemid, "Ascending")
            menu.Bind(wx.EVT_MENU, lambda x, col=sortcolumn: self.parent_list.OnSort(col, True), id=itemid)
            menu.Check(itemid, sortreverse)
            itemid = wx.NewId()
            menu.AppendRadioItem(itemid, "Descending")
            menu.Bind(wx.EVT_MENU, lambda x, col=sortcolumn: self.parent_list.OnSort(col, False), id=itemid)
            menu.Check(itemid, not sortreverse)

        ctrl = self.sortby_icon
        pos = wx.Point(ctrl.GetPosition().x, self.filter_panel.GetPosition().y + self.filter_panel.GetSize().y)
        self.PopupMenu(menu, pos)
        menu.Destroy()
        self.Layout()

    def OnPopupChannelType(self, event):
        current_cat = self.GetChannelCategory()

        menu = wx.Menu()
        for cat in self.channel_categories:
            itemid = wx.NewId()
            menu.AppendRadioItem(itemid, cat)
            menu.Bind(wx.EVT_MENU, lambda x, cat=cat: self.SetChannelCategory(cat), id=itemid)
            menu.Check(itemid, current_cat == cat)

        ctrl = self.channeltype_icon
        pos = wx.Point(ctrl.GetPosition().x, self.filter_panel.GetPosition().y + self.filter_panel.GetSize().y)
        self.PopupMenu(menu, pos)
        menu.Destroy()
        self.Layout()

    @warnWxThread
    def OnKey(self, event=None):
        search = self.search.GetValue().strip()
        self.parent_list.GotFilter(search)

    def GetChannelCategory(self):
        if self.channellist_manager.category:
            return self.channellist_manager.category
        else:
            return "All"

    def SetChannelCategory(self, cat):
        if cat in self.channel_categories:
            self.guiutility.showChannelCategory(cat)

    def ShowChannelTypeFilter(self, show):
        self.channeltype_icon.Show(show)
        self.channeltype.Show(show)

    @warnWxThread
    def Reset(self):
        self.search.Clear()

    @warnWxThread
    def AddButton(self, btn_label, btn_handler):
        num_children = len(self.filter_sizer.GetChildren())
        if num_children < 2:
            return
        child = self.filter_sizer.GetItem(num_children - 3)
        child = child.GetWindow() if getattr(child, 'IsWindow', False) and child.IsWindow() else child
        if not isinstance(child, wx.Button):
            if btn_handler:
                btn = wx.Button(self.filter_panel, -1, btn_label)
                btn.Bind(wx.EVT_BUTTON, btn_handler)
                btn.SetMinSize((-1, 23))
                self.filter_sizer.Insert(num_children - 2, btn, 0, wx.CENTER | wx.RIGHT, 3)
                self.filter_sizer.Layout()
                self.Layout()
        else:
            btn = child
            if btn_handler:
                btn.SetLabel(btn_label)
                btn.Bind(wx.EVT_BUTTON, btn_handler)
            else:
                self.filter_sizer.Remove(btn)
                btn.Destroy()
                self.filter_sizer.Layout()


class DownloadFilter(BaseFilter):

    def __init__(self, parent, parent_list, spacers=[10, 3]):
        self.guiutility = GUIUtility.getInstance()
        self.slider_minmax = (0, 0)
        self.slider_positions = (0, 0)
        self.conversion_factor = 1048576.0

        BaseFilter.__init__(self, parent, parent_list, ColumnsManager.getInstance().getColumns(LibraryListItem), spacers)

    @warnWxThread
    def GetFilterPanel(self, parent):
        panel = wx.Panel(parent)
        panel.SetMinSize((-1, 25))
        panel.SetBackgroundColour(self.GetBackgroundColour())

        self.icon_down = NativeIcon.getInstance().getBitmap(self, 'arrow', self.GetBackgroundColour(), state=0)
        self.icon_right = self.icon_down.ConvertToImage().Rotate90(False).ConvertToBitmap()

        self.sortby_icon = wx.StaticBitmap(panel, -1, self.icon_right)
        self.sortby = LinkStaticText(panel, 'Sort by', None, font_colour=wx.BLACK)
        self.sortby.Bind(wx.EVT_LEFT_UP, self.OnPopupSort)

        self.filesize_str = StaticText(panel, -1, 'File size:')
        self.filesize = MinMaxSlider(panel, -1)
        self.filesize.SetFormatter(self.guiutility.utility.size_format)

        self.state_icon = wx.StaticBitmap(panel, -1, self.icon_right)
        self.state = LinkStaticText(panel, 'Download state', None, font_colour=wx.BLACK)
        self.state.Bind(wx.EVT_LEFT_UP, self.OnPopupState)

        self.search = wx.SearchCtrl(panel)
        self.search.SetDescriptiveText('Filter downloads')
        self.search.Bind(wx.EVT_TEXT, self.OnKey)
        if sys.platform == 'darwin':
            self.search.SetMinSize((175, 20))
        else:
            self.search.SetMinSize((175, -1))

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.AddSpacer((self.spacers[0], -1))
        hSizer.Add(self.sortby_icon, 0, wx.CENTER | wx.RIGHT, 3)
        hSizer.Add(self.sortby, 0, wx.CENTER)
        hSizer.AddSpacer((45, -1))
        hSizer.Add(self.state_icon, 0, wx.CENTER | wx.RIGHT, 3)
        hSizer.Add(self.state, 0, wx.CENTER)
        hSizer.AddSpacer((45, -1))
        hSizer.Add(self.filesize_str, 0, wx.CENTER | wx.RIGHT, 10)
        hSizer.Add(self.filesize, 0, wx.CENTER)
        hSizer.AddStretchSpacer()
        hSizer.Add(self.search, 0, wx.CENTER)
        hSizer.AddSpacer((self.spacers[1], -1))
        self.filter_sizer = hSizer

        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(hSizer, 1, wx.EXPAND)
        panel.SetSizer(vSizer)
        return panel

    def OnPopupState(self, event):
        currentState = self.parent_list.statefilter if self.parent_list.statefilter != None else ''

        menu = wx.Menu()
        for state in ['All', 'Completed', 'Active', 'Seeding', 'Downloading', 'Stopped', 'Checking']:
            itemid = wx.NewId()
            menu.AppendRadioItem(itemid, state)
            menu.Bind(wx.EVT_MENU, lambda x, state=state: self.OnState(state), id=itemid)
            if state == 'All':
                enabled = bool(currentState)
            else:
                enabled = state.lower() == currentState.lower()
            menu.Check(itemid, enabled)

        ctrl = self.state_icon
        pos = wx.Point(ctrl.GetPosition().x, self.filter_panel.GetPosition().y + self.filter_panel.GetSize().y)
        self.PopupMenu(menu, pos)
        menu.Destroy()
        self.Layout()

    def OnPopupSort(self, event):
        sortcolumn = self.parent_list.list.sortcolumn if self.parent_list.list.sortcolumn != None else -1
        sortreverse = getattr(self.parent_list.list, 'sortreverse', False)

        menu = wx.Menu()
        for index, column in enumerate(self.columns):
            if column.get('show', True):
                sortAsc = column.get('sortAsc', False)
                sortDef = column.get('defaultSorted', False)
                sortcolumn = index if (sortcolumn == -1 and sortDef) else sortcolumn
                itemid = wx.NewId()
                menu.AppendRadioItem(itemid, column['name'] if column['name'] else 'Progress')
                menu.Bind(wx.EVT_MENU, lambda x, index=index, sortAsc=sortAsc: self.parent_list.OnSort(index, sortAsc), id=itemid)
                menu.Check(itemid, sortcolumn == index)

        if len(self.columns) > 0:
            menu.AppendSeparator()
            itemid = wx.NewId()
            menu.AppendRadioItem(itemid, "Ascending")
            menu.Bind(wx.EVT_MENU, lambda x, col=sortcolumn: self.parent_list.OnSort(col, True), id=itemid)
            menu.Check(itemid, sortreverse)
            itemid = wx.NewId()
            menu.AppendRadioItem(itemid, "Descending")
            menu.Bind(wx.EVT_MENU, lambda x, col=sortcolumn: self.parent_list.OnSort(col, False), id=itemid)
            menu.Check(itemid, not sortreverse)

        ctrl = self.sortby_icon
        pos = wx.Point(ctrl.GetPosition().x, self.filter_panel.GetPosition().y + self.filter_panel.GetSize().y)
        self.PopupMenu(menu, pos)
        menu.Destroy()
        self.Layout()

    @warnWxThread
    def OnSlider(self, min_val, max_val):
        search = self.search.GetValue().strip()
        # Remove old filter
        if search.find("size=") > -1:
            try:
                start = search.find("size=") + 5
                end = search.find(" ", start)
                if end == -1:
                    end = len(search)
                search = search[:start - 5] + search[end:]
                search = search.strip()
            except:
                pass
        # Insert new filter
        if min_val <= max_val:
            if search:
                search += " "
            search += "size=%d:%d" % (min_val / self.conversion_factor, max_val / self.conversion_factor)
        self.search.SetValue(search)

    @warnWxThread
    def OnState(self, state):
        search = self.search.GetValue().strip()
        # Remove old filter
        if search.find("state=") > -1:
            try:
                start = search.find("state=") + 6
                end = search.find(" ", start)
                if end == -1:
                    end = len(search)
                search = search[:start - 6] + search[end:]
                search = search.strip()
            except:
                pass
        # Insert new filter
        if state and state != 'All':
            if search:
                search += " "
            search += "state=%s" % state
        self.search.SetValue(search)

    @warnWxThread
    def OnKey(self, event=None):
        search = self.search.GetValue().strip()
        self.parent_list.GotFilter(search)
        if event and search.find("size=") > -1:
            try:
                start = search.find("size=") + 5
                end = search.find(" ", start)
                if end == -1:
                    end = len(search)

                sizeStr = search[start:end]
                if sizeStr.find(":") > -1:
                    sizes = sizeStr.split(":")
                    if sizes[0] != '':
                        min_val = int(sizes[0])
                    if sizes[1] != '':
                        max_val = int(sizes[1])
                else:
                    min_val = max_val = int(sizeStr)
                self.slider_positions = (min_val * self.conversion_factor, max_val * self.conversion_factor)
                self.filesize.SetCurrentValues(*self.slider_positions)
            except:
                pass

    @warnWxThread
    def Reset(self):
        self.search.Clear()
        self.filesize.Reset()
        self.slider_positions = (0, 0)

    def GetSliderMinMax(self):
        return self.slider_minmax

    @warnWxThread
    def SetSliderMinMax(self, length_min, length_max):
        if self.slider_minmax != (length_min, length_max):
            self.slider_minmax = (length_min, length_max)
            self.filesize.SetMinMax(length_min, length_max)
            min_val = max(self.slider_positions[0], length_min)
            max_val = min(self.slider_positions[1], length_max)
            self.filesize.SetCurrentValues(min_val, max_val)

    @warnWxThread
    def AddButton(self, btn_label, btn_handler):
        num_children = len(self.filter_sizer.GetChildren())
        if num_children < 2:
            return
        child = self.filter_sizer.GetItem(num_children - 3)
        child = child.GetWindow() if getattr(child, 'IsWindow', False) and child.IsWindow() else child
        if not isinstance(child, wx.Button):
            if btn_handler:
                btn = wx.Button(self.filter_panel, -1, btn_label)
                btn.Bind(wx.EVT_BUTTON, btn_handler)
                btn.SetMinSize((-1, 23))
                self.filter_sizer.Insert(num_children - 2, btn, 0, wx.CENTER | wx.RIGHT, 3)
                self.filter_sizer.Layout()
                self.Layout()
        else:
            btn = child
            if btn_handler:
                btn.SetLabel(btn_label)
                btn.Bind(wx.EVT_BUTTON, btn_handler)
            else:
                self.filter_sizer.Remove(btn)
                btn.Destroy()
                self.filter_sizer.Layout()

    def ResizeColumn(self, *args, **kwargs):
        pass


class ListItemHeader(wx.Panel):

    def __init__(self, parent, parent_list):
        wx.Panel.__init__(self, parent)

        self.guiutility = GUIUtility.getInstance()

        self.SetBackgroundColour(FILTER_GREY)
        self.SetForegroundColour(parent.GetForegroundColour())

        self.icon_down = NativeIcon.getInstance().getBitmap(self, 'arrow', self.GetBackgroundColour(), state=0)
        self.icon_right = self.icon_down.ConvertToImage().Rotate90(False).ConvertToBitmap()

        self.parent_list = parent_list
        self.header_cols = [{'name': 'Name', 'fontSize': 2, 'showColumname': False}]
        self.header_list = self.GetHeaderList(self)

        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(self.header_list, 1, wx.EXPAND)
        self.SetSizer(vSizer)

    def SetTitle(self, item):
        pass

    def SetButtons(self, channel):
        pass

    def OnExpand(self, item):
        return True

    def OnCollapse(self, item, panel, from_expand=False):
        if panel:
            panel.Destroy()
            self.parent_list.ResetBottomWindow()
        wx.CallAfter(self.guiutility.frame.top_bg.TorrentsChanged)

    def GetHeaderList(self, parent):
        return FixedListBody(parent, self, self.header_cols, singleExpanded=True)


class ChannelHeader(ListItemHeader):

    @warnWxThread
    def SetTitle(self, item):
        if item and isinstance(item, Channel):
            channel = item
            if self.header_list.InList(channel.id):
                self.header_list.RemoveKey(channel.id)

            self.header_list.SetData([(channel.id, [channel.name], channel, ChannelListItemNoButton)], force=True)

            new_item = self.header_list.GetItem(channel.id)
            new_item.SetTitleSizerHeight(30)
            new_item.list_deselected = FILTER_GREY
            new_item.SetHideButtons(False)

            self.header_list.Layout()

    @warnWxThread
    def SetButtons(self, channel):
        item = self.header_list.GetItems()[0]
        num_items = len(self.parent_list.list.raw_data) if self.parent_list.list.raw_data else 0

        channelstate, iamModerator = channel.getState()

        open2edit = channelstate == ChannelCommunity.CHANNEL_CLOSED and iamModerator
        allow2edit = channel.my_vote == 2 and channelstate == ChannelCommunity.CHANNEL_OPEN
        item.buttonSizer.Clear(deleteWindows=True)

        if channel.my_vote == 0 and not iamModerator:
            item.AddButton("Mark as Spam", self.parent_list.OnSpam, 4)
            item.AddButton("Mark as Favorite", self.parent_list.OnFavorite, 4)
        else:
            if open2edit or allow2edit:
                item.AddButton("Edit this Channel", self.parent_list.OnManage, 4)
            if channel.my_vote == -1:
                item.AddButton("This is not Spam", self.parent_list.OnRemoveSpam, 4)
            elif channel.my_vote == 2:
                item.AddButton("Remove Favorite", self.parent_list.OnRemoveFavorite, 4)
            elif not open2edit and not allow2edit:
                item.AddButton("Edit this Channel", self.parent_list.OnManage, 4)

    @warnWxThread
    def OnExpand(self, item):
        if isinstance(item, ChannelListItem):
            from Tribler.Main.vwxGUI.list_details import ChannelDetails
            self.parent_list.list.DeselectAll()
            detailspanel = self.guiutility.SetBottomSplitterWindow(ChannelDetails)
            detailspanel.showChannel(item.original_data)
            item.expandedPanel = detailspanel

        return ListItemHeader.OnExpand(self, item)


class PlaylistHeader(ListItemHeader):

    @warnWxThread
    def SetTitle(self, item):
        if item and isinstance(item, Playlist):
            playlist = item
            if self.header_list.InList(playlist.id):
                self.header_list.RemoveKey(playlist.id)

            self.header_list.SetData([(playlist.id, [playlist.name], playlist, PlaylistItemNoButton)], force=True)

            new_item = self.header_list.GetItem(playlist.id)
            new_item.SetTitleSizerHeight(30)

            from Tribler.Main.vwxGUI.widgets import TagText
            tag = TagText(new_item, -1, label='channel', fill_colour=wx.Colour(210, 252, 120))
            tag.SetToolTipString("Click on this icon to return to %s's channel" % playlist.channel.name)
            new_item.AddEvents(tag)
            tag.Bind(wx.EVT_LEFT_UP, lambda evt: self.guiutility.showChannel(playlist.channel))
            new_item.titleSizer.Insert(0, tag, 0, wx.ALIGN_CENTER_VERTICAL | wx.TOP, 2)
            new_item.titleSizer.Insert(1, (5, -1))
            new_item.titleSizer.Insert(2, wx.StaticBitmap(new_item, -1, self.icon_right), 0, wx.ALIGN_CENTER_VERTICAL | wx.TOP, 2)
            new_item.titleSizer.Insert(3, (5, -1))
            new_item.buttonSizer.Clear(deleteWindows=True)

            new_item.list_deselected = FILTER_GREY
            new_item.ShowSelected()

            self.header_list.Layout()

    def OnExpand(self, item):
        if isinstance(item, PlaylistItem):
            from Tribler.Main.vwxGUI.list_details import PlaylistDetails
            self.parent_list.list.DeselectAll()
            detailspanel = self.guiutility.SetBottomSplitterWindow(PlaylistDetails)
            detailspanel.showPlaylist(item.original_data)
            item.expandedPanel = detailspanel

        return ListItemHeader.OnExpand(self, item)


class DetailHeader(wx.Panel):

    def __init__(self, parent, title=""):
        wx.Panel.__init__(self, parent)
        self.SetBackgroundColour(SEPARATOR_GREY)

        vSizer = wx.BoxSizer(wx.VERTICAL)

        panel = wx.Panel(self)
        panel.SetMinSize((-1, 25))
        panel.SetBackgroundColour(FILTER_GREY)
        if hasattr(parent, 'OnLeaveWindow'):
            panel.Bind(wx.EVT_ENTER_WINDOW, lambda event: parent.OnLeaveWindow())
        self.title = wx.StaticText(panel, label=title)
        _set_font(self.title, fontweight=wx.FONTWEIGHT_BOLD, fontcolour=wx.BLACK)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.title, 0, wx.CENTER | wx.LEFT, 7)
        panel.SetSizer(sizer)

        vSizer.Add(panel, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 1)
        self.SetSizer(vSizer)

    def SetTitle(self, title):
        self.title.SetLabel(title)

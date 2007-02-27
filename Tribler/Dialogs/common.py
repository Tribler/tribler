# Written by Jie Yang
# see LICENSE.txt for license information

import wx
from ABC.GUI.list import ManagedList
from safeguiupdate import DelayedInvocation
from threading import Event

def sort_dictlist(dict_list, key, order='increase'):
    
    aux = [(dict_list[i][key], i) for i in xrange(len(dict_list))]
    try:
        aux.sort()
    except UnicodeDecodeError,e:
        # Arno: there are unicode strings and non-unicode strings in the data.
        # One of the non-unicode strings contains data that cannot be
        # decoded into a unicode string for comparison to the other unicode
        # strings by the default 'ascii' codec. See
        # http://downloads.egenix.com/python/Unicode-EPC2002-Talk.pdf
        #
        # This is a legacy problem, as the new code will store everything as
        # unicode in the database. I therefore chose a dirty solution, don't
        # sort 
        pass
    if order == 'decrease' or order == 1:    # 0 - increase, 1 - decrease
        aux.reverse()
    return [dict_list[i] for x, i in aux]


class CommonTriblerList(ManagedList, DelayedInvocation):
    """ 
    0. Give a unique prefix
    1. IDs in rightalign and centeralign must be set in Utility.constants;
    2. Column labels must be set in the language file;
    3. To set default values, modify Utility.utility.setupConfig()

    WARNING: this constructor is called after the subclass already initialized
    itself, so anything you do here will override the subclass, not initialize it.
    """
    def __init__(self, parent, style, prefix, minid, maxid, exclude = [], rightalign = [], centeralign = []):
        self.parent = parent
        self.utility = parent.utility
        self.prefix = prefix
        ManagedList.__init__(self, parent, style, prefix, minid, maxid, exclude, rightalign, centeralign)
        DelayedInvocation.__init__(self)
        self.doneflag = Event()
        
        self.data = []
        self.lastcolumnsorted, self.reversesort = self.columns.getSortedColumn()
        self.info_dict = {}            # use infohash as the key, used for update
        self.num = self.getMaxNum()    # max num of lines to show
        self.curr_pos = -1

        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnRightClick)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnActivated)
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnColClick)
        self.Bind(wx.EVT_KEY_DOWN, self.onKeyDown)
        
        # for search
        self.Bind(wx.EVT_FIND, self.OnFind)
        self.Bind(wx.EVT_FIND_NEXT, self.OnFind)
        self.Bind(wx.EVT_FIND_CLOSE, self.OnFindClose)
        
        #self.loadList()
        self.DeleteAllItems()
        self.loading()
                    
    def loading(self):    # display "loading ..." 
        self.InsertStringItem(0, self.utility.lang.get('loading'))
                    
    def getMaxNum(self):
        return self.utility.config.Read(self.prefix + "_num", "int")
            
    def OnRightClick(self, event):
        print "right click", self.getSelectedItems()
    
    def onKeyDown(self, event):
        keycode = event.GetKeyCode()
        if event.CmdDown():
            if keycode == ord('a') or keycode == ord('A'):
                # Select all files (CTRL-A)
                self.selectAll()
            elif keycode == ord('x') or keycode == ord('X'):
                # Invert file selection (CTRL-X)
                self.invertSelection()
            elif keycode == ord('f') or keycode == ord('F'):
                self.OnShowFind(event)
        elif keycode == 399:
            # Open right-click menu (windows menu key)
            self.OnRightClick(event)
        event.Skip()
            
    def OnShowFind(self, evt):
        data = wx.FindReplaceData()
        data.SetFlags(1)
        dlg = wx.FindReplaceDialog(self, data, "Find")
        dlg.data = data  # save a reference to it...
        dlg.Show(True)

    def OnFindClose(self, evt):
        evt.GetDialog().Destroy()
            
    def OnFind(self, evt):
#        if self.search_key not in self.keys:
#            return
        et = evt.GetEventType()
        flag = evt.GetFlags()    # 1: down, 2: mach whole word only, 4: match case, 6:4+2
        if not et in (wx.wxEVT_COMMAND_FIND, wx.wxEVT_COMMAND_FIND_NEXT):
            return
        if et == wx.wxEVT_COMMAND_FIND:
            selected = self.getSelectedItems()
            if selected:
                self.curr_pos = selected[0]
            else:
                self.curr_pos = -1
        find_str = evt.GetFindString()
        self.curr_pos = self.findAnItem(find_str, flag)
        if self.curr_pos == -1:
            dlg = wx.MessageDialog(self, 'Passed the end of the list!',
                               'Search Stop',
                               wx.OK | wx.ICON_INFORMATION
                               )
            dlg.ShowModal()
            dlg.Destroy()
            pass
        else:
            #print "found", self.curr_pos
            #item = self.GetItem(index)
            self.SetItemState(self.curr_pos, wx.LIST_STATE_SELECTED, wx.LIST_STATE_SELECTED)
            self.SetItemState(self.curr_pos, wx.LIST_STATE_FOCUSED, wx.LIST_STATE_FOCUSED)
        
    def findAnItem(self, find_str, flag):
        def match(text, find_str, flag):
            if flag&2:    #  mach whole word only
                str_list = text.split()
            else:
                str_list = [text]
            if not flag&4:    # don't match case
                find_str = find_str.lower()
                for i in range(len(str_list)):
                    str_list[i] = str_list[i].lower()
            for s in str_list:
                if s.find(find_str) != -1:
                    return True
            return False
        
        #print "find an item", find_str, flag, self.curr_pos
        if flag&1:
            begin = self.curr_pos+1
            end = len(self.data)
            step = 1
        else:
            if self.curr_pos == -1:
                begin = len(self.data) -1
            else:
                begin = self.curr_pos - 1
            end = -1
            step = -1
        datalist = range(begin, end, step)
        #print "step:", begin, end, step, datalist
        for row in datalist:
            text = self.data[row][self.search_key]
            text=text.replace('.', ' ')
            text=text.replace('_', ' ')
            text=text.replace('-', ' ')
            if match(text, find_str, flag):
                return row
        return -1    # not found
            
    def getSelectedItems(self):
        item = -1
        itemList = []
        while 1:
            item = self.GetNextItem(item,wx.LIST_NEXT_ALL,wx.LIST_STATE_SELECTED)
            if item == -1:
                break
            else:
                itemList.append(item)
        itemList.sort()
        return itemList
    
    def OnActivated(self, event):
        self.curr_idx = event.m_itemIndex
        #print "actived", self.curr_idx

    def OnColClick(self, event):
        col = event.m_col
        active_columns = self.columns.active
        if col >= len(active_columns) or col < 0:
            return
        else:
            col = active_columns[col][0]    # the real position
        if self.lastcolumnsorted == col:
            self.reversesort = 1 - self.reversesort
        else:
            self.reversesort = 0
        self.lastcolumnsorted = col
        self.columns.writeSortedColumn(self.lastcolumnsorted, self.reversesort)
        self.loadList(reload=False, sorted=True)
        
    def reloadData(self):
        raise

    def getText(self, data, row, col):
        raise
        
    def loadList(self, reload=True, sorted=True):
        self.DeleteAllItems() 
        self.loading()
        
        active_columns = self.columns.active
        if not active_columns:
            return
        
        if reload:
            self.reloadData()
        
        if sorted:
            key = self.keys[self.lastcolumnsorted]
            self.data = sort_dictlist(self.data, key, self.reversesort)
            
        num = len(self.data)
        if self.num > 0 and self.num < num:
            num = self.num
            
        first_col = active_columns[0][0]
        # Delete the "Loading... entry before adding the real stuff
        self.DeleteAllItems()
        for i in xrange(num):
            self.InsertStringItem(i, self.getText(self.data, i, first_col))
            for col,rank in active_columns[1:]:
                txt = self.getText(self.data, i, col)
                self.SetStringItem(i, rank, txt)

        self.Show(True)
            
class MainWindow(wx.Frame):
    def __init__(self,parent,id, title):
        wx.Frame.__init__(self,parent,wx.ID_ANY,title,
                          style=wx.DEFAULT_FRAME_STYLE|wx.NO_FULL_REPAINT_ON_RESIZE)
        self.control = CommonTriblerList(self, wx.Size(500, 100))
        self.Fit()
        self.Show(True)

if __name__ == '__main__':
    app = wx.App()
    frame=MainWindow(None,-1,'Demo')
    app.MainLoop()

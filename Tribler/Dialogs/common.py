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

        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnRightClick)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnActivated)
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnColClick)
        #self.loadList()
        self.DeleteAllItems()
        self.loading()
                    
    def loading(self):    # display "loading ..." 
        self.InsertStringItem(0, self.utility.lang.get('loading'))
                    
    def getMaxNum(self):
        return self.utility.config.Read(self.prefix + "_num", "int")
            
    def OnRightClick(self, event):
        print "right click", self.getSelectedItems()
    
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

import wx

def sort_dictlist(dict_list, key, order='increase'):
    aux = [(dict_list[i][key], i) for i in xrange(len(dict_list))]
    aux.sort()
    if order == 'decrease' or order == 1:    # 0 - increase, 1 - decrease
        aux.reverse()
    return [dict_list[i] for x, i in aux]

class CommonTriblerList(wx.ListCtrl):
    def __init__(self, parent, window_size):
        self.parent = parent
        
        try:    # get system font width
            self.fw = wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT).GetPointSize()+1
        except:
            self.fw = wx.SystemSettings_GetFont(wx.SYS_SYSTEM_FONT).GetPointSize()+1
            
        self.data = []
        self.list_key = self.getListKey()
        self.columns = self.getColumns()
        self.sort_column = self.getCurrentSortColumn()
        self.orders = self.getCurrentOrders()
        self.num = self.getMaxNum()     # num of items to be showed 

        assert len(self.list_key) == len(self.columns)
        assert len(self.orders) == len(self.columns)
        assert self.sort_column < len(self.columns)
        
        style = wx.LC_REPORT|wx.LC_VRULES|wx.CLIP_CHILDREN
        wx.ListCtrl.__init__(self, parent, -1, style=style)
        self.SetMinSize(window_size)

        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnRightClick)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnActivated)
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnColClick)
        
        for i in range(len(self.columns)):
            self.InsertColumn(i, self.columns[i][0], format=self.columns[i][1], width=self.columns[i][2]*self.fw)
            
        self.loadList()
                    
    def getListKey(self):
        return ['key1', 'key2']
                    
    def getColumns(self):
        format = wx.LIST_FORMAT_CENTER
        width = 15
        columns = [('test title 1', format, width),
                   ('test title 2', format, width),
                  ]
        
        return columns
    
    def getCurrentSortColumn(self):
        return 0
    
    def getCurrentOrders(self):
        n = len(self.columns)
        orders = [0]*n  # 1 - decrease; 0 - increase
        return orders
            
    def getMaxNum(self):
        return -1
            
    def OnRightClick(self, event):
        #print "right click", self.getSelectedItems()
        pass
        
    
    def OnActivated(self, event):
        self.curr_idx = event.m_itemIndex
        #print "actived", self.curr_idx

    def OnColClick(self, event):
        self.sort_column = event.m_col
        self.orders[self.sort_column] = 1 - self.orders[self.sort_column]
        self.loadList(False)
        
    def reloadData(self):
        self.data = [{'key1': 23, 'key2': 'abc'},
                     {'key1': 14, 'key2': 'cba'},
                    ]

    def getText(self, data, row, col):
        return str(data[row][self.list_key[col]])
        
    def loadList(self, reload=True):

        if reload:
            self.reloadData()
        
        self.data = sort_dictlist(self.data, self.list_key[self.sort_column], self.orders[self.sort_column])
        if self.num >= 0:
            data = self.data[:self.num]
        else:
            data = self.data
        
        self.DeleteAllItems() 
        i = 0
        for i in xrange(len(data)):
            self.InsertStringItem(i, self.getText(data, i, 0))
            for j in range(1, len(self.list_key)):
                self.SetStringItem(i, j, self.getText(data, i, j))
            i += 1
            
        self.Show(True)
    
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
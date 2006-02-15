# Written by Jie Yang
# see LICENSE.txt for license information

import wx
from Tribler.CacheDB.CacheDBHandler import PeerDBHandler, FriendDBHandler
from Tribler.utilities import friendly_time, sort_dictlist

DEBUG = False

class TasteBuddyList(wx.ListCtrl):
    def __init__(self, parent):
        self.parent = parent
        self.utility = parent.utility
        style = wx.LC_REPORT|wx.LC_VRULES|wx.CLIP_CHILDREN
        wx.ListCtrl.__init__(self, parent, -1, size=wx.Size(780, 500), style=style)
        
        self.peer_db = PeerDBHandler()
        
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnShowDetail)
        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnRightClick)
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnColClick)
        
        self.max_num = 100
        self.column = -1
        self.list_key = ['name', 'ip', 'similarity', 'last_seen']
        self.order = [0, 0, 1, 1]    # 1 - decrease; 0 - increase

        try:    # get system font width
            fw = wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT).GetPointSize()+1
        except:
            fw = wx.SystemSettings_GetFont(wx.SYS_SYSTEM_FONT).GetPointSize()+1
            
        self.InsertColumn(0, "Name", format=wx.LIST_FORMAT_CENTER, width=fw*6)
        self.InsertColumn(1, "IP", format=wx.LIST_FORMAT_CENTER, width=fw*15)
        self.InsertColumn(2, "Similarity", format=wx.LIST_FORMAT_CENTER, width=fw*5)
        self.InsertColumn(3, "Last Seen", format=wx.LIST_FORMAT_CENTER, width=fw*15)

        peer_list = self.peer_db.getPeerList()
        self.peers = self.peer_db.getPeers(peer_list, ['permid', 'name', 'ip', 'last_seen', 'similarity'])
        
        self.loadList(num=self.max_num)

    def loadList(self, key='last_seen', order=1, num=100):
        
        if order == 1:
            self.peers = sort_dictlist(self.peers, key, 'decrease')[:num]
        else:
            self.peers = sort_dictlist(self.peers, key, 'increase')[:num]
        
        self.DeleteAllItems() 
        i = 0
        for i in xrange(len(self.peers)):
            peer = self.peers[i]
            self.InsertStringItem(i, peer['name'])
            self.SetStringItem(i, 1, str(peer['ip']))
            self.SetStringItem(i, 2, '%.2f'%(peer['similarity']/1000.0))
            last_seen = friendly_time(peer['last_seen'])
            self.SetStringItem(i, 3, last_seen)
            i += 1
        
        self.Show(True)
                
    def OnColClick(self, event):
        lastColumn = self.column
        self.column = event.m_col
        if self.column == lastColumn:
            self.order[self.column] = 1 - self.order[self.column]
        key = self.list_key[event.m_col]
        self.loadList(key, self.order[self.column])
        
    def OnRightClick(self, event=None):
        self.curr_idx = event.m_itemIndex
        if not hasattr(self, "addFriendID"):
            self.addFriendID = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnAddFriend, id=self.addFriendID)
            self.showDetailID = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnShowDetail, id=self.showDetailID)
            
        # menu for change torrent's rank
        menu = wx.Menu()
        menu.Append(self.addFriendID, "Add to friend")
        #menu.Append(self.showDetailID, "Show Buddy Details")
        
        self.PopupMenu(menu, event.GetPosition())
        menu.Destroy()
        
    def OnAddFriend(self, event=None):
        peer = self.peers[self.curr_idx]
        permid = peer['permid']
        #self.SetStringItem(self.curr_idx, 1, '1')
#        self.DeleteItem(self.curr_idx)
#        self.peers.pop(self.curr_idx)
        self.parent.parent.friendPanel.addFriend(permid)
        if DEBUG:
            print "add friend", peer['name']
        
    def OnShowDetail(self, event=None):
        print "show detail"
    
        

class FriendList(wx.ListCtrl):
    def __init__(self, parent):
        self.parent = parent
        self.tasteBuddyPanel = self.parent.parent.tasteBuddyPanel
        self.utility = parent.utility
        style = wx.LC_REPORT|wx.LC_VRULES|wx.CLIP_CHILDREN
        wx.ListCtrl.__init__(self, parent, -1, size=wx.Size(780, 500), style=style)
        
        self.friend_db = FriendDBHandler()
        
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnShowDetail)
        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnRightClick)

        try:    # get system font width
            fw = wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT).GetPointSize()+1
        except:
            fw = wx.SystemSettings_GetFont(wx.SYS_SYSTEM_FONT).GetPointSize()+1
            
        self.InsertColumn(0, "Name", format=wx.LIST_FORMAT_CENTER, width=fw*6)
        self.InsertColumn(1, "IP", format=wx.LIST_FORMAT_CENTER, width=fw*15)
        self.InsertColumn(2, "Similarity", format=wx.LIST_FORMAT_CENTER, width=fw*5)
        self.InsertColumn(3, "Last Seen", format=wx.LIST_FORMAT_CENTER, width=fw*15)

        self.loadList()
        
    def addFriend(self, permid):
        self.friend_db.addFriend(permid)
        self.loadList()

    def loadList(self):

        self.friends = self.friend_db.getFriends()
#        print "===================================="
#        for buddy in self.friends:
#            print buddy
            
        self.DeleteAllItems() 
        i = 0
        for peer in self.friends:
            if DEBUG:
                print "Insert peer", peer, i
            self.InsertStringItem(i, peer['name'])
            self.SetStringItem(i, 1, str(peer['ip']))
            self.SetStringItem(i, 2, '%.2f'%(peer['similarity']/1000.0))
            last_seen = friendly_time(peer['last_seen'])
            self.SetStringItem(i, 3, last_seen)
            i += 1
            
        self.Show(True)
        
    def OnRightClick(self, event=None):
        self.curr_idx = event.m_itemIndex
        if not hasattr(self, "removeFriendID"):
            self.removeFriendID = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnRemoveFriend, id=self.removeFriendID)
            self.showDetailID = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnShowDetail, id=self.showDetailID)
                
        # menu for change torrent's rank
        menu = wx.Menu()
        menu.Append(self.removeFriendID, "Remove the friend")
        #menu.Append(self.showDetailID, "Show Friend's Details")
        
        self.PopupMenu(menu, event.GetPosition())
        menu.Destroy()
        
    def OnRemoveFriend(self, event=None):
        peer = self.friends[self.curr_idx]
        permid = peer['permid']
        self.DeleteItem(self.curr_idx)
        self.friends.pop(self.curr_idx)
        self.friend_db.deleteFriend(permid)
        #self.tasteBuddyPanel.update()
        if DEBUG:
            print "remove friend", peer['name']
        
    def OnShowDetail(self, event=None):
        print "show detail"
    

class FriendPanel(wx.Panel):
    def __init__(self, parent, utility, dialog = None):
        self.parent = parent
        self.utility = utility
        wx.Panel.__init__(self, parent, -1)

        self.list=FriendList(self)
        
        self.Show()
        
    def addFriend(self, permid):
        self.list.addFriend(permid)
        

class TasteBuddyPanel(wx.Panel):
    def __init__(self, parent, utility, dialog = None):
        self.parent = parent
        self.utility = utility
        wx.Panel.__init__(self, parent, -1)

        self.list=TasteBuddyList(self)
        
        self.Show()

    def update(self):
        self.list.loadList()
        
class ABCBuddyFrame(wx.Frame):
    def __init__(self, parent):
        self.utility = parent.utility
        size = wx.Size(800, 500)
        wx.Frame.__init__(self, None, -1, "Buddy Frame", wx.DefaultPosition, size)
       
        self.notebook = wx.Notebook(self, -1)

        self.tasteBuddyPanel = TasteBuddyPanel(self.notebook, self.utility)
        self.notebook.AddPage(self.tasteBuddyPanel, "Peer List")
        self.notebook.tasteBuddyPanel = self.tasteBuddyPanel

        self.friendPanel = FriendPanel(self.notebook, self.utility)
        self.notebook.AddPage(self.friendPanel, "Friend List")
        self.notebook.friendPanel = self.friendPanel

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        self.Show()

    def OnCloseWindow(self, event = None):
        self.utility.frame.buddyFrame = None
        self.Destroy()        

if __name__ == '__main__':
    app = wx.PySimpleApp()
#    frame = ABCBuddyFrame()
    frame = wx.Frame(None, -1).Show()
    app.MainLoop()

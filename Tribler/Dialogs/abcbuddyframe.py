# Written by Jie Yang
# see LICENSE.txt for license information

import wx
from Tribler.CacheDB.CacheDBHandler import PeerDBHandler, FriendDBHandler
from Tribler.utilities import friendly_time, sort_dictlist
from common import CommonTriblerList

DEBUG = False

class TasteBuddyList(CommonTriblerList):
    def __init__(self, parent, window_size):
        self.parent = parent
        self.peer_db = parent.peer_db
        self.friend_db = parent.friend_db
        CommonTriblerList.__init__(self, parent, window_size)

    def getColumns(self):
        format = wx.LIST_FORMAT_CENTER
        columns = [
            ('Friend', format, 5),
            ('Name', format, 10),
            ('IP', format, 15),
            ('Similarity', format, 8),
            ('Last Seen', format, 15),
            ]
        return columns

    def getListKey(self):
        return ['friend', 'name', 'ip', 'similarity', 'last_seen']

    def getCurrentSortColumn(self):
        return 1

    def getMaxNum(self):
        return 500
        
    def getText(self, data, row, col):
        key = self.list_key[col]
        original_data = data[row][key]
        if key == 'friend':
            if original_data:
                return '*'
            else:
                return ''
        if key == 'name':
            if original_data == '\xff':
                return 'unknown'
        if key == 'similarity':
            return '%.2f'%(original_data/1000.0)
        if key == 'last_seen':
            if original_data == 0:
                return 'Never'
            return friendly_time(original_data)
        return str(original_data)
        
    def reloadData(self):
        peer_list = self.peer_db.getPeerList()
        key = ['permid', 'name', 'ip', 'similarity', 'last_seen']
        self.data = self.peer_db.getPeers(peer_list, key)
        self.friend_list = self.friend_db.getFriendList()
        for i in xrange(len(self.data)):
            if self.data[i]['name'] == '':
                self.data[i]['name'] = '\xff'
            self.data[i]['friend'] = self.data[i]['permid'] in self.friend_list
        
    def OnRightClick(self, event=None):
        self.curr_idx = event.m_itemIndex
        if not hasattr(self, "addFriendID") or not hasattr(self, "removeFriendID"):
            self.addFriendID = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnAddFriend, id=self.addFriendID)
            self.removeFriendID = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnRemoveFriend, id=self.removeFriendID)
        
        # menu for change torrent's rank
        menu = wx.Menu()
        if self.data[self.curr_idx]['friend']:
            menu.Append(self.removeFriendID, "Remove the friend")
        else:
            menu.Append(self.addFriendID, "Add the peer as your friend")
        #menu.Append(self.showDetailID, "Show Buddy Details")
        
        self.PopupMenu(menu, event.GetPosition())
        menu.Destroy()
        
    def OnAddFriend(self, event=None):
        permid = self.data[self.curr_idx]['permid']
        self.data[self.curr_idx]['friend'] = True
        self.SetStringItem(self.curr_idx, 0, '*')
        self.friend_db.addFriend(permid)
#        self.parent.parent.friendPanel.addFriend(permid)
        if DEBUG:
            print "add friend", peer['name']
            
    def OnRemoveFriend(self, event=None):
        peer = self.data[self.curr_idx]
        permid = peer['permid']
        peer['friend'] = False
        self.SetStringItem(self.curr_idx, 0, '')
        self.friend_db.deleteFriend(permid)
#        self.parent.parent.friendPanel.deleteFriend(permid)
        

class TasteBuddyPanel(wx.Panel):
    def __init__(self, frame, parent):
        self.parent = parent
        self.peer_db = frame.peer_db
        self.friend_db = frame.friend_db
        wx.Panel.__init__(self, parent, -1)
        
        self.list=TasteBuddyList(self, frame.window_size)
        self.Fit()
        self.Show(True)


class ABCBuddyFrame(wx.Frame):
    def __init__(self, parent):
        self.parent = parent
        width = 600
        height = 500
        self.window_size = wx.Size(width, height)
        wx.Frame.__init__(self, None, -1, "Buddy Frame", size=wx.Size(width+20, height+60))
       
        self.friend_db = FriendDBHandler()
        self.peer_db = PeerDBHandler()
        
        self.notebook = wx.Notebook(self, -1)

        self.tasteBuddyPanel = TasteBuddyPanel(self, self.notebook)
        self.notebook.AddPage(self.tasteBuddyPanel, "Peer List")
        self.notebook.tasteBuddyPanel = self.tasteBuddyPanel

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        self.Show()

    def OnCloseWindow(self, event = None):
        self.parent.utility.frame.buddyFrame = None
        self.Destroy()        


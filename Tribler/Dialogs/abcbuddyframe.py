# Written by Jie Yang
# see LICENSE.txt for license information

import wx
from Tribler.CacheDB.CacheDBHandler import PeerDBHandler, FriendDBHandler, PreferenceDBHandler
from Tribler.utilities import friendly_time, sort_dictlist
from common import CommonTriblerList
from managefriends import ManageFriendsPanel

DEBUG = False

class TasteBuddyList(CommonTriblerList):
    def __init__(self, parent, window_size):
        self.parent = parent
        self.peer_db = parent.peer_db
        self.friend_db = parent.friend_db
        self.pref_db = parent.pref_db
        CommonTriblerList.__init__(self, parent, window_size)

    def getColumns(self):
        format = wx.LIST_FORMAT_CENTER
        columns = [
            #('Friend', format, 5),
            ('Name', format, 10),
            ('IP', format, 15),
            ('Similarity', format, 8),
            ('Last Seen', format, 15),
            ('# Preferences', format, 10)  
            ]
        return columns

    def getListKey(self):
        #return ['friend', 'name', 'ip', 'similarity', 'last_seen', 'npref']
        return ['name', 'ip', 'similarity', 'last_seen', 'npref']

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
            if original_data == '~':
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
        tempdata = self.peer_db.getPeers(peer_list, key)
        self.friend_list = self.friend_db.getFriendList()

        ## Arno: to make GUI updates simpler, don't show friends in peerlist
        self.data = []
        for peer in tempdata:
            if peer['permid'] not in self.friend_list:
                self.data.append(peer)

        for i in xrange(len(self.data)):
            permid = self.data[i]['permid']
            if self.data[i]['name'] == '':
                self.data[i]['name'] = '~'
            self.data[i]['friend'] = permid in self.friend_list
            self.data[i]['npref'] = self.pref_db.getNumPrefs(permid)
        
    def OnRightClick(self, event=None):
        curr_idx = self.getSelectedItems()

        if not hasattr(self, "addFriendID"): 
            self.addFriendID = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnAddFriend, id=self.addFriendID)
        if not hasattr(self, "deleteFriendID"):
            self.deleteFriendID = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnDeleteFriend, id=self.deleteFriendID)
        if not hasattr(self, "deletePeerID"):
            self.deletePeerID = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnDeletePeer, id=self.deletePeerID)
            
        menu = wx.Menu()
        add_friend = False
        delete_friend = False
        for i in curr_idx:    
            # if all the selected peers have been friend, don't show add menu
            if not self.data[i]['friend']:
                add_friend = True
            else:
                delete_friend = True
                
        if add_friend:
            menu.Append(self.addFriendID, "Add the peer as your friend")
        #if delete_friend:
        #    menu.Append(self.deleteFriendID, "Remove the peer from your friend list")
        menu.Append(self.deletePeerID, "Delete the peer")
            
        self.PopupMenu(menu, event.GetPosition())
        menu.Destroy()
        
    def OnAddFriend(self, event=None):
        selected = self.getSelectedItems()
        for i in selected:
            self.addFriend(i)
        self.parent.reaction()

    def addFriend(self, curr_idx):
        if not self.data[curr_idx]['friend']:
            permid = self.data[curr_idx]['permid']
            self.data[curr_idx]['friend'] = True
            #self.SetStringItem(curr_idx, 0, '*')
            self.friend_db.addFriend(permid)

    def OnDeleteFriend(self, event=None):
        selected = self.getSelectedItems()
        for i in selected:
            self.deleteFriend(i)
        self.parent.reaction()        

    def externalDeleteFriend(self, permid):
        idx = -1
        for i in xrange(len(self.data)):
            if self.data[i]['permid'] == permid:
                idx = i
                break
        if idx > 0:
            self.data[idx]['friend'] = False
            self.SetStringItem(idx, 0, '')
        else:
            self.loadList()
        
    def deleteFriend(self, curr_idx):
        if self.data[curr_idx]['friend']:
            peer = self.data[curr_idx]
            permid = peer['permid']
            peer['friend'] = False
            self.SetStringItem(curr_idx, 0, '')
            self.friend_db.deleteFriend(permid)
#        self.parent.parent.friendPanel.deleteFriend(permid)
        
    def OnDeletePeer(self, event=None):
        curr_idx = self.getSelectedItems()
        j = 0
        for i in curr_idx:
            permid = self.data[i]['permid']
            if self.data[i]['friend']:
                self.friend_db.deleteFriend(permid)
            self.peer_db.deletePeer(permid)
            self.DeleteItem(i-j)
            self.data.pop(i-j)
            j += 1
        self.parent.reaction()
        

class TasteBuddyPanel(wx.Panel):
    def __init__(self, frame, parent):
        self.parent = parent
        self.frame = frame
        self.peer_db = frame.peer_db
        self.friend_db = frame.friend_db
        self.pref_db = frame.pref_db
        wx.Panel.__init__(self, parent, -1)
        
        colSizer = wx.BoxSizer(wx.VERTICAL)
        self.list=TasteBuddyList(self, frame.window_size)
        colSizer.Add(self.list, 1, wx.EXPAND|wx.ALL, 5)
        label = wx.StaticText(self, -1, "Right click on a peer to add as a friend or delete it")
        colSizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL)
        self.SetSizer(colSizer)
        self.SetAutoLayout(True)
        #self.Fit()
        self.Show(True)

    def reaction(self):
        self.frame.reaction()

class ABCBuddyFrame(wx.Frame):
    def __init__(self, parent):
        self.parent = parent
        self.parent.utility.abcbuddyframe = self
        self.utility = self.parent.utility

        width = 640
        height = 300
        self.window_size = wx.Size(width, height)
        wx.Frame.__init__(self, None, -1, self.utility.lang.get('managefriendspeers'), size=wx.Size(width+20, height+60))
       
        self.friend_db = FriendDBHandler()
        self.peer_db = PeerDBHandler()
        self.pref_db = PreferenceDBHandler()
        
        mainbox = wx.BoxSizer(wx.VERTICAL)

        # 1. Topbox contains the notebook
        topbox = wx.BoxSizer(wx.HORIZONTAL)

        self.notebook = wx.Notebook(self, -1)
        self.addPanels()
        topbox.Add(self.notebook, 1, wx.EXPAND|wx.ALL, 5)

        # 2. Bottom box contains "Close" button
        botbox = wx.BoxSizer(wx.HORIZONTAL)

        button = wx.Button(self, -1, self.utility.lang.get('close'), style = wx.BU_EXACTFIT)
        wx.EVT_BUTTON(self, button.GetId(), self.OnCloseWindow)
        botbox.Add(button, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)

        # 3. Pack boxes together
        mainbox.Add(topbox, 0, wx.EXPAND|wx.ALIGN_CENTER_HORIZONTAL, 5)
        mainbox.Add(botbox, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, 5)
        self.SetSizerAndFit(mainbox)

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        self.Show()

    def updateBuddy(self):
        self.tasteBuddyPanel.list.loadList()
        
    def deleteFriend(self, permid):
        self.tasteBuddyPanel.list.externalDeleteFriend(permid)
        
    def OnCloseWindow(self, event = None):
        self.parent.utility.frame.buddyFrame = None
        self.parent.utility.abcbuddyframe = None
        self.Destroy()        

    def addPanels(self):
        self.addFriendsPanel()
        self.addPeerPanel()

    def addFriendsPanel(self):
        self.friendsPanel = ManageFriendsPanel(self.notebook, self.utility, self)
        self.notebook.InsertPage(0,self.friendsPanel, self.utility.lang.get('managefriends'))

    def addPeerPanel(self):
        self.tasteBuddyPanel = TasteBuddyPanel(self, self.notebook)
        self.notebook.InsertPage(1,self.tasteBuddyPanel, self.utility.lang.get('viewpeerlist'))

    def reaction(self):
        cursel = self.notebook.GetSelection()
        self.notebook.DeletePage(0)
        self.addFriendsPanel()
        if cursel != -1:
            self.notebook.SetSelection(cursel)

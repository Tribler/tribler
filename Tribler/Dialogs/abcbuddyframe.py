# Written by Jie Yang
# see LICENSE.txt for license information

import wx
from socket import inet_aton, inet_ntoa

from Tribler.CacheDB.CacheDBHandler import PeerDBHandler, FriendDBHandler, PreferenceDBHandler
from Tribler.utilities import friendly_time, sort_dictlist
from Tribler.unicode import str2unicode
from common import CommonTriblerList
from managefriends import ManageFriendsPanel
from Utility.constants import *

DEBUG = False

class TasteBuddyList(CommonTriblerList):
    def __init__(self, parent):
        self.parent = parent
        self.peer_db = parent.peer_db
        self.friend_db = parent.friend_db
        self.pref_db = parent.pref_db
        
        self.utility = parent.utility
        self.min_rank = -1
        self.max_rank = 5
        self.reversesort = 0
        self.lastcolumnsorted = -1
        
        style = wx.LC_REPORT|wx.LC_HRULES|wx.LC_VRULES
        
        prefix = 'buddy'
        self.search_key = 'name'
        minid = 0
        maxid = 8
        rightalign = []
        centeralign = [
            BUDDY_FRIEND,
            BUDDY_NAME,
            BUDDY_IP,
            BUDDY_SIM,
            BUDDY_LASTSEEN,
            BUDDY_NPREF,
            BUDDY_NCONN,
            BUDDY_NEXNG,
        ]
        
        exclude = []
        
        self.keys = ['friend', 'name', 'ip', 'similarity', 'last_seen', 
                      'npref', 'connected_times', 'buddycast_times']

        CommonTriblerList.__init__(self, parent, style, prefix, minid, maxid, 
                                     exclude, rightalign, centeralign)

    def getText(self, data, row, col):
        key = self.keys[col]
        original_data = data[row][key]
        if key == 'friend':
            if original_data:
                return '*'
            else:
                return ''
        if key == 'ip':
            try:
                ip = inet_ntoa(original_data)
            except:
                ip = original_data
            return ip
        if key == 'name':
            if original_data == '~':
                return 'unknown'
        if key == 'similarity':
            return '%.2f'%(original_data/1000.0)
        if key == 'last_seen':
            if original_data == 0:
                return '-'
            return friendly_time(original_data)
        return str2unicode(original_data)
                
    def reloadData(self):
        peer_list = self.peer_db.getPeerList()
        key = ['permid', 'name', 'ip', 'similarity', 'last_seen', 'connected_times', 'buddycast_times']
        tempdata = self.peer_db.getPeers(peer_list, key)
        for i in xrange(len(tempdata)):
            if tempdata[i]['connected_times'] == 0 and tempdata[i]['buddycast_times'] == 0:
                tempdata[i] = None
        tempdata = filter(None, tempdata)        
        self.friend_list = self.friend_db.getFriendList()

        self.data = []
        for peer in tempdata:
            if peer['permid']:
                self.data.append(peer)

        for i in xrange(len(self.data)):
            permid = self.data[i]['permid']
            if self.data[i]['name'] == '':
                self.data[i]['name'] = '~'
            self.data[i]['friend'] = permid in self.friend_list
            self.data[i]['npref'] = self.pref_db.getNumPrefs(permid)
            try:
                ip = inet_aton(self.data[i]['ip'])
            except:
                ip = self.data[i]['ip']
            self.data[i]['ip'] = ip    # for sort
            
        
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
        include_friend = False
        all_friends = True
        for i in curr_idx:    
            # if all the selected peers have been friend, don't show add menu
            if self.data[i]['friend']:
                include_friend = True
            else:
                all_friends = False
                
        if not all_friends:
            menu.Append(self.addFriendID, self.utility.lang.get('addpeeradfriend'))
            menu.Append(self.deletePeerID, self.utility.lang.get('deletepeer'))
        if include_friend:
            menu.Append(self.deleteFriendID, self.utility.lang.get('deletepeerfriend'))
        
            
        self.PopupMenu(menu, event.GetPosition())
        menu.Destroy()
        
    def OnAddFriend(self, event=None):
        selected = self.getSelectedItems()
        for i in selected:
            self.addFriend(i)
        self.parent.updateFriendPanel()

    def addFriend(self, curr_idx):
        if not self.data[curr_idx]['friend']:
            permid = self.data[curr_idx]['permid']
            self.data[curr_idx]['friend'] = True
            self.SetStringItem(curr_idx, 0, '*')
            self.friend_db.addFriend(permid)

    def OnDeleteFriend(self, event=None):
        selected = self.getSelectedItems()
        for i in selected:
            self.deleteFriend(i)
        self.parent.updateFriendPanel()    

    def deleteFriend(self, curr_idx):
        if self.data[curr_idx]['friend']:
            peer = self.data[curr_idx]
            permid = peer['permid']
            peer['friend'] = False
            self.SetStringItem(curr_idx, 0, '')
            self.friend_db.deleteFriend(permid)
        
    def externalDeleteFriend(self, permid):
        idx = -1
        for i in xrange(len(self.data)):
            if self.data[i]['permid'] == permid:
                idx = i
                break
        if idx > 0:
            self.data[idx]['friend'] = False
            self.SetStringItem(idx, 0, '')
        
    def OnDeletePeer(self, event=None):
        curr_idx = self.getSelectedItems()
        j = 0
        for i in curr_idx:
            permid = self.data[i-j]['permid']
            if self.data[i-j]['friend']:
                continue
            self.peer_db.deletePeer(permid)
            self.DeleteItem(i-j)
            self.data.pop(i-j)
            j += 1

    def updateView(self, friends):
        self.loadList(True)

class TasteBuddyPanel(wx.Panel):
    def __init__(self, frame, parent):
        self.parent = parent
        self.frame = frame
        self.utility = frame.utility
        self.peer_db = frame.peer_db
        self.friend_db = frame.friend_db
        self.pref_db = frame.pref_db
        wx.Panel.__init__(self, parent, -1)

        colSizer = wx.BoxSizer(wx.VERTICAL)
        self.list = TasteBuddyList(self)
        colSizer.Add(self.list, 1, wx.EXPAND|wx.ALL, 5)
        label = wx.StaticText(self, -1, self.utility.lang.get('add_friend_notes'))
        colSizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL)
        self.SetSizer(colSizer)
        self.SetAutoLayout(True)
        #self.Fit()
        self.Show(True)

    def updateFriendPanel(self):
        self.frame.updateFriendPanel()
        
    def updateView(self, friends):
        self.list.updateView(friends)

    def updateColumns(self, force=False):
        self.list.loadList(False, False)

class ABCBuddyFrame(wx.Frame):
    def __init__(self, parent):
        self.utility = parent.utility
        wx.Frame.__init__(self, None, -1, self.utility.lang.get('tb_buddy_short'), 
                          size=self.utility.frame.buddyFrame_size, 
                          pos=self.utility.frame.buddyFrame_pos)
        self.main_panel = self.createMainPanel()
        self.count = 0
        self.loadTasteBuddyList = False

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        self.Bind(wx.EVT_IDLE, self.updateTasteBuddyList)
        self.Show()

    def createMainPanel(self):
        main_panel = wx.Panel(self)
        
        notebook = self.createNoteBook(main_panel)
        bot_box = self.createBottomBoxer(main_panel)
        
        mainbox = wx.BoxSizer(wx.VERTICAL)
        mainbox.Add(self.notebook, 1, wx.EXPAND|wx.ALL, 5)
        mainbox.Add(bot_box, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, 5)
        main_panel.SetSizer(mainbox)
        
        return main_panel

    def loadDatabase(self):
        self.friend_db = FriendDBHandler()
        self.peer_db = PeerDBHandler()
        self.pref_db = PreferenceDBHandler()
        
    def createNoteBook(self, main_panel):
        self.loadDatabase()
        self.notebook = wx.Notebook(main_panel, -1)
        
        self.friendsPanel = ManageFriendsPanel(self.notebook, self.utility, self)
        self.tasteBuddyPanel = TasteBuddyPanel(self, self.notebook)
        
        self.notebook.InsertPage(0, self.tasteBuddyPanel, self.utility.lang.get('viewpeerlist'))
        self.notebook.InsertPage(1, self.friendsPanel, self.utility.lang.get('managefriends'))
        
    def createBottomBoxer(self, main_panel):
        bot_box = wx.BoxSizer(wx.HORIZONTAL)
        button = wx.Button(main_panel, -1, self.utility.lang.get('close'), style = wx.BU_EXACTFIT)
        self.Bind(wx.EVT_BUTTON, self.OnCloseWindow, button)
        bot_box.Add(button, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)
        return bot_box

    def updateTasteBuddyList(self, event=None):
        # Arno: on Linux, the list does not get painted properly before this
        # idle handler is called, which is weird. Hence, I wait for the next
        # idle event and load the filelist there.
        self.count += 1
        if not self.loadTasteBuddyList and self.count >= 2:
            self.tasteBuddyPanel.list.loadList()
            self.Unbind(wx.EVT_IDLE)
            self.count = 0

    def OnCloseWindow(self, event = None):
        self.utility.frame.buddyFrame_size = self.GetSize()
        self.utility.frame.buddyFrame_pos = self.GetPosition()
        self.utility.frame.buddyFrame = None
        self.utility.abcbuddyframe = None
        
        self.Destroy()        
        
    def externalDeleteFriend(self, permid):    # keep update if user deletes 
        self.tasteBuddyPanel.list.externalDeleteFriend(permid)
        
    def updateFriendPanel(self):
        self.friendsPanel.updateView(updateBuddyFrame=False)
        
    def updateBuddyPanel(self, friends):
        self.tasteBuddyPanel.updateView(friends)

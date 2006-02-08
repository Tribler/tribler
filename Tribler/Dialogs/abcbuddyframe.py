# Written by Jie Yang
# see LICENSE.txt for license information

import wx
import images

DEBUG = False

class PeerList(wx.ListCtrl):
    def __init__(self, parent):
        self.parent = parent
        self.utility = parent.utility
        style = wx.LC_REPORT|wx.LC_VRULES|wx.CLIP_CHILDREN
        wx.ListCtrl.__init__(self, parent, -1, size=wx.Size(800, 500), style=style)
        
        self.utility = parent.utility

        #self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        #self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.test)
        #self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnItemSelected)
        self.loadList()

    def loadList(self):

        try:    # get system font width
            fw = wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT).GetPointSize()+1
        except:
            fw = wx.SystemSettings_GetFont(wx.SYS_SYSTEM_FONT).GetPointSize()+1
            
        self.InsertColumn(0, "Name", format=wx.LIST_FORMAT_CENTER, width=fw*6)
        self.InsertColumn(1, "IP", format=wx.LIST_FORMAT_CENTER, width=fw*15)
        self.InsertColumn(2, "Last Download", format=wx.LIST_FORMAT_CENTER, width=fw*30)
        self.InsertColumn(3, "Last Seen", format=wx.LIST_FORMAT_CENTER, width=fw*15)
        
        peers = self.utility.all_peers_cache.getPeers()
        peers.sort()
        
        i = 0
        for peer in peers:
#            if int(peer['friend']) > 0 or not peer['perm_id']:
#                continue
            self.InsertStringItem(i, peer['name'])
            self.SetStringItem(i, 1, peer['ip'])
            if not peer['last_file']:
                peer['last_file'] = ''
            self.SetStringItem(i, 2, peer['last_file'])
            self.SetStringItem(i, 3, peer['last_seen'])
            i += 1
            
        self.Show(True)
    
    def test(self, event):
        rank = event.GetItem()
        print "test", rank
        

    # Do thing when keys are pressed down
    def OnKeyDown(self, event):
        keycode = event.GetKeyCode()
        if event.CmdDown() and (keycode == 97 or keycode == 65):
            # Select all (Ctrl-A)
            self.selectAll()
        elif keycode == 399:
            self.OnItemSelected()
        
        event.Skip()

    def OnItemSelected(self, event = None):
        self.popupmenu = BuddyPopupMenu(self.utility)
        
        # Popup the menu.  If an item is selected then its handler
        # will be called before PopupMenu returns.
        if event is None:
            # use the position of the first selected item (key event)
            position = self.GetItemPosition(10)    #FIXME: find the real postion
        else:
            # use the cursor position (mouse event)
            position = event.GetPosition()
        if DEBUG:
            print event, position
        
        self.PopupMenu(self.popupmenu, position)


class TasteBuddyList(wx.ListCtrl):
    def __init__(self, parent):
        self.parent = parent
        self.utility = parent.utility
        style = wx.LC_REPORT|wx.LC_VRULES|wx.CLIP_CHILDREN
        wx.ListCtrl.__init__(self, parent, -1, size=wx.Size(800, 500), style=style)
        
        self.utility = parent.utility
        
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnShowDetail)
        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnRightClick)

        self.loadList()

    def loadList(self):
        try:    # get system font width
            fw = wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT).GetPointSize()+1
        except:
            fw = wx.SystemSettings_GetFont(wx.SYS_SYSTEM_FONT).GetPointSize()+1
            
        self.InsertColumn(0, "Name", format=wx.LIST_FORMAT_CENTER, width=fw*6)
        self.InsertColumn(1, "Friend Layer", format=wx.LIST_FORMAT_CENTER, width=fw*5)
        self.InsertColumn(2, "My Trust", format=wx.LIST_FORMAT_CENTER, width=fw*5)
        self.InsertColumn(3, "System Trust", format=wx.LIST_FORMAT_CENTER, width=fw*5)
        self.InsertColumn(4, "Similarity", format=wx.LIST_FORMAT_CENTER, width=fw*5)
        self.InsertColumn(5, "IP", format=wx.LIST_FORMAT_CENTER, width=fw*15)
        self.InsertColumn(6, "Last File", format=wx.LIST_FORMAT_CENTER, width=fw*15)
        self.InsertColumn(7, "Last Seen", format=wx.LIST_FORMAT_CENTER, width=fw*15)
        
        self.buddies = self.utility.all_peers_cache.getBuddies(last_file=True)
#        print "===================================="
#        for buddy in self.buddies:
#            print buddy
        
        self.DeleteAllItems() 
        i = 0
        for peer in self.buddies:
            if not peer['perm_id']:
                continue
            if DEBUG:
                print "Insert peer", peer, i
            self.InsertStringItem(i, peer['name'])
            self.SetStringItem(i, 1, str(peer['friend']))
            self.SetStringItem(i, 2, str(peer['my_trust']))
            self.SetStringItem(i, 3, str(peer['sys_trust']))
            self.SetStringItem(i, 4, str(peer['similarity']))
            self.SetStringItem(i, 5, peer['ip'])
            if not peer['last_file']:
                peer['last_file'] = ''
            self.SetStringItem(i, 6, str(peer['last_file']))
            self.SetStringItem(i, 7, peer['last_seen'])
            i += 1
        
        self.Show(True)

    def OnRightClick(self, event=None):
        self.curr_idx = event.m_itemIndex
        curr_trust = self.buddies[self.curr_idx]['my_trust']
        if not hasattr(self, "addFriendID"):
            self.addFriendID = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnAddFriend, id=self.addFriendID)
            self.showDetailID = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnShowDetail, id=self.showDetailID)
            self.requestPreferenceID = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnRequestPreference, id=self.requestPreferenceID)
            
            self.adjustRankID = wx.NewId()
            self.num_ranks = 10
            self.rankID = []
            self.OnRank = []
            self.OnRank.append(self.OnRank0)
            self.OnRank.append(self.OnRank1)
            self.OnRank.append(self.OnRank2)
            self.OnRank.append(self.OnRank3)
            self.OnRank.append(self.OnRank4)
            self.OnRank.append(self.OnRank5)
            self.OnRank.append(self.OnRank6)
            self.OnRank.append(self.OnRank7)
            self.OnRank.append(self.OnRank8)
            self.OnRank.append(self.OnRank9)
            self.OnRank.append(self.OnRank10)
            for i in xrange(self.num_ranks+1):
                self.rankID.append(wx.NewId())
            for i in xrange(self.num_ranks+1):
                self.Bind(wx.EVT_MENU, self.OnRank[i], id=self.rankID[i])
                
        # menu for change torrent's rank
        menu = wx.Menu()
        menu.Append(self.addFriendID, "Add to friend")
        menu.Append(self.showDetailID, "Show Buddy Details")
        menu.Append(self.requestPreferenceID, "Request Preference")
        sm = wx.Menu()
        for i in xrange(self.num_ranks, -1, -1):
            if i == 0:
                label = "No rating"
            else:
                label = str(i)
            if i == curr_trust:
                item = wx.MenuItem(sm, self.rankID[i], label)
                bmp = images.getSmilesBitmap()
                item.SetBitmap(bmp)
                sm.AppendItem(item)
            else:
                sm.Append(self.rankID[i], label)
        menu.AppendMenu(self.adjustRankID, "Rank your trust", sm)
        
        self.PopupMenu(menu, event.GetPosition())
        menu.Destroy()
        
    def OnAddFriend(self, event=None):
        peer = self.buddies[self.curr_idx]
        self.utility.all_peers_cache.addFriend(peer['id'])
        #self.SetStringItem(self.curr_idx, 1, '1')
        self.DeleteItem(self.curr_idx)
        self.buddies.pop(self.curr_idx)
        self.parent.parent.friendPanel.list.loadList()
        if DEBUG:
            print "add friend", peer['name']
        
    def OnShowDetail(self, event=None):
        print "show detail"
    
    def OnRequestPreference(self, event=None):
        
        print "request preference"
        
    def changeTrust(self, rank):
        peer = self.buddies[self.curr_idx]
        peer['my_trust'] = rank
        self.utility.all_peers_cache.updatePeerTrust(peer['id'], rank)
        self.SetStringItem(self.curr_idx, 2, str(rank))
        print "Set my trust", peer['id'], "rank", rank
        
    def OnRank0(self, event=None):
        self.changeTrust(0)
        
    def OnRank1(self, event=None):
        self.changeTrust(1)
        
    def OnRank2(self, event=None):
        self.changeTrust(2)
        
    def OnRank3(self, event=None):
        self.changeTrust(3)
        
    def OnRank4(self, event=None):
        self.changeTrust(4)
        
    def OnRank5(self, event=None):
        self.changeTrust(5)
        
    def OnRank6(self, event=None):
        self.changeTrust(6)
        
    def OnRank7(self, event=None):
        self.changeTrust(7)
        
    def OnRank8(self, event=None):
        self.changeTrust(8)
        
    def OnRank9(self, event=None):
        self.changeTrust(9)
        
    def OnRank10(self, event=None):
        self.changeTrust(10)
        

class FriendList(wx.ListCtrl):
    def __init__(self, parent):
        self.parent = parent
        self.utility = parent.utility
        style = wx.LC_REPORT|wx.LC_VRULES|wx.CLIP_CHILDREN
        wx.ListCtrl.__init__(self, parent, -1, size=wx.Size(800, 500), style=style)
        
        self.utility = parent.utility
        
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnShowDetail)
        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnRightClick)

        self.loadList()

    def loadList(self):

        try:    # get system font width
            fw = wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT).GetPointSize()+1
        except:
            fw = wx.SystemSettings_GetFont(wx.SYS_SYSTEM_FONT).GetPointSize()+1
            
        self.InsertColumn(0, "Name", format=wx.LIST_FORMAT_CENTER, width=fw*6)
        self.InsertColumn(1, "My Trust", format=wx.LIST_FORMAT_CENTER, width=fw*5)
        self.InsertColumn(2, "System Trust", format=wx.LIST_FORMAT_CENTER, width=fw*5)
        self.InsertColumn(3, "Similarity", format=wx.LIST_FORMAT_CENTER, width=fw*5)
        self.InsertColumn(4, "IP", format=wx.LIST_FORMAT_CENTER, width=fw*15)
        self.InsertColumn(5, "Last Seen", format=wx.LIST_FORMAT_CENTER, width=fw*15)
        
        self.friends = self.utility.all_peers_cache.getFriends(last_file=True)
#        print "===================================="
#        for buddy in self.friends:
#            print buddy
            
        self.DeleteAllItems() 
        i = 0;
        for peer in self.friends:
            self.InsertStringItem(i, peer['name'])
            self.SetStringItem(i, 1, str(peer['my_trust']))
            self.SetStringItem(i, 2, str(peer['sys_trust']))
            self.SetStringItem(i, 3, str(peer['similarity']))
            self.SetStringItem(i, 4, peer['ip'])
            self.SetStringItem(i, 5, peer['last_seen'])
            i += 1
            
        self.Show(True)
        
    def OnRightClick(self, event=None):
        self.curr_idx = event.m_itemIndex
        curr_trust = self.friends[self.curr_idx]['my_trust']
        if not hasattr(self, "removeFriendID"):
            self.removeFriendID = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnRemoveFriend, id=self.removeFriendID)
            self.showDetailID = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnShowDetail, id=self.showDetailID)
            self.requestPreferenceID = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnRequestPreference, id=self.requestPreferenceID)
            
            self.adjustRankID = wx.NewId()
            self.num_ranks = 10
            self.rankID = []
            self.OnRank = []
            self.OnRank.append(self.OnRank0)
            self.OnRank.append(self.OnRank1)
            self.OnRank.append(self.OnRank2)
            self.OnRank.append(self.OnRank3)
            self.OnRank.append(self.OnRank4)
            self.OnRank.append(self.OnRank5)
            self.OnRank.append(self.OnRank6)
            self.OnRank.append(self.OnRank7)
            self.OnRank.append(self.OnRank8)
            self.OnRank.append(self.OnRank9)
            self.OnRank.append(self.OnRank10)
            for i in xrange(self.num_ranks+1):
                self.rankID.append(wx.NewId())
            for i in xrange(self.num_ranks+1):
                self.Bind(wx.EVT_MENU, self.OnRank[i], id=self.rankID[i])
                
        # menu for change torrent's rank
        menu = wx.Menu()
        menu.Append(self.removeFriendID, "Remove the friend")
        menu.Append(self.showDetailID, "Show Friend's Details")
        menu.Append(self.requestPreferenceID, "Request Preference")
        sm = wx.Menu()
        for i in xrange(self.num_ranks, -1, -1):
            if i == 0:
                label = "No rating"
            else:
                label = str(i)
            if i == curr_trust:
                item = wx.MenuItem(sm, self.rankID[i], label)
                bmp = images.getSmilesBitmap()
                item.SetBitmap(bmp)
                sm.AppendItem(item)
            else:
                sm.Append(self.rankID[i], label)
        menu.AppendMenu(self.adjustRankID, "Rank your trust", sm)
        
        self.PopupMenu(menu, event.GetPosition())
        menu.Destroy()
        
    def OnRemoveFriend(self, event=None):
        peer = self.friends[self.curr_idx]
        self.utility.all_peers_cache.removeFriend(peer['id'])
        self.DeleteItem(self.curr_idx)
        self.friends.pop(self.curr_idx)
        self.parent.parent.tasteBuddyPanel.list.loadList()
        if DEBUG:
            print "remove friend", peer['name']
        
    def OnShowDetail(self, event=None):
        print "show detail"
    
    def OnRequestPreference(self, event=None):
        print "request preference"
        
    def changeTrust(self, rank):
        peer = self.friends[self.curr_idx]
        peer['my_trust'] = rank
        self.utility.all_peers_cache.updatePeerTrust(peer['id'], rank)
        self.SetStringItem(self.curr_idx, 1, str(rank))
        if DEBUG:
            print "Set my trust", peer['id'], "rank", rank
        
    def OnRank0(self, event=None):
        self.changeTrust(0)
        
    def OnRank1(self, event=None):
        self.changeTrust(1)
        
    def OnRank2(self, event=None):
        self.changeTrust(2)
        
    def OnRank3(self, event=None):
        self.changeTrust(3)
        
    def OnRank4(self, event=None):
        self.changeTrust(4)
        
    def OnRank5(self, event=None):
        self.changeTrust(5)
        
    def OnRank6(self, event=None):
        self.changeTrust(6)
        
    def OnRank7(self, event=None):
        self.changeTrust(7)
        
    def OnRank8(self, event=None):
        self.changeTrust(8)
        
    def OnRank9(self, event=None):
        self.changeTrust(9)
        
    def OnRank10(self, event=None):
        self.changeTrust(10)        

        
class BuddyPopupMenu(wx.Menu):
    def __init__(self, utility):
        wx.Menu.__init__(self)

        self.utility = utility
        self.window = utility.window
        
        self.items = {}

        self.items['add'] = self.makePopup(self.onAddFriend, '&Add friend')
        self.items['detail'] = self.makePopup(self.onBuddyDetail, '&Show details')
        self.items['remove'] = self.makePopup(self.onDelFriend, '&Remove friend')
        self.items['access'] = self.makePopup(self.onAccessDisk, '&Access disk')

    def onAddFriend(self, event=None):
        print "add a friend"
        pass
        
    def onDelFriend(self, event=None):
        print "remove the friend"
        pass
        
    def onBuddyDetail(self, event=None):
        print "buddy detail"
        pass
        
    def onAccessDisk(self, event=None):
        print "access disk"
        pass

    def makePopup(self, event = None, label = ""):
        #text = self.utility.lang.get(label)
        text = label
        
        newid = wx.NewId()
        if event is not None:
            self.Bind(wx.EVT_MENU, event, id=newid)
        self.Append(newid, text)
        return newid


class PeerPanel(wx.Panel):
    def __init__(self, parent, utility, dialog = None):
        self.parent = parent
        self.utility = utility
        wx.Panel.__init__(self, parent, -1)

        self.list=PeerList(self)
        
        self.Show()

        
class FriendPanel(wx.Panel):
    def __init__(self, parent, utility, dialog = None):
        self.parent = parent
        self.utility = utility
        wx.Panel.__init__(self, parent, -1)

        self.list=FriendList(self)
        
        self.Show()


class TasteBuddyPanel(wx.Panel):
    def __init__(self, parent, utility, dialog = None):
        self.parent = parent
        self.utility = utility
        wx.Panel.__init__(self, parent, -1)

        self.list=TasteBuddyList(self)
        
        self.Show()

        
class ABCBuddyFrame(wx.Frame):
    def __init__(self, parent):
        self.utility = parent.utility
        size = wx.Size(800, 500)
        wx.Frame.__init__(self, None, -1, "Buddy Frame", wx.DefaultPosition, size)
       
        self.notebook = wx.Notebook(self, -1)

        self.tasteBuddyPanel = TasteBuddyPanel(self.notebook, self.utility)
        self.notebook.AddPage(self.tasteBuddyPanel, "Taste Buddy List")
        self.notebook.tasteBuddyPanel = self.tasteBuddyPanel

        self.peerPanel = PeerPanel(self.notebook, self.utility)
        self.notebook.AddPage(self.peerPanel, "Peer List")
        self.notebook.peerPanel = self.peerPanel

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

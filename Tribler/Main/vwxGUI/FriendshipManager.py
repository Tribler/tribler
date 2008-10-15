# Written by Ali Abbas, Arno Bakker, Tim Tucker
# see LICENSE.txt for license information

#########################################################################
# Description : Ask whether or not to accept a friendship request
#########################################################################
import sys
from traceback import print_exc
import wx

from Tribler.Core.API import *
from Tribler.Core.Utilities.utilities import show_permid_short

from Tribler.Main.vwxGUI.IconsManager import IconsManager, data2wxBitmap

class FriendshipManager:
    
    def __init__(self,utility,iconpath):
        self.utility = utility
        self.session = utility.session
        self.iconpath = iconpath
        self.iconsManager = IconsManager.getInstance()

        self.session.set_friendship_callback(self.sesscb_friendship_callback)
    
    def sesscb_friendship_callback(self,permid,params):
        """ Called by SessionThread """
        
        # Find peer in DB, to get name
        peerdb = self.utility.session.open_dbhandler(NTFY_PEERS)
        peer = peerdb.getPeer(permid)
        icon = peerdb.getPeerIcon(permid)
        self.utility.session.close_dbhandler(peerdb)
        
        wx.CallAfter(self.gui_friendship_callback,permid,peer,icon)
        
    def gui_friendship_callback(self,permid,peer,icon):
        if peer['name'] is None or peer['name'] == "":
            name = show_permid_short(permid)
        else:
            name = peer['name']

        defbm = self.iconsManager.get_default('personsMode','DEFAULT_THUMB')
        if icon[0] is None:
            bm = defbm 
        else:
            bm = data2wxBitmap(icon[0],icon[1])
            if bm is None:
                bm = defbm
        
        dial = FriendRequestDialog(None,self.utility,self.iconpath,name,bm)
        returnValue = dial.ShowModal()
        #print >>sys.stderr,"fm: displayReq: RETURN",returnValue
        if returnValue != wx.ID_CANCEL:
            approved = returnValue == wx.ID_YES
            # Send our response 
            self.session.send_friendship_message(permid,F_RESPONSE_MSG,approved=approved)    



class FriendRequestDialog(wx.Dialog):
    
    def __init__(self,parent,utility,iconpath,name,bm):
        self.utility = utility
        wx.Dialog.__init__(self,parent,-1,self.utility.lang.get('question'))
        
        # Set icons for Dialog
        self.icons = wx.IconBundle()
        self.icons.AddIconFromFile(iconpath,wx.BITMAP_TYPE_ICO)
        self.SetIcons(self.icons)

        mainbox = wx.BoxSizer(wx.VERTICAL)
        peerbox = wx.BoxSizer(wx.HORIZONTAL)
        bb = wx.BitmapButton(self,-1,bm)
        qtext = wx.StaticText(self, -1, self.utility.lang.get('addfriendfillin') % name)
        peerbox.Add(bb, 1, wx.EXPAND|wx.ALL, 5)
        peerbox.Add(qtext, 1, wx.EXPAND|wx.ALL , 5)

        # The standard stuff has problems: NO button doesn't return on ShowModal()
        # buttonbox = self.CreateStdDialogButtonSizer(wx.YES_NO)

        self.yesbtn = wx.Button(self, -1, self.utility.lang.get('yes'))
        self.Bind(wx.EVT_BUTTON, self.onYES, self.yesbtn)
        self.nobtn = wx.Button(self, -1, self.utility.lang.get('no'))
        self.Bind(wx.EVT_BUTTON, self.onNO, self.nobtn)
        buttonbox = wx.BoxSizer( wx.HORIZONTAL )
        buttonbox.Add(self.yesbtn, 0, wx.ALL, 5)
        buttonbox.Add(self.nobtn, 0, wx.ALL, 5)

        self.Bind(wx.EVT_CLOSE, self.onCloseWindow)        
        mainbox.Add(peerbox, 1, wx.EXPAND, 1)
        mainbox.Add(buttonbox, 0, wx.ALIGN_BOTTOM|wx.EXPAND, 1)
        self.SetSizerAndFit(mainbox)


    def onYES(self, event = None):
        self.EndModal(wx.ID_YES)
        
    def onNO(self, event = None):
        self.EndModal(wx.ID_NO)

    def onCloseWindow(self, event = None):
        self.EndModal(wx.ID_CANCEL)

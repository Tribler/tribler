# Written by Arno Bakker and ABC authors  
# see LICENSE.txt for license information

import sys
import wx

from traceback import print_exc,print_stack

from Tribler.Core.API import *
#from Tribler.Main.Dialogs.GUIServer import GUIServer
from Tribler.Main.Dialogs.aboutme import *
from Tribler.Main.Dialogs.TorrentMaker import TorrentMaker    
from Tribler.Main.Dialogs.abcoption import ABCOptionDialog
    
class MainMenuBar(wx.MenuBar):
    
    def __init__(self,parent,utility):
        self.utility = utility
        self.parent = parent

        self.torrentmaker = None
        
        wx.MenuBar.__init__(self)
        self.parent.SetMenuBar(self)

        filemenu = wx.Menu()
        item = filemenu.Append(-1,self.utility.lang.get('menu_addtorrentfile'))
        self.parent.Bind(wx.EVT_MENU,self.OnMenuAddTorrent,id = item.GetId())
        
        item = filemenu.Append(-1,self.utility.lang.get('menu_addtorrentnondefault'))
        self.parent.Bind(wx.EVT_MENU,self.OnMenuAddTorrentNonDefault,id = item.GetId())
        
        item = filemenu.Append(-1,self.utility.lang.get('menu_addtorrenturl'))
        self.parent.Bind(wx.EVT_MENU,self.OnMenuAddTorrentURL,id = item.GetId())
        
        item = filemenu.Append(wx.ID_PREFERENCES,self.utility.lang.get('menuabcpreference'))
        self.parent.Bind(wx.EVT_MENU,self.OnMenuPreferences,id = item.GetId())
        
        item = filemenu.Append(wx.ID_CLOSE,self.utility.lang.get('menuexit'))
        self.parent.Bind(wx.EVT_MENU,self.parent.OnCloseWindow,id = item.GetId())
        
        toolsmenu = wx.Menu()
        item = toolsmenu.Append(-1,self.utility.lang.get('menucreatetorrent'))
        self.parent.Bind(wx.EVT_MENU,self.OnMenuCreateTorrent,id = item.GetId())
        
        aboutmenu = wx.Menu()
        item = aboutmenu.Append(-1,self.utility.lang.get('menuchecklatestversion'))
        self.parent.Bind(wx.EVT_MENU,self.OnMenuCheckVersion,id = item.GetId())
        
        item = aboutmenu.Append(wx.ID_ABOUT,self.utility.lang.get('menuaboutabc'))
        self.parent.Bind(wx.EVT_MENU,self.OnMenuAbout,id = item.GetId())
        
        #self.parent.Bind(wx.EVT_MENU, self.OnMenu)
        
        menus = [(filemenu,self.utility.lang.get('menu_file')),(toolsmenu,self.utility.lang.get('menutools')),(aboutmenu,self.utility.lang.get('menuversion'))]
        self.SetMenus(menus)


    def OnMenuAddTorrent(self,event=None):
        
        print >>sys.stderr,"mmb: OnMenuAddTorrent"
        
        paths = self.askPathsFromUser()
        if paths is None:
            return

        for torrentfile in paths:
            # Arno: remember last dir
            self.utility.setLastDir("open",os.path.dirname(torrentfile))
            self.parent.startDownload(torrentfile)

    def OnMenuAddTorrentNonDefault(self,event=None):
        paths = self.askPathsFromUser()
        if paths is None:
            return
        
        destdir = self.getDestDir()
        if destdir is None:
            return

        for torrentfile in paths:
            # Arno: remember last dir
            self.utility.setLastDir("open",os.path.dirname(torrentfile))
            self.parent.startDownload(torrentfile)

    def OnMenuAddTorrentURL(self,event=None):

        # See if there's a url in the clipboard
        # If there is, use that as the default for the dialog
        starturl = ""
        text = None
        if wx.TheClipboard.Open():
            data = wx.TextDataObject()
            gotdata = wx.TheClipboard.GetData(data)
            wx.TheClipboard.Close()
            if gotdata:
                text = data.GetText()
        if text is not None:
            if text.startswith("http://") and (text.endswith(".torrent") or text.endswith(TRIBLER_TORRENT_EXT)):
                starturl = text
    
        dialog = wx.TextEntryDialog(None, 
                                    self.utility.lang.get('enterurl'), 
                                    self.utility.lang.get('addtorrenturl_short'),
                                    starturl)

        result = dialog.ShowModal()
        btlink = dialog.GetValue()
        dialog.Destroy()

        if result != wx.ID_OK:
            return

        if btlink != "":
            #guiserver = GUIServer.getInstance()
            load_url_lambda = lambda:self.load_torrent_from_url(btlink)
            wx.CallAfter(load_url_lambda)
            #guiserver.add_task(load_url_lambda,0)


    def load_torrent_from_url(self,url):
        """ Called by GUIServer thread (!= MainThread) """
        tdef = TorrentDef.load_from_url(url)
        wx.CallAfter(self.parent.startDownload,None,tdef=tdef)


    def OnMenuPreferences(self,event=None):
        dialog = ABCOptionDialog(self.utility.frame)
        dialog.ShowModal()
        dialog.Destroy()
        pass

    def OnMenuCreateTorrent(self,event=None):
        self.torrentmaker = TorrentMaker(self.utility.frame)
    
    def OnMenuCheckVersion(self,event=None):
        dialog = VersionDialog(self.utility.frame)
        dialog.ShowModal()
        dialog.Destroy()

    def OnMenuAbout(self,event=None):
        dialog = AboutMeDialog(self.utility.frame)
        dialog.ShowModal()
        dialog.Destroy()
        
        

    def askPathsFromUser(self):
        dialog = wx.FileDialog(None, 
                               self.utility.lang.get('choosetorrentfile'), 
                               self.utility.getLastDir("open"), 
                               '', 
                               self.utility.lang.get('torrentfileswildcard') + ' (*.torrent;*'+TRIBLER_TORRENT_EXT+';*.tstream)|*.torrent;*'+TRIBLER_TORRENT_EXT+';*.tstream', 
                               wx.OPEN|wx.MULTIPLE)
        result = dialog.ShowModal()
        dialog.Destroy()
        if result != wx.ID_OK:
            return None
        
        return dialog.GetPaths()

    def getDestDir(self):
        
        defaultdir = self.utility.getLastDir("save")

        dialog = wx.DirDialog(None, 
                              self.utility.lang.get('choosedirtosaveto'), 
                              defaultdir, 
                              style = wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        dialog.Raise()
        result = dialog.ShowModal()
        dialog.Destroy()
        if result != wx.ID_OK:
            return None
        
        destdir = dialog.GetPath()

        self.utility.setLastDir('save',destdir)
        
        return destdir
            
        

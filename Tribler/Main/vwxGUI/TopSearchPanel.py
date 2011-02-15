# Written by Niels Zeilemaker

import wx.animate
from GuiUtility import GUIUtility
from Tribler.Main.Utility.utility import Utility
from Tribler.__init__ import LIBRARYNAME
from Tribler.Core.CacheDB.SqliteCacheDBHandler import UserEventLogDBHandler, NetworkBuzzDBHandler
from Tribler.Core.simpledefs import NTFY_TERM
from Tribler.Core.APIImplementation.miscutils import NamedTimer
from Tribler.Core.Session import Session

from bgPanel import bgPanel
from tribler_topButton import *
from traceback import print_exc

DEBUG = False

class TopSearchPanel(bgPanel):
    def __init__(self, *args, **kwds):
        if DEBUG:
            print >> sys.stderr , "TopSearchPanel: __init__"
        bgPanel.__init__(self, *args, **kwds)
        self.init_ready = False
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility 
        self.installdir = self.utility.getPath()
        self.animationTimer = None
        
        self.buttonsBackgroundColourSelected = wx.Colour(235, 233, 228)
        self.buttonsBackgroundColour = wx.Colour(193, 188, 177)
        self.buttonsForegroundColour = wx.BLACK
        
        self.uelog = UserEventLogDBHandler.getInstance()
        self.nbdb = NetworkBuzzDBHandler.getInstance()
    
    def OnAutoComplete(self):
        self.OnSearchKeyDown()
        self.uelog.addEvent(message="TopSearchPanel: user used autocomplete", type = 2)  
    
    def OnSearchKeyDown(self, event = None):
        if DEBUG:
            print >> sys.stderr, "TopSearchPanel: OnSearchKeyDown"
        wx.CallAfter(self.guiUtility.dosearch)
    
    def StartSearch(self):
        self.ag.Show()
        self.go.GetContainingSizer().Layout()
        self.ag.Play()
            
        # Timer to stop animation after 10 seconds. No results will come 
        # in after that
        if self.animationTimer:
            self.animationTimer.Restart(10000)
        else:
            self.animationTimer = wx.CallLater(10000, self.HideAnimation)
            
        if not self.results.IsEnabled():
            self.results.Enable()
                  
        self.selectTab('search_results')
        self.results.SetValue(True)
    
    def OnResults(self, event):
        self._selectPage('search_results')

    def OnChannels(self, event):
        if self.guiUtility.guiPage not in ['channels', 'mychannel']:
            wx.CallAfter(self.guiUtility.ShowPage, 'channels')
        self.selectTab('channels')
   
    def OnSettings(self, event):
        self._selectPage('settings')
    
    def OnHome(self, event):
        self._selectPage('home')
        
    def OnLibrary(self, event):
        self._selectPage('my_files')
    
    def OnStats(self, event):
        self._selectPage('stats')
    
    def _selectPage(self, page):
        if self.guiUtility.guiPage != page:
            wx.CallAfter(self.guiUtility.ShowPage, page)
            
        self.selectTab(page)
        
    def selectTab(self, tab):
        self.home.SetValue(tab == 'home')
        self.results.SetValue(tab == 'search_results')
        self.channels.SetValue(tab == 'channels')
        self.settings.SetValue(tab == 'settings')
        self.my_files.SetValue(tab == 'my_files')
                
    def complete(self, term):
        """autocompletes term."""
        if len(term) > 1:
            return self.nbdb.getTermsStartingWith(term, num=7)
        return []

    def SearchFocus(self):
        self.searchField.SetFocus()
        self.searchField.SelectAll()

    def Bitmap(self, path, type):
        namelist = path.split("/")
        path = os.path.join(self.installdir, LIBRARYNAME, "Main", "vwxGUI", *namelist)
        return wx.Bitmap(path, type)
        
    def _PostInit(self):
        if DEBUG:
            print >> sys.stderr, "TopSearchPanel: OnCreate"
        
        bgPanel._PostInit(self)
        self.SetBackgroundColour(wx.Colour(255, 255, 255))
        
        
        """
        if sys.platform == 'linux2':
            #bug in linux for searchctrl, focus does not hide search text + text stays grey
            self.searchField = wx.TextCtrl(self, -1, "", style=wx.TE_PROCESS_ENTER)
        else:
            self.searchField = wx.SearchCtrl(self, -1, "", style=wx.TE_PROCESS_ENTER)
        self.searchField.SetMinSize((400, -1))
        self.searchField.SetFocus()
        
        self.searchField.Bind(wx.EVT_SEARCHCTRL_SEARCH_BTN, self.OnSearchKeyDown)
        """
        
        if sys.platform == 'darwin':
            self.searchField = wx.SearchCtrl(self, -1, "", style=wx.TE_PROCESS_ENTER)
            self.searchField.Bind(wx.EVT_SEARCHCTRL_SEARCH_BTN, self.OnSearchKeyDown)
        else:
            self.searchField = TextCtrlAutoComplete(self, entrycallback = self.complete, selectcallback = self.OnAutoComplete)
        self.searchField.SetMinSize((400, -1))
        self.searchField.SetFocus()
        self.searchField.Bind(wx.EVT_TEXT_ENTER, self.OnSearchKeyDown)
        
        self.go = tribler_topButton(self,-1,name = 'Search_new')
        self.go.SetMinSize((50, 24))
        self.go.Bind(wx.EVT_LEFT_UP, self.OnSearchKeyDown)
        
        def createToggle(label, event):
            button = wx.ToggleButton(self, -1, label)
            button.Bind(wx.EVT_TOGGLEBUTTON, event)
            return button
        
        self.channels = createToggle('Channels', self.OnChannels)
        self.settings = createToggle('Settings', self.OnSettings)
        self.my_files = createToggle('Library', self.OnLibrary)
        self.results = createToggle('Results', self.OnResults)
        self.results.Disable()
        
        self.home = createToggle('Home', self.OnHome)
        self.selectTab('home')
        
        if sys.platform == 'win32':
            self.files_friends = wx.StaticBitmap(self, -1, self.Bitmap("images/search_files_channels.png", wx.BITMAP_TYPE_ANY))
            self.tribler_logo2 = wx.StaticBitmap(self, -1, self.Bitmap("images/logo4video2_win.png", wx.BITMAP_TYPE_ANY))
        else:    
            self.files_friends = wx.StaticText(self, -1, "Search Files or Channels") 
            self.tribler_logo2 = wx.StaticBitmap(self, -1, self.Bitmap("images/logo4video2.png", wx.BITMAP_TYPE_ANY))
            
            if sys.platform == 'linux2':
                self.files_friends.SetFont(wx.Font(8, wx.SWISS, wx.NORMAL, wx.BOLD, 0, "Nimbus Sans L"))
            elif sys.platform == 'darwin': # mac
                self.files_friends.SetFont(wx.Font(8, wx.SWISS, wx.NORMAL, wx.BOLD, 0, ""))
        self.tribler_logo2.Bind(wx.EVT_LEFT_UP, self.OnStats)
        
        self.__do_layout()
        self.Layout()
        
        self.init_ready = True
        self.Bind(wx.EVT_SIZE, self.OnResize)

#        # ProxyService 90s Test_
#        from Tribler.Core.TorrentDef import TorrentDef
#        import M2Crypto
#        from Tribler.Core.simpledefs import NTFY_PEERS, PROXY_MODE_PRIVATE
#        import urllib
#        # Test if the 90s file exists in the Session.get_state_dir() folder
#        if os.path.isfile(os.path.join(self.utility.session.get_state_dir(),"Proxy90secondsTest")):
#            # Do not execute the 90s test
#            pass
#        else:
#            # Execute the 90s test
#            
#            # Mark test as active
#            session = Session.get_instance()
#            session.set_90stest_state(True)
#            
#            # Create the 90s empty file
#            open(os.path.join(self.utility.session.get_state_dir(),"Proxy90secondsTest"), "w").close()
#            
#            # http://swarm.cs.pub.ro/~george/90s-test/Data.90s-test.8M.swarm.torrent is a temporary location
#            torrent_def = TorrentDef.load_from_url('http://proxytestreporter.tribler.org/Data.90s-test.8M.swarm.torrent')
#            
#            # Check if the torrent_def is a valid object 
#            if torrent_def is None:
#                return
#            
#            # add the 4 proxy servers to batabase
#            peerlist = []
#            # add the proxy01 as a friend
#            # get proxy01 permid
#            proxy01_keypair = urllib.urlopen('http://proxytestreporter.tribler.org/ec01pub.pem').read()
#            if proxy01_keypair != '':
#                tmpfile = open(os.path.join(self.utility.session.get_state_dir(),"Proxy90secondsTestTemporaryPermidKey01"), "w")
#                tmpfile.write(proxy01_keypair)
#                tmpfile.close()
#                proxy01_ec_keypair = M2Crypto.EC.load_pub_key(os.path.join(self.utility.session.get_state_dir(),"Proxy90secondsTestTemporaryPermidKey01"))
#                proxy01_permid = str(proxy01_ec_keypair.pub().get_der())
#                # set proxy01 ip address
#                proxy01_ip = "95.211.105.67"
##                proxy01_ip = "141.85.224.203"
##                proxy01_ip = "10.38.129.243"
#                # set proxy01 port
#                proxy01_port = 25123
#                # add proxy01 as a peer
#                peerdb = self.utility.session.open_dbhandler(NTFY_PEERS)
#                peer = {}
#                peer['permid'] = proxy01_permid
#                peer['ip'] = proxy01_ip
#                peer['port'] = proxy01_port
#                peer['last_seen'] = 0
#                peerdb.addPeer(peer['permid'], peer, update_dns=True, commit=True)
#                
#                # Delete the temporary key file 
#                os.remove(os.path.join(self.utility.session.get_state_dir(),"Proxy90secondsTestTemporaryPermidKey01"))
#
#                peerlist.append(proxy01_permid)
#
#            # add the proxy02 as a friend
#            # get proxy02 permid
#            proxy02_keypair = urllib.urlopen('http://proxytestreporter.tribler.org/ec02pub.pem').read()
#            if proxy02_keypair != '':
#                tmpfile = open(os.path.join(self.utility.session.get_state_dir(),"Proxy90secondsTestTemporaryPermidKey02"), "w")
#                tmpfile.write(proxy02_keypair)
#                tmpfile.close()
#                proxy02_ec_keypair = M2Crypto.EC.load_pub_key(os.path.join(self.utility.session.get_state_dir(),"Proxy90secondsTestTemporaryPermidKey02"))
#                proxy02_permid = str(proxy02_ec_keypair.pub().get_der())
#                # set proxy02 ip address
#                proxy02_ip = "95.211.105.69"
##                proxy02_ip = "141.85.224.207"
##                proxy02_ip = "10.38.229.46"
#                # set proxy02 port
#                proxy02_port = 25123
#                # add proxy02 as a peer
#                peerdb = self.utility.session.open_dbhandler(NTFY_PEERS)
#                peer = {}
#                peer['permid'] = proxy02_permid
#                peer['ip'] = proxy02_ip
#                peer['port'] = proxy02_port
#                peer['last_seen'] = 0
#                peerdb.addPeer(peer['permid'], peer, update_dns=True, commit=True)
#                
#                # Delete the temporary key file 
#                os.remove(os.path.join(self.utility.session.get_state_dir(),"Proxy90secondsTestTemporaryPermidKey02"))
#
#                peerlist.append(proxy02_permid)
#
#            # add the proxy03 as a friend
#            # get proxy03 permid
#            proxy03_keypair = urllib.urlopen('http://proxytestreporter.tribler.org/ec03pub.pem').read()
#            if proxy03_keypair != '':
#                tmpfile = open(os.path.join(self.utility.session.get_state_dir(),"Proxy90secondsTestTemporaryPermidKey03"), "w")
#                tmpfile.write(proxy03_keypair)
#                tmpfile.close()
#                proxy03_ec_keypair = M2Crypto.EC.load_pub_key(os.path.join(self.utility.session.get_state_dir(),"Proxy90secondsTestTemporaryPermidKey03"))
#                proxy03_permid = str(proxy03_ec_keypair.pub().get_der())
#                # set proxy03 ip address
#                proxy03_ip = "95.211.105.71"
##                proxy03_ip = "141.85.224.209"
##                proxy03_ip = "10.38.165.170"
#                # set proxy03 port
#                proxy03_port = 25123
#                # add proxy03 as a peer
#                peerdb = self.utility.session.open_dbhandler(NTFY_PEERS)
#                peer = {}
#                peer['permid'] = proxy03_permid
#                peer['ip'] = proxy03_ip
#                peer['port'] = proxy03_port
#                peer['last_seen'] = 0
#                peerdb.addPeer(peer['permid'], peer, update_dns=True, commit=True)
#                
#                # Delete the temporary key file 
#                os.remove(os.path.join(self.utility.session.get_state_dir(),"Proxy90secondsTestTemporaryPermidKey03"))
#
#                peerlist.append(proxy03_permid)
#
#            # add the proxy04 as a friend
#            # get proxy04 permid
#            proxy04_keypair = urllib.urlopen('http://proxytestreporter.tribler.org/ec04pub.pem').read()
#            if proxy04_keypair != '':
#                tmpfile = open(os.path.join(self.utility.session.get_state_dir(),"Proxy90secondsTestTemporaryPermidKey04"), "w")
#                tmpfile.write(proxy04_keypair)
#                tmpfile.close()
#                proxy04_ec_keypair = M2Crypto.EC.load_pub_key(os.path.join(self.utility.session.get_state_dir(),"Proxy90secondsTestTemporaryPermidKey04"))
#                proxy04_permid = str(proxy04_ec_keypair.pub().get_der())
#                # set proxy04 ip address
#                proxy04_ip = "95.211.105.73"
##                proxy04_ip = "141.85.224.210"
##                proxy04_ip = "10.38.242.17"
#                # set proxy04 port
#                proxy04_port = 25123
#                # add proxy04 as a peer
#                peerdb = self.utility.session.open_dbhandler(NTFY_PEERS)
#                peer = {}
#                peer['permid'] = proxy04_permid
#                peer['ip'] = proxy04_ip
#                peer['port'] = proxy04_port
#                peer['last_seen'] = 0
#                peerdb.addPeer(peer['permid'], peer, update_dns=True, commit=True)
#                
#                # Delete the temporary key file 
#                os.remove(os.path.join(self.utility.session.get_state_dir(),"Proxy90secondsTestTemporaryPermidKey04"))
#
#                peerlist.append(proxy04_permid)
#
#            # Start the 90s test download
#            guiUtility = GUIUtility.getInstance()
#            d = guiUtility.frame.startDownload(tdef = torrent_def, proxymode=PROXY_MODE_PRIVATE)
#            d.ask_coopdl_helpers(peerlist)
#     
#            # 300s = 5 minutes
#            t = NamedTimer(300, self.del_dl)
#            t.start()
#        # _ProxyService 90s Test
#
#    # ProxyService 90s Test_
#    def del_dl(self):
#        guiUtility = GUIUtility.getInstance()
#        torrentManager = guiUtility.torrentsearch_manager
#        dlist = guiUtility.utility.session.get_downloads()
#        for d in dlist:
#            safename = `d.get_def().get_name()`
#            if safename == "'Data.90s-test.8M.bin'":
#                guiUtility.utility.session.remove_download(d, removecontent=True)
#                torrentManager.mypref_db.deletePreference(d.get_def().get_infohash())
#                wx.CallAfter(guiUtility.frame.librarylist.GetManager().refresh)
#
#        from Tribler.Core.Statistics.Status.Status import get_status_holder
#        status = get_status_holder("Proxy90secondsTest")
#        status.create_and_add_event("deleted-90s-test", [True])
#
#        # Mark test as inactive
#        session = Session.get_instance()
#        session.set_90stest_state(False)
#    # _ProxyService 90s Test

    def __do_layout(self):
        mainSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        #Add searchbox etc.
        searchSizer = wx.BoxSizer(wx.VERTICAL)

        #Search for files or channels label
        searchSizer.Add(self.files_friends, 0, wx.TOP, 20) 
        if sys.platform == 'win32': #platform specific spacer
            searchSizer.AddSpacer((0, 6))
        else:
            searchSizer.AddSpacer((0, 3))
        
        searchBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        searchBoxSizer.Add(self.searchField, 1, wx.TOP, 1) #add searchbox
        searchBoxSizer.Add(self.go, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5) #add searchbutton

        if sys.platform == 'darwin' or sys.platform == 'win32':
            ag_fname = os.path.join(self.utility.getPath(), LIBRARYNAME, 'Main', 'vwxGUI', 'images', 'search_new_windows.gif')
        else:
            ag_fname = os.path.join(self.utility.getPath(), LIBRARYNAME, 'Main', 'vwxGUI', 'images', 'search_new.gif')
        self.ag = wx.animate.GIFAnimationCtrl(self, -1, ag_fname)
        self.ag.Hide()
        
        searchBoxSizer.Add(self.ag, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RESERVE_SPACE_EVEN_IF_HIDDEN, 3)
        searchSizer.Add(searchBoxSizer, 0, wx.EXPAND)
        
        #finished searchSizer, add to mainSizer
        mainSizer.Add(searchSizer, 0, wx.LEFT, 10)
        
        #niels: add strechingspacer, all controls added before 
        #this spacer will be aligned to the left of the screen
        #all controls added after, will be to the right
        mainSizer.AddStretchSpacer()
        
        #add buttons
        self.buttonSizer = wx.BoxSizer(wx.VERTICAL)
        
        #add buttons horizontally
        buttonBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        buttonBoxSizer.Add(self.home, 0, wx.RIGHT, 5)
        buttonBoxSizer.Add(self.results, 0, wx.RIGHT, 5)
        buttonBoxSizer.Add(self.channels, 0, wx.RIGHT, 5)
        buttonBoxSizer.Add(self.settings, 0, wx.RIGHT, 5)
        buttonBoxSizer.Add(self.my_files)
        
        self.buttonSizer.Add(buttonBoxSizer, 0, wx.TOP, 3)
        
        self.notifyPanel = wx.Panel(self)
        self.notifyPanel.SetBackgroundColour("yellow")
        self.notifyIcon = wx.StaticBitmap(self.notifyPanel, -1, wx.ArtProvider.GetBitmap(wx.ART_INFORMATION))
        self.notify = wx.StaticText(self.notifyPanel)
        
        notifyS = wx.BoxSizer(wx.HORIZONTAL)
        notifyS.Add(self.notifyIcon, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 5)
        notifyS.Add(self.notify, 1, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)
        self.notifyPanel.SetSizer(notifyS)
        self.notifyPanel.Hide()
        
        self.buttonSizer.Add(self.notifyPanel, 0, wx.ALIGN_RIGHT | wx.TOP, 5)
        mainSizer.Add(self.buttonSizer)
        
        mainSizer.AddSpacer((15, 0))
        
        mainSizer.Add(self.tribler_logo2, 0, wx.TOP, 3)
        mainSizer.AddSpacer((10, 0))
        self.SetSizer(mainSizer)
    
    def OnResize(self, event):
        self.Refresh()
        event.Skip()
    
    def Notify(self, msg, icon= -1):
        self.notify.SetLabel(msg)
        self.notify.SetSize(self.notify.GetBestSize())
        
        if icon != -1:
            self.notifyIcon.Show()
            self.notifyIcon.SetBitmap(wx.ArtProvider.GetBitmap(icon, wx.ART_FRAME_ICON))
        else:
            self.notifyIcon.Hide()
        
        self.Freeze()
        self.notifyPanel.Show()
        #NotifyLabel size changed, thus call Layout
        self.buttonSizer.Layout()
        self.Thaw()
        
        wx.CallLater(5000, self.HideNotify)

    def HideNotify(self):
        self.notifyPanel.Hide()
        
    def HideAnimation(self):
        self.ag.Stop()
        self.ag.Hide()

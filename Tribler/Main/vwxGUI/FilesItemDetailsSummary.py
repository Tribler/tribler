# Written by Jelle Roozenburg, Richard Gwin
# see LICENSE.txt for license information

import wx
import sys

from Tribler.Core.Overlay.MetadataHandler import get_filename
from Tribler.Core.simpledefs import *
from Tribler.Core.Utilities.utilities import *
from Tribler.Core.TorrentDef import TorrentDef

from Tribler.Main.vwxGUI.tribler_topButton import tribler_topButton, SwitchButton, TestButton
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.TriblerStyles import TriblerStyles
from Tribler.Main.vwxGUI.bgPanel import *
from Tribler.Main.globals import DefaultDownloadStartupConfig,get_default_dscfg_filename
from font import *

from Tribler.Video.VideoPlayer import VideoPlayer
from Tribler.Video.utils import videoextdefaults
from Tribler.__init__ import LIBRARYNAME




# font sizes
if sys.platform == 'darwin':
    FS_PLAYTEXT = 10
    FS_SAVETEXT = 10
    FS_TORRENT = 9
    FS_BELONGS_TO_CHANNEL = 7

elif sys.platform == 'linux2':
    FS_PLAYTEXT = 7
    FS_SAVETEXT = 7
    FS_TORRENT = 9
    FS_BELONGS_TO_CHANNEL = 6

else: # windows
    FS_PLAYTEXT = 7
    FS_SAVETEXT = 7
    FS_TORRENT = 9
    FS_BELONGS_TO_CHANNEL = 6


class FilesItemDetailsSummary(bgPanel):
    
    def __init__(self, parent, torrentHash, torrent, web2data = None):
        wx.Panel.__init__(self, parent, -1)

        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility   
        self.session = self.utility.session

        self.vcdb = self.utility.session.open_dbhandler(NTFY_VOTECAST)
        self.chdb = self.utility.session.open_dbhandler(NTFY_CHANNELCAST)
        self.torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)


        self.fileList = None

        self.currentPage=0
        self.lastPage=0
        self.totalItems=0
        self.filesPerPage=3
        self.fileSpacing=(0,5) # space between files
        self.fileLength=50
        self.fileColour=(255,51,0)
        self.fileColourSel=(0,105,156)
 
        # list of files within the torrent
        self.files=[] 


        #self.refreshScrollButtons()


        self.infohash = torrentHash
        self.torrent = torrent
        self.torrenthash = torrentHash

        self.addComponents()


        self.tile = True
        self.backgroundColour = wx.Colour(102,102,102)
        self.searchBitmap('blue_long.png')
        self.createBackgroundImage()


        self.gridmgr = parent.parent.getGridManager()

        self.Refresh(True)
        self.Update()

        
        
    def addComponents(self):
        self.triblerStyles = TriblerStyles.getInstance()
        ##self.SetMinSize((300,40))

        self.hSizer0 = wx.BoxSizer(wx.HORIZONTAL)               
        self.hSizer1 = wx.BoxSizer(wx.HORIZONTAL)               
        self.hSizermain = wx.BoxSizer(wx.HORIZONTAL)               
        
        self.vSizer = wx.BoxSizer(wx.VERTICAL)               



        # belongs to channel text
        self.belongstochanneltext = wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(180,14))        
        self.belongstochanneltext.SetBackgroundColour((216, 233, 240))
        self.belongstochanneltext.SetForegroundColour((100,100,100))
        self.belongstochanneltext.SetFont(wx.Font(FS_BELONGS_TO_CHANNEL,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.belongstochanneltext.SetMinSize((180,14))


        channel = self.chdb.getMostPopularChannelFromTorrent(self.torrenthash)
        if channel is not None:
            self.belongstochanneltext.SetLabel("From %s's Channel" % channel)





        self.vSizer.Add([0,0], 0, wx.BOTTOM|wx.FIXED_MINSIZE, 0)
        self.vSizer.Add(self.belongstochanneltext, 0, wx.LEFT, 5)



        # vSizerLeft
        self.vSizerLeft = wx.BoxSizer(wx.VERTICAL)
       
        # vSizerRight
        self.vSizerRight = wx.BoxSizer(wx.VERTICAL)

        # vSizerContents
        self.vSizerContents = wx.BoxSizer(wx.VERTICAL) ## list of items within a particular channel
        self.vSizerContents.SetMinSize((470,30))


        # scroll left
        self.scrollLeft = tribler_topButton(self, -1, name = "ScrollLeft")
        self.scrollLeft.createBackgroundImage()  
        self.scrollLeft.Bind(wx.EVT_LEFT_UP, self.scrollLeftClicked)      
        self.scrollLeft.Hide()

 
        # scroll right
        self.scrollRight = tribler_topButton(self, -1, name = "ScrollRight")
        self.scrollRight.createBackgroundImage()        
        self.scrollRight.Bind(wx.EVT_LEFT_UP, self.scrollRightClicked)      
        self.scrollRight.Hide()




        self.download = tribler_topButton(self, -1, name='save_medium')
        self.download.SetMinSize((62,32))
        self.download.SetSize((62,32))
        self.download.Hide()

        self.play_big = SwitchButton(self, -1, name='playbig')
        self.play_big.setToggled(False) # default
        self.play_big.Bind(wx.EVT_LEFT_UP, self.playbig_clicked)
        self.play_big.Hide()



        self.play_big.SetPosition((580,20))
        self.download.SetPosition((615,28))



        # loading gif
        ag_fname = os.path.join(self.utility.getPath(),LIBRARYNAME,'Main','vwxGUI','images','5.0','fids.gif')
        self.ag = wx.animate.GIFAnimationCtrl(self, -1, ag_fname)
        if sys.platform == 'darwin':
            wx.CallAfter(self.ag.Play)
        else:
            self.ag.Play()

        #self.vSizer2 = wx.BoxSizer(wx.VERTICAL)
        #self.vSizer2.Add([0,10], 0, wx.FIXED_MINSIZE, 0)
        #self.vSizer2.Add(self.play_big, 0, wx.FIXED_MINSIZE, 4)
        
        #self.vSizer3 = wx.BoxSizer(wx.VERTICAL)
        #self.vSizer3.Add([0,18], 0, wx.FIXED_MINSIZE, 0)
        #self.vSizer3.Add(self.download, 0, wx.FIXED_MINSIZE, 4)

            
        self.vSizerLeft.Add((0,3), 0, 0, 0)
        self.vSizerLeft.Add(self.scrollLeft, 0, 0, 0)

        self.vSizerRight.Add((0,3), 0, 0, 0)
        self.vSizerRight.Add(self.scrollRight, 0, 0, 0)



        self.hSizer0.Add((20,80), 0, 0, 0)
        self.hSizer0.Add(self.vSizerLeft, 0, 0, 0)
        self.hSizer0.Add((10,0), 0, 0, 0)
        self.hSizer0.Add(self.vSizerContents, 0, wx.TOP, 0)
        self.hSizer0.Add((10,0), 0, 0, 0)
        self.hSizer0.Add(self.vSizerRight, 0, 0, 0)
        #self.hSizer0.Add((80,0), 0, 0, 0)
        #self.hSizer0.Add(self.vSizer2, 0, 0, 0)
        #self.hSizer0.Add((3,0), 0, 0, 0)
        #self.hSizer0.Add(self.vSizer3, 0, 0, 0)




        self.hSizer1.Add((300,0), 0, 0, 0)
        self.hSizer1.Add(self.ag, 0, 0, 0)

        self.hSizermain.Add(self.hSizer1, 0, 0, 0)
        self.hSizermain.Add(self.hSizer0, 0, 0, 0)
        
        self.vSizer.Add(self.hSizermain, 0, 0, 0)


        self.SetSizer(self.vSizer)
        self.SetAutoLayout(1);  
        self.Layout()



        def is_playable_callback(torrent, playable):
            self.setPlayableStatus(playable)
              

        playable = self.guiUtility.standardDetails.torrent_is_playable(callback=is_playable_callback)
        self.setPlayableStatus(playable)



    def setPlayableStatus(self, playable):
        """ Three playablestatus options : 
        1 : Torrent is not playable
        2 : Torrent is playable and contains 1 file
        3 : Torrent is playable and contains multiple files
        """
        if playable[0]:
            self.play_big.Show()
            self.download.Show()
            self.fileList=playable[1]
            if len(self.fileList) == 1: # torrent contains only one file
                self.play_big.setToggled(True)
                self.scrollLeft.Hide()
                self.scrollRight.Hide()
            else:
                self.loadTorrent(self.fileList)
                self.scrollLeft.Show()
                self.scrollRight.Show()
            if sys.platform == 'darwin':
                wx.CallAfter(self.ag.Stop)
                wx.CallAfter(self.ag.Hide)
            else:
                self.ag.Stop()
                self.ag.Hide()
            self.hSizermain.Detach(0)
            self.hSizermain.Layout()
            self.vSizer.Layout()
            self.Layout()
            self.Refresh()
        else: # torrent is not playable   
            self.scrollLeft.Hide()
            self.scrollRight.Hide()


    def loadTorrent(self, files):
        self.totalItems = len(files)
        self.setLastPage()
        self.addItems(files)
        #self.erasevSizerContents
        self.displayTorrentContents()
        self.Refresh()


    def addItems(self, files):
        for i in range(self.totalItems):
            ##item = wx.StaticText(self, -1, files[i], wx.Point(0,0), wx.Size(300,14))
            ##self.files.append(item)
            ##self.files[i].SetFont(wx.Font(FS_TORRENT,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
            ##self.files[i].Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction(i))
            ##self.files[i].SetToolTipString(self.fileList[i]['name'][:self.fileLength])
            ##self.files[i].SetForegroundColour(self.fileColour)


            item = fileItem(self)
            item.setSummary(self)
            item.setTitle(files[i])
            self.files.append(item)
            self.files[i].Hide()





    def displayTorrentContents(self):
        if self.currentPage == self.lastPage:
            numItems = self.totalItems % self.filesPerPage
            if numItems == 0:
                numItems = self.filesPerPage
        else:
            numItems = self.filesPerPage    

        for i in range(numItems):
            self.vSizerContents.Add(self.files[self.currentPage*self.filesPerPage+i], 0, 0, 0)
            self.files[self.currentPage*self.filesPerPage+i].Show()
            # self.vSizerContents.Add(self.torrentSpacing, 0, 0, 0)
        self.vSizerContents.Layout()
        self.hSizer0.Layout()
        self.vSizer.Layout()
        self.refreshScrollButtons()
        self.Layout()
        self.Refresh()




    def erasevSizerContents(self):
        if self.currentPage == self.lastPage:
            numItems = self.totalItems % self.filesPerPage
        else:
            numItems = self.filesPerPage    
        for i in range(numItems):
            self.files[self.currentPage*self.filesPerPage+i].Hide()
        self.vSizerContents.Clear()
        self.vSizerContents.Layout()
        self.hSizer0.Layout()
        self.Layout()



    def setLastPage(self, lastPage=None):
        if lastPage is None:
            if self.totalItems % self.filesPerPage == 0:
                self.lastPage = self.totalItems / self.filesPerPage - 1
            else:
                self.lastPage = (self.totalItems - self.totalItems % self.filesPerPage) / self.filesPerPage
        else:
            self.lastPage=lastPage




    def refreshScrollButtons(self):
        self.scrollLeft.setSelected(self.currentPage==0)
        self.scrollRight.setSelected(self.currentPage==self.lastPage)


    def scrollLeftClicked(self, event):
        if self.currentPage > 0:
            self.erasevSizerContents()
            self.currentPage = self.currentPage - 1
            self.displayTorrentContents()



    def scrollRightClicked(self, event):
        if self.currentPage < self.lastPage:
            self.erasevSizerContents()
            self.currentPage = self.currentPage + 1
            self.displayTorrentContents()



    def playbig_clicked(self,event):
        if self.play_big.isToggled():

            ds = self.torrent.get('ds')

            videoplayer = self._get_videoplayer(exclude=ds) 
            videoplayer.stop_playback() # stop current playback
            videoplayer.show_loading()

            ##self.play_big.setToggled()
            ##self.guiUtility.buttonClicked(event)
            if ds is None:
                self.guiUtility.standardDetails.download(vodmode=True)
            else:
                self.play(ds)

            self.guiUtility.standardDetails.setVideodata(self.guiUtility.standardDetails.getData())
            self._get_videoplayer(exclude=ds).videoframe.get_videopanel().SetLoadingText(self.guiUtility.standardDetails.getVideodata()['name'])
            if sys.platform == 'darwin':
                self._get_videoplayer(exclude=ds).videoframe.show_videoframe()
                self._get_videoplayer(exclude=ds).videoframe.get_videopanel().Refresh()
                self._get_videoplayer(exclude=ds).videoframe.get_videopanel().Layout()

    def play(self,ds):


        self._get_videoplayer(exclude=ds).play(ds)


    def _get_videoplayer(self, exclude=None):
        """
        Returns the VideoPlayer instance and ensures that it knows if
        there are other downloads running.
        """
        other_downloads = False
        for ds in self.gridmgr.get_dslist():
            if ds is not exclude and ds.get_status() not in (DLSTATUS_STOPPED, DLSTATUS_STOPPED_ON_ERROR):
                other_downloads = True
                break
        
        videoplayer = VideoPlayer.getInstance()
        videoplayer.set_other_downloads(other_downloads)
        return videoplayer



class fileItem(wx.Panel):
    def __init__(self, *args,**kwds):
        if len(args) == 0:
            pre = wx.PrePanel()
            # the Create step is done by XRC.
            self.PostCreate(pre)
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)
        else:
            wx.Panel.__init__(self, *args)
            self._PostInit()
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    
    def _PostInit(self):
         # Do all init here
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility        
        self.fileColour=(255,51,0)
        self.fileColourSel=(0,105,156)


        if sys.platform == 'win32':
            self.minsize=(460,17)
        elif sys.platform == 'linux2':
            self.minsize=(460,17)
        else:
            self.minsize=(460,19)



        self.SetMinSize(self.minsize)
        self.selected=False
        self.addComponents()
        self.SetBackgroundColour((216, 233, 240))
        self.Refresh()


    def addComponents(self):
        # hSizer
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)

        # file title
        self.title = wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(self.minsize[0]-30, self.minsize[1]))
        self.title.SetFont(wx.Font(FS_TORRENT,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))        
        self.title.SetForegroundColour(self.fileColour)
        self.title.SetMinSize((self.minsize[0]-30, self.minsize[1]))

        # play button
        self.play = tribler_topButton(self, -1, name='fids_play')
        self.play.mouseOver = False
        self.play.Refresh()

        self.hSizer.Add(self.play, 0, 0, 0)
        self.hSizer.Add((10,0), 0, 0, 0)
        self.hSizer.Add(self.title, 0, 0, 0)

        self.SetSizer(self.hSizer)
        self.SetAutoLayout(1)
        self.Layout()
        self.Refresh()

        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
        wl = []
        for c in self.GetChildren():
            wl.append(c)
        for window in wl:
            window.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        if sys.platform != 'linux2':
            self.title.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)


    def setTitle(self, title):
        self.title.SetToolTipString(title) 
        i=0
        try:
            while self.title.GetTextExtent(title[:i])[0] < self.minsize[0]-30 and i <= len(title):
                i=i+1
            self.title.SetLabel(title[:(i-1)])
        except:
            self.title.SetLabel(title)
        self.Refresh()       


    def mouseAction(self, event):
        event.Skip()

        if event.Entering():
            self.title.SetForegroundColour(self.fileColourSel)
            self.play.mouseOver = True
            self.play.Refresh()
            self.hSizer.Layout()
        elif event.Leaving():
            self.title.SetForegroundColour(self.fileColour)
            self.play.mouseOver = False
            self.play.Refresh()
            self.hSizer.Layout()


        if event.LeftUp():
            self.play_clicked()

        self.Refresh()


    def setSummary(self, summary):
        self.summary = summary # filesitemdetailssummary


    def play_clicked(self):

        ds = self.summary.torrent.get('ds')
        selectedinfilename = self.title.GetLabel()

        if ds is not None:
            self.summary._get_videoplayer(exclude=ds).play(ds, selectedinfilename)

        else:
            torrent = self.summary.torrent
            if 'torrent_file_name' not in torrent:
                torrent['torrent_file_name'] = get_filename(torrent['infohash']) 
            torrent_dir = self.utility.session.get_torrent_collecting_dir()
            torrent_filename = os.path.join(torrent_dir, torrent['torrent_file_name'])
            tdef = TorrentDef.load(torrent_filename)

            defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
            dscfg = defaultDLConfig.copy()

            self.summary._get_videoplayer().start_and_play(tdef, dscfg, selectedinfilename)


        videoplayer = self.summary._get_videoplayer(exclude=ds) 
        videoplayer.stop_playback() # stop current playback
        videoplayer.show_loading()


        self.guiUtility.standardDetails.setVideodata(self.guiUtility.standardDetails.getData())
        self.summary._get_videoplayer(exclude=ds).videoframe.get_videopanel().SetLoadingText(self.guiUtility.standardDetails.getVideodata()['name'])
        if sys.platform == 'darwin':
            self.summary._get_videoplayer(exclude=ds).videoframe.show_videoframe()
            self.summary._get_videoplayer(exclude=ds).videoframe.get_videopanel().Refresh()
            self.summary._get_videoplayer(exclude=ds).videoframe.get_videopanel().Layout()





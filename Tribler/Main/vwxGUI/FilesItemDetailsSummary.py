import wx, os
from Tribler.Main.vwxGUI.tribler_topButton import tribler_topButton, SwitchButton, TestButton
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.TriblerStyles import TriblerStyles
## from Tribler.Main.vwxGUI.TextButton import *
from Tribler.Main.vwxGUI.bgPanel import *
from Tribler.Core.Utilities.unicode import bin2unicode

from Tribler.Video.VideoPlayer import VideoPlayer,return_feasible_playback_modes,PLAYBACKMODE_INTERNAL

from Tribler.Core.CacheDB.sqlitecachedb import bin2str
from Tribler.Main.vwxGUI.ColumnHeader import ColumnHeaderBar
## from Tribler.Main.vwxGUI.SubscriptionsItemPanel import SubscriptionsItemPanel
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.vwxGUI.GridState import GridState
from Tribler.Category.Category import Category
from Tribler.Core.simpledefs import *
from Tribler.Core.Utilities.utilities import *
from Tribler.Main.vwxGUI.SearchGridManager import SEARCHMODE_NONE, SEARCHMODE_SEARCHING, SEARCHMODE_STOPPED


class FilesItemDetailsSummary(bgPanel):
    
    def __init__(self, parent, torrentHash, torrent, web2data = None):
        wx.Panel.__init__(self, parent, -1)

        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility   
        self.mcdb = self.utility.session.open_dbhandler(NTFY_MODERATIONCAST)
        self.vcdb = self.utility.session.open_dbhandler(NTFY_VOTECAST)

        self.session = self.utility.session
        self.torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)


        self.infohash = torrentHash
        self.torrent = torrent

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
        
        self.vSizer = wx.BoxSizer(wx.VERTICAL)               

        ## text information

        ##self.Seeders = wx.StaticText(self,-1,"Seeders:",wx.Point(0,0),wx.Size(125,22))     
        ##self.Seeders.SetMinSize((125,14))
        ##self.triblerStyles.setDarkText(self.Seeders)

        ##self.NumSeeders = wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(125,22))     
        ##self.NumSeeders.SetMinSize((125,14))
        ##self.triblerStyles.setDarkText(self.NumSeeders)
        ##self.NumSeeders.SetLabel('%s' % self.torrent['num_seeders'])
        

        ##self.Leechers = wx.StaticText(self,-1,"Leechers:",wx.Point(0,0),wx.Size(125,22))     
        ##self.Leechers.SetMinSize((125,14))
        ##self.triblerStyles.setDarkText(self.Leechers)

        ##self.NumLeechers = wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(125,22))     
        ##self.NumLeechers.SetMinSize((125,14))
        ##self.triblerStyles.setDarkText(self.NumLeechers)
        ##self.NumLeechers.SetLabel('%s' % self.torrent['num_leechers'])

        self.Popularity = wx.StaticText(self,-1,"Popularity:",wx.Point(0,0),wx.Size(125,22))     
        self.Popularity.SetMinSize((125,14))
        self.triblerStyles.setDarkText(self.Popularity)    

        self.Popularity_info = wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(125,22))     
        self.Popularity_info.SetMinSize((125,14))
        self.triblerStyles.setDarkText(self.Popularity_info)
        pop = self.torrent['num_seeders'] + self.torrent['num_leechers']    
        if pop > 0:
            if pop == 1:
                self.Popularity_info.SetLabel('%s person' %(pop))
            else: 
                self.Popularity_info.SetLabel('%s people' %(pop))
        else: 
            self.Popularity_info.SetLabel('unknown')


        ##self.TriblerSources = wx.StaticText(self,-1,"Tribler sources:",wx.Point(0,0),wx.Size(125,22))     
        ##self.TriblerSources.SetMinSize((125,14))
        ##self.triblerStyles.setDarkText(self.TriblerSources)

        self.CreationDate = wx.StaticText(self,-1,"Creation date:",wx.Point(0,0),wx.Size(125,22))     
        self.CreationDate.SetMinSize((125,14))
        self.triblerStyles.setDarkText(self.CreationDate)

        self.CreationDate_info = wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(125,22))     
        self.CreationDate_info.SetMinSize((125,14))
        self.triblerStyles.setDarkText(self.CreationDate_info)
        self.CreationDate_info.SetLabel(friendly_time(self.torrent['creation_date']))

        self.ModeratorName = wx.StaticText(self,-1,"Moderated by: ",wx.Point(0,0),wx.Size(125,22))     
        self.ModeratorName.SetMinSize((125,14))
        self.triblerStyles.setLightText(self.ModeratorName)

        self.ModeratorName_info = wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(125,22))     
        self.ModeratorName_info.SetMinSize((125,14))
        self.triblerStyles.setLightText(self.ModeratorName_info)


        ## hSizer2
        self.hSizer2 = wx.BoxSizer(wx.HORIZONTAL)
        


        # check for moderation
        if self.infohash is not None and self.mcdb.hasModeration(bin2str(self.infohash)):
            moderation = self.mcdb.getModeration(bin2str(self.infohash))
            mod_name = moderation[1]
            
            # If the moderator is himself, he should not be able to rate the file properties
            if moderation[0] != bin2str(self.session.get_permid()):
                self.Rate = wx.StaticText(self,-1,"Rate these file properties as ",wx.Point(0,0),wx.Size(160,22))
                self.triblerStyles.setLightText(self.Rate)
                self.Or = wx.StaticText(self,-1," or",wx.Point(0,0),wx.Size(25,22))
                self.triblerStyles.setLightText(self.Or)
    
                self.fake = TestButton(self, -1, name='fake')
                self.fake.SetMinSize((35,16))
                self.fake.SetSize((35,16))
                self.guiUtility.fakeButton = self.fake
    
                self.real = TestButton(self, -1, name='real')
                self.real.SetMinSize((35,16))
                self.real.SetSize((35,16))
                self.guiUtility.realButton = self.real
    
                self.hSizer2.Add(self.Rate,0,wx.LEFT|wx.FIXED_MINSIZE,0)
                self.hSizer2.Add(self.fake,0,wx.LEFT|wx.FIXED_MINSIZE,5)
                self.hSizer2.Add(self.Or,0,wx.LEFT|wx.FIXED_MINSIZE,5)
                self.hSizer2.Add(self.real,0,wx.LEFT|wx.FIXED_MINSIZE,5)

        else:
            mod_name = "None"
            # disable fake and real buttons
            ##self.fake.setState(False)
            ##self.real.setState(False)

        self.ModeratorName_info.SetLabel(mod_name)

        self.vSizer.Add([0,10], 0, wx.BOTTOM|wx.FIXED_MINSIZE, 0)

        ##self.hSizer3 = wx.BoxSizer(wx.HORIZONTAL)
        ##self.hSizer3.Add(self.Seeders,0,wx.FIXED_MINSIZE,5)
        ##self.hSizer3.Add(self.NumSeeders,0,wx.FIXED_MINSIZE,5)
        ##self.vSizer.Add(self.hSizer3,0,wx.LEFT|wx.FIXED_MINSIZE,5)

        ##self.vSizer.Add([0,2], 0, wx.BOTTOM|wx.FIXED_MINSIZE, 0)

        self.hSizer4 = wx.BoxSizer(wx.HORIZONTAL)
        ##self.hSizer4.Add(self.Leechers,0,wx.FIXED_MINSIZE,5)
        ##self.hSizer4.Add(self.NumLeechers,0,wx.FIXED_MINSIZE,5)
        self.hSizer4.Add(self.Popularity,0,wx.FIXED_MINSIZE,5)
        self.hSizer4.Add(self.Popularity_info,0,wx.FIXED_MINSIZE,5)
        self.vSizer.Add(self.hSizer4,0,wx.LEFT|wx.FIXED_MINSIZE,5)

        ##self.vSizer.Add([0,2], 0, wx.BOTTOM|wx.FIXED_MINSIZE, 0)
        ##self.vSizer.Add(self.TriblerSources,0,wx.LEFT|wx.FIXED_MINSIZE,5)
        ##self.vSizer.Add([0,2], 0, wx.BOTTOM|wx.FIXED_MINSIZE, 0)

        self.hSizer5 = wx.BoxSizer(wx.HORIZONTAL)
        self.hSizer5.Add(self.CreationDate,0,wx.FIXED_MINSIZE,5)
        self.hSizer5.Add(self.CreationDate_info,0,wx.FIXED_MINSIZE,5)
        self.vSizer.Add(self.hSizer5,0,wx.LEFT|wx.FIXED_MINSIZE,5)


        ##self.vSizer.Add([0,20], 0, wx.BOTTOM|wx.FIXED_MINSIZE, 0)
        self.vSizer.Add(self.hSizer2,0,wx.LEFT|wx.FIXED_MINSIZE,5)
        self.vSizer.Add([0,2], 0, wx.BOTTOM|wx.FIXED_MINSIZE, 0)

        self.hSizer7 = wx.BoxSizer(wx.HORIZONTAL)
        self.hSizer7.Add(self.ModeratorName,0,wx.FIXED_MINSIZE,5)
        self.hSizer7.Add(self.ModeratorName_info,0,wx.FIXED_MINSIZE,5)
        self.vSizer.Add(self.hSizer7,0,wx.LEFT|wx.FIXED_MINSIZE,5)

        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)               

        self.hSizer.Add([20,10], 0, wx.BOTTOM|wx.FIXED_MINSIZE, 1)

        ##self.save = wx.StaticText(self,-1,"save",wx.Point(0,0),wx.Size(50,22))     
        ##self.save.SetMinSize((50,14))
        ##self.save.SetForegroundColour(wx.RED)



        self.download = tribler_topButton(self, -1, name='download')
        self.download.SetMinSize((20,20))
        self.download.SetSize((20,20))

        ##self.select_files = tribler_topButton(self, -1, name='select_files')
        ##self.select_files.SetMinSize((148,16))
        ##self.select_files.SetSize((148,16))

        ##self.view_related_files = tribler_topButton(self, -1, name='view_related_files')
        ##self.view_related_files.SetMinSize((116,16))
        ##self.view_related_files.SetSize((116,16))
  
        ##self.edit = tribler_topButton(self, -1, name='edit')
        ##self.edit.SetMinSize((40,16))
        ##self.edit.SetSize((40,16))


        self.hSizer.Add(self.vSizer, 0, wx.FIXED_MINSIZE, 10)


        self.play_big = SwitchButton(self, -1, name='playbig')
        self.play_big.setToggled(True)
        self.play_big.Bind(wx.EVT_LEFT_UP, self.playbig_clicked)

        def is_playable_callback(torrent, playable):
            print >> sys.stderr, "PLAYABLE : " , playable
            self.play_big.setToggled(playable)

        if not self.guiUtility.standardDetails.torrent_is_playable(callback=is_playable_callback):

            self.play_big.setToggled(False)
            

        self.vSizer2 = wx.BoxSizer(wx.VERTICAL)
        self.vSizer2.Add([0,20], 0, wx.FIXED_MINSIZE, 0)
        self.vSizer2.Add(self.play_big, 0, wx.FIXED_MINSIZE, 4)
                

        self.vSizer3 = wx.BoxSizer(wx.VERTICAL)
        self.vSizer3.Add([0,37], 0, wx.FIXED_MINSIZE, 0)
        self.vSizer3.Add(self.download, 0, wx.FIXED_MINSIZE, 4)




        
        ##self.vSizer = wx.BoxSizer(wx.VERTICAL)  
        ##self.hSizer.Add(self.vSizer, 0, wx.TOP, 25) 
        
        ##self.downloading = self.data and self.data.get('myDownloadHistory')
        
        self.hSizer0.Add(self.hSizer, 1, wx.EXPAND , 10)
        self.hSizer0.Add(self.vSizer2, 0 , wx.FIXED_MINSIZE , 4)
        self.hSizer0.Add([10,0], 0, wx.FIXED_MINSIZE, 0)
        self.hSizer0.Add(self.vSizer3, 0 , wx.FIXED_MINSIZE , 4)
        self.hSizer0.Add([50,10], 0, wx.FIXED_MINSIZE, 0)

        self.SetSizer(self.hSizer0)
        self.SetAutoLayout(1);  
        self.Layout()





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


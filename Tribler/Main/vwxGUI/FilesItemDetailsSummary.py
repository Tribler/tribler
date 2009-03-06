import wx, os
from Tribler.Main.vwxGUI.tribler_topButton import tribler_topButton, SwitchButton, TestButton
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.TriblerStyles import TriblerStyles
from Tribler.Main.vwxGUI.TextButton import *
from Tribler.Main.vwxGUI.bgPanel import *
from Tribler.Core.Utilities.unicode import bin2unicode

from Tribler.Video.VideoPlayer import VideoPlayer,return_feasible_playback_modes,PLAYBACKMODE_INTERNAL

from Tribler.Core.CacheDB.sqlitecachedb import bin2str
from Tribler.Main.vwxGUI.ColumnHeader import ColumnHeaderBar
from Tribler.Main.vwxGUI.SubscriptionsItemPanel import SubscriptionsItemPanel
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
        self.play_big.Bind(wx.EVT_LEFT_UP, self.playbig_clicked)

        def is_playable_callback(torrent, playable):
            self.play_big.Show(playable)

        if not self.guiUtility.standardDetails.torrent_is_playable(callback=is_playable_callback):
            self.play_big.Hide()

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
        ds = self.torrent.get('ds')
        ##self.play_big.setToggled()
        ##self.guiUtility.buttonClicked(event)
        if ds is None:
            self.guiUtility.standardDetails.download(vodmode=True)
        else:
            self.play(ds)

    def play(self,ds):
        #self._get_videoplayer(exclude=ds).videoframe.get_videopanel().vlcwin.agVideo.Show()
        #self._get_videoplayer(exclude=ds).videoframe.get_videopanel().vlcwin.agVideo.Play()
        #self._get_videoplayer(exclude=ds).videoframe.get_videopanel().vlcwin.Refresh()

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

        
    def setDataLib(self):
        filelist = self.guiUtility.filesList(self.data)
        print 'tb > filelist = %s' % filelist
        
            
    def setDataNoLib(self):
        print 'tb > SET DATA'
        torrent = {}
        if self.data:            
            torrent = self.data
        
        #------------- DESCRIPTION --------------
        descrtxt = ''
        flag = False
        ##self.thumbSummary.setTorrent(self.Parent.data)
        if not torrent.get('web2'):
#            print 'tb > self.Parent.data = %s' % self.Parent.data

            
#            # check here if there are more than one file in the torrent is > playlist
            torrent_dir = self.utility.session.get_torrent_collecting_dir()
            torrent_filename = os.path.join(torrent_dir, torrent['torrent_file_name'])
            metadata = self.utility.getMetainfo(torrent_filename)
            
            if metadata:
#            if 'metadata' in torrent:
#                metadata = torrent['metadata']
                
                # see how many files are in the torrent
                info = metadata.get('info')
#                print 'tb > info = %s' % info
#                print 'tb > metadata = %s' % metadata
                if not info:
                    print 'tb > RETURN'
                    return {}
            
                #print metadata.get('comment', 'no comment')
                filedata = info.get('files')
            
                if filedata:
                    self.moreFileInfo.SetName('moreFileInfoPlaylist')                
                else:
                    self.moreFileInfo.SetName('moreFileInfo')                
                
                
                # - size
                if torrent.get('web2'):                    
                    self.fileSize.SetLabel('%s s' % torrent['length'])
                else:
                    self.fileSize.SetLabel(self.utility.size_format(torrent['length']))
                self.fileSize.Enable(True)
                
                # encoding
                encoding = None
                if 'encoding' in metadata and metadata['encoding'].strip():
                    encoding = metadata['encoding']

                flag = False
                for key in ['comment','comment-utf8','Description']: # reverse priority
                    if key in metadata: # If vuze torrent
                        tdescrtxt = metadata[key]
                        if key == 'comment-utf8':
                            tencoding = 'utf_8'
                        else:
                            tencoding = encoding
                        descrtxt = bin2unicode(tdescrtxt,tencoding)
                        flag = True
                if not flag:
                    if 'source' in torrent:
                        s = torrent['source']
                        if s != '':
                            if s == 'BC':
                                s = 'Received from other user'
                            descrtxt = "Source: "+s

                        flag = True
            elif 'description' in torrent:
                descrtxt = torrent['description']
                flag = True
            else:    
                descrtxt = 'Found at other Tribler user \n\nNo more info available'
                self.moreFileInfo.Hide()
                flag = True
             
            if not flag:
                if 'source' in torrent:
                    s = torrent['source']
                    if s == 'BC':
                        s = 'Received from other user'
                    descrtxt = "Source: "+s

        elif torrent.get('web2'):
            print 'tb > NO MORE INFO'
            descrtxt = 'Found at a video website \n\nNo more info available'
            self.moreFileInfo.Hide()
        
        self.Description.SetLabel(descrtxt)
        self.Description.Wrap(-1)       

        self.guiUtility.standardDetails.setDownloadbutton(torrent=torrent, item = self.download)        

            
        
class LibraryItemDetailsSummary(wx.Panel):
    
    def __init__(self, parent, torrentHash, web2data = None):
        wx.Panel.__init__(self, parent, -1)
        self.guiUtility = GUIUtility.getInstance()

        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility   

        self.addComponents()
        
        
    def addComponents(self):
        self.triblerStyles = TriblerStyles.getInstance()                
        self.SetMinSize((300,40))
#        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)               
#        
#        self.vSizer = wx.BoxSizer(wx.VERTICAL)  
#        self.hSizer.Add(self.vSizer, 0, wx.TOP, 25) 
 
        self.downloading = True ## added       
        ##self.downloading = self.data and self.data.get('myDownloadHistory')
        
        if self.downloading:
            
            self.SetMinSize((-1,100))
            # Add three hSizers to VSizer
            self.hSizer0 = wx.BoxSizer(wx.HORIZONTAL)
            self.vSizer1 = wx.BoxSizer(wx.VERTICAL)
            self.vSizer2 = wx.BoxSizer(wx.VERTICAL)
            self.vSizer3 = wx.BoxSizer(wx.VERTICAL)
            
            self.hSizer0.Add(self.vSizer1, 0, wx.FIXED|wx.EXPAND, 0)          
            self.hSizer0.Add(self.vSizer2, 1, wx.FIXED|wx.EXPAND, 0)  
            vLine = wx.StaticLine(self,-1,wx.DefaultPosition, wx.Size(1,0),wx.LI_VERTICAL)
            self.hSizer0.Add(vLine, 0, wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED, 4)                   
            self.hSizer0.Add(self.vSizer3, 0, wx.FIXED|wx.EXPAND, 0)          
            
#            self.hSizer1 = wx.BoxSizer(wx.HORIZONTAL)
#            self.hSizer2 = wx.BoxSizer(wx.HORIZONTAL)
#            self.hSizer3 = wx.BoxSizer(wx.HORIZONTAL)
#            self.vSizerOverall.Add(self.hSizer0, 0, wx.FIXED|wx.EXPAND, 0)   
#            self.vSizerOverall.Add(self.hSizer1, 0, wx.ALL|wx.EXPAND, 0)
#            self.vSizerOverall.Add(self.hSizer2, 0, wx.ALL|wx.EXPAND, 0)
#            self.vSizerOverall.Add(self.hSizer3, 0, wx.ALL|wx.EXPAND, 0)
            
            # Add thumb
            
            #self.thumbSummary = self.guiUtility.thumbnailViewer(self.Parent, 'libraryItemSummary')
            #self.thumbSummary.SetSize((125,70))
#            self.thumb = ThumbnailViewer(self, 'libraryMode')
            #self.thumbSummary.setBackground(wx.BLACK)
    #        self.thumb.SetSize(libraryModeThumbSize)
#            self.thumb.SetSize((125,70))
            #self.vSizer1.Add(self.thumbSummary, 0, wx.TOP, 25)
            
            # Status message
            self.statusField = wx.StaticText(self, -1,'-0-', wx.Point(),wx.Size())
            self.triblerStyles.setDarkText(self.statusField)
            self.statusField.SetMinSize((60,12))
            self.vSizer2.Add(self.statusField, 1, wx.TOP|wx.LEFT, 4)
            
            
            self.buttonsSizer = wx.BoxSizer(wx.HORIZONTAL)
            
            # Boost button
            self.boost = SwitchButton(self, name="boost")
            self.boost.setBackground(wx.WHITE)
            self.boost.SetSize((50,16))
            self.boost.setEnabled(False)
            self.buttonsSizer.Add(self.boost, 0, wx.TOP|wx.RIGHT|wx.ALIGN_RIGHT, 2)
           
            # Play Fast
            self.playFast = SwitchButton(self, name="playFast")
            self.playFast.setBackground(wx.WHITE)
            self.playFast.SetSize((39,16))
            self.playFast.setEnabled(False)
            self.buttonsSizer.Add(self.playFast, 0, wx.TOP|wx.ALIGN_RIGHT, 2)
            
            # Add buttons
            self.download = tribler_topButton(self, -1, name='download1')
            self.download.SetMinSize((20,20))
            self.download.SetSize((20,20))
            self.play = tribler_topButton(self, -1, name='play1')
            self.play.SetMinSize((20,20))
            self.play.SetSize((20,20))
            self.playAdd = tribler_topButton(self, -1, name='playAdd1')
            self.playAdd.SetMinSize((20,20))
            self.playAdd.SetSize((20,20))
    
    #        self.buttonsSizer.Add([2,20],1,wx.EXPAND|wx.FIXED_MINSIZE,0) 
            self.buttonsSizer.Add(self.download,0,wx.RIGHT|wx.FIXED_MINSIZE,4)
            self.buttonsSizer.Add(self.play,0,wx.RIGHT|wx.FIXED_MINSIZE,4)
            self.buttonsSizer.Add(self.playAdd,0,wx.RIGHT|wx.FIXED_MINSIZE,4)
            
    #        self.vSizer1.Add([2,20],1,wx.EXPAND|wx.FIXED_MINSIZE,0) 
            self.vSizer2.Add(self.buttonsSizer, 0, wx.RIGHT|wx.ALIGN_RIGHT|wx.ALIGN_BOTTOM, 2)
            
            # Up/Down text speed
            self.downSizer = wx.BoxSizer(wx.HORIZONTAL)
            self.upSizer = wx.BoxSizer(wx.HORIZONTAL)
            
            
            self.downSpeed = ImagePanel(self, -1, wx.DefaultPosition, wx.Size(16,16),name='downSpeed')
    #        self.downSpeed.setBackground(wx.WHITE)
            self.downSpeed.SetToolTipString(self.utility.lang.get('down'))
            self.speedDown2 = wx.StaticText(self,-1,"down: 0 KB/s",wx.Point(274,3),wx.Size(70,12),wx.ALIGN_RIGHT | wx.ST_NO_AUTORESIZE)                                
            self.triblerStyles.setDarkText(self.speedDown2)        
            self.speedDown2.SetMinSize((70,12))        
            self.upSpeed = ImagePanel(self, -1, wx.DefaultPosition, wx.Size(16,16),name='upSpeed')
    #        self.upSpeed.setBackground(wx.WHITE)
            self.upSpeed.SetToolTipString(self.utility.lang.get('up'))
            self.speedUp2   = wx.StaticText(self,-1,"up: 0 KB/s",wx.Point(274,3),wx.Size(70,12),wx.ALIGN_RIGHT | wx.ST_NO_AUTORESIZE)                        
            self.triblerStyles.setDarkText(self.speedUp2)
            self.speedUp2.SetMinSize((70,12))
    
            self.downSizer.Add(self.downSpeed, 0, wx.TOP, 2)
            self.downSizer.Add([2,20],0,wx.EXPAND|wx.FIXED_MINSIZE,0)                 
            self.downSizer.Add(self.speedDown2, 0, wx.TOP|wx.EXPAND, 4)
            
            self.upSizer.Add(self.upSpeed, 0, wx.LEFT|wx.TOP, 2)                  
            self.upSizer.Add([2,20],0,wx.EXPAND|wx.FIXED_MINSIZE,0)                 
            self.upSizer.Add(self.speedUp2, 0, wx.TOP|wx.EXPAND, 4)  
            
            self.vSizer3.Add(self.downSizer, 0, wx.RIGHT, 2)         
            self.vSizer3.Add(self.upSizer, 0, wx.RIGHT, 2)         
             
            
    #        self.hSizer1.Add([2,20],0,wx.EXPAND|wx.FIXED_MINSIZE,0) 
    
    #        self.titleBG.SetSizer(self.titleSizer)
    #        self.hSizer1.Add(self.vSizerOverall, 0, wx.LEFT|wx.RIGHT|wx.TOP|wx.EXPAND, 0)
                    
            # Status Icon
    ##        self.statusIcon = ImagePanel(self, -1, name="LibStatus_boosting")        
    ##        self.statusIcon.searchBitmap(name = statusLibrary["stopped"])
    ##
    ##        self.hSizer.Add(self.statusIcon, 0, wx.TOP|wx.RIGHT|wx.EXPAND, 2)
            
    
            # Play
    ##        self.playerPlay = SwitchButton(self, name="libraryPlay")
    ##        self.playerPlay.setBackground(wx.WHITE)
    ##        self.playerPlay.SetSize((16,16))
    ##        self.playerPlay.setEnabled(False)
    ##        self.hSizer1.Add(self.playerPlay, 0, wx.TOP|wx.ALIGN_RIGHT, 2)          
    ##        self.hSizer1.Add([2,20],0,wx.EXPAND|wx.FIXED_MINSIZE,0) 
            
            # Add more info
            self.moreFileInfo = tribler_topButton(self, -1, name='moreFileInfo')
            self.moreFileInfo.SetMinSize((60,11))
            self.moreFileInfo.SetSize((60,11))
            self.vSizer3.Add(self.moreFileInfo, 0, wx.TOP, 6)
        
            
            
            
            
            
            
            
            
            
#            self.thumbSummary = self.guiUtility.thumbnailViewer(self.Parent, 'filesItemSummary')
#            self.thumbSummary.SetSize((125,70))
#    #        self.thumbSummary.setTorrent(self.data)
#    #        self.thumbSummary.setBackground(wx.BLACK)
#    #        self.thumb2 = self.thumbnailViewer(self, 'filesMode')
#            
#    #        self.thumbSummary = ImagePanel(self)
#    #        self.thumbSummary.SetSize((125,70))
#    #        self.guiUtility.standardDetails.setTorrentThumb( 'filesMode', self.data, self.thumbSummary, size='normal')
#            
#            self.vSizer.Add(self.thumbSummary, 0, wx.LEFT, 10)
#            
#            
#            # Description
#            self.vSizer0 = wx.BoxSizer(wx.VERTICAL)
#            self.Description = wx.StaticText(self, -1, '')     
#            self.triblerStyles.setLightText(item=self.Description) 
#            self.vSizer0.Add(self.Description, 1, wx.BOTTOM|wx.EXPAND, 1)        
#            self.hSizer.Add(self.vSizer0, 1, wx.TOP|wx.LEFT|wx.RIGHT|wx.EXPAND, 3)
#            
#            self.vSizer2 = wx.BoxSizer(wx.VERTICAL)
#            self.vSizer2.Add([100,1],0,wx.ALL,0)
#            self.qualityText          = wx.StaticText(self, -1, 'quality:')
#            self.spokenlangText       = wx.StaticText(self, -1, 'spoken lang:')
#            self.subtitlesText        = wx.StaticText(self, -1, 'incl. subtitles:')
#            self.tasteText            = wx.StaticText(self, -1, 'fit to taste:')
#            self.keywordsText         = wx.StaticText(self, -1, 'keywords:')        
#            self.triblerStyles.setDarkText(self.qualityText)                
#            self.triblerStyles.setDarkText(self.spokenlangText)                
#            self.triblerStyles.setDarkText(self.subtitlesText)                
#            self.triblerStyles.setDarkText(self.tasteText)                
#            self.triblerStyles.setDarkText(self.keywordsText)
#    #        self.vSizer2.Add([100,10], 0, wx.BOTTOM|wx.FIXED_MINSIZE, 1)
#            self.vSizer2.Add(self.qualityText, 0, wx.BOTTOM, 1)        
#            self.vSizer2.Add(self.spokenlangText, 0, wx.BOTTOM, 1)        
#            self.vSizer2.Add(self.subtitlesText, 0, wx.BOTTOM, 1)        
#            self.vSizer2.Add(self.tasteText, 0, wx.BOTTOM, 1)        
#            self.vSizer2.Add(self.keywordsText, 0, wx.BOTTOM, 1)                        
#            self.hSizer.Add(self.vSizer2, 0, wx.TOP|wx.RIGHT|wx.LEFT|wx.EXPAND, 3)
#            
#            self.vSizer3 = wx.BoxSizer(wx.VERTICAL)
#            self.vSizer3.Add([100,1],0,wx.ALL,0)
#            self.theQuality          = wx.StaticText(self, -1, 'good (DVD)')
#            self.theSpokenlang       = wx.StaticText(self, -1, 'English')
#            self.theSubtitles        = wx.StaticText(self, -1, '13 included')
#            self.theTaste            = wx.StaticText(self, -1, '2nd')
#            self.theKeywords         = wx.StaticText(self, -1, 'keyword a, keyword b, keyword c')        
#            self.moreFileInfo = tribler_topButton(self, -1, name='moreFileInfo')
#            self.moreFileInfo.SetMinSize((60,11))
#            self.moreFileInfo.SetSize((60,11))
#            
#    #        self.moreInfo            = TextButton(self, name = "more info>")
#            self.hSizer3 = wx.BoxSizer(wx.HORIZONTAL)
#            self.download = tribler_topButton(self, -1, name='download1')
#            self.download.SetMinSize((20,20))
#            self.download.SetSize((20,20))
#            self.play = tribler_topButton(self, -1, name='play1')
#            self.play.SetMinSize((20,20))
#            self.play.SetSize((20,20))
#            self.playAdd = tribler_topButton(self, -1, name='playAdd1')
#            self.playAdd.SetMinSize((20,20))
#            self.playAdd.SetSize((20,20))
#    
#            self.hSizer3.Add(self.download,0,wx.RIGHT|wx.FIXED_MINSIZE,4)
#            self.hSizer3.Add(self.play,0,wx.RIGHT|wx.FIXED_MINSIZE,4)
#            self.hSizer3.Add(self.playAdd,0,wx.RIGHT|wx.FIXED_MINSIZE,4)
#    #        self.vSizer2.Add(self.hSizer3, 0, wx.BOTTOM|wx.ALIGN_RIGHT, 3) 
#    #        self.download            = tribler_topButton(self, -1, name='download')        
#    #        self.download.SetMinSize((55,55))        
#    
#            self.triblerStyles.setDarkText(self.theQuality)                
#            self.triblerStyles.setDarkText(self.theSpokenlang)                
#            self.triblerStyles.setDarkText(self.theSubtitles)                
#            self.triblerStyles.setDarkText(self.theTaste)                
#            self.triblerStyles.setDarkText(self.theKeywords)
#    #        self.vSizer3.Add([100,10], 0, wx.BOTTOM|wx.FIXED_MINSIZE, 1)
#            self.vSizer3.Add(self.theQuality, 0, wx.BOTTOM, 1)        
#            self.vSizer3.Add(self.hSizer3, 0, wx.BOTTOM|wx.EXPAND, 1)
#            self.vSizer3.Add(self.theSpokenlang, 0, wx.BOTTOM, 1)        
#            self.vSizer3.Add(self.theSubtitles, 0, wx.BOTTOM, 1)        
#            self.vSizer3.Add(self.theTaste, 0, wx.BOTTOM, 1)        
#            self.vSizer3.Add(self.theKeywords, 0, wx.BOTTOM, 1)
#            self.vSizer3.Add(self.moreFileInfo, 0, wx.BOTTOM|wx.EXPAND, 1)
#            
#            self.hSizer.Add(self.vSizer3, 0, wx.TOP|wx.RIGHT|wx.EXPAND, 3)
#            
#            # hidden because no data is available yet.      
#            self.qualityText.Hide()
#            self.spokenlangText.Hide()
#            self.subtitlesText.Hide()
#            self.keywordsText.Hide()
#            self.tasteText.Hide()
#            
#            self.theQuality.Hide()
#            self.theSpokenlang.Hide()
#            self.theSubtitles.Hide()
#            self.theKeywords.Hide()
#            self.theTaste.Hide()
        

        self.SetSizer(self.hSizer0)
        self.SetAutoLayout(1);  
        self.Layout()
        
    def setDataLib(self):
        filelist = self.guiUtility.filesList(self.data)
        print 'tb > filelist = %s' % filelist
        
            
    def setDataNoLib(self):
        print 'tb > SET DATA'
        torrent = {}
        if self.data:            
            torrent = self.data
        
        #------------- DESCRIPTION --------------
        descrtxt = ''
        flag = False
        ##self.thumbSummary.setTorrent(self.Parent.data)
        if not torrent.get('web2'):
#            print 'tb > self.Parent.data = %s' % self.Parent.data


            # check here if there are more than one file in the torrent is > playlist
            torrent_dir = self.utility.session.get_torrent_collecting_dir()
            torrent_filename = os.path.join(torrent_dir, torrent['torrent_file_name'])
            metadata = self.utility.getMetainfo(torrent_filename)
            
            if metadata:
#            if 'metadata' in torrent:
#                metadata = torrent['metadata']
                
                # see how many files are in the torrent
                info = metadata.get('info')
#                print 'tb > info = %s' % info
#                print 'tb > metadata = %s' % metadata
                if not info:
                    print 'tb > RETURN'
                    return {}
            
                #print metadata.get('comment', 'no comment')
                filedata = info.get('files')
            
                if filedata:
                    self.moreFileInfo.SetName('moreFileInfoPlaylist')                
                else:
                    self.moreFileInfo.SetName('moreFileInfo')                
                
                # encoding
                encoding = None
                if 'encoding' in metadata and metadata['encoding'].strip():
                    encoding = metadata['encoding']

                flag = False
                for key in ['comment','comment-utf8','Description']: # reverse priority
                    if key in metadata: # If vuze torrent
                        tdescrtxt = metadata[key]
                        if key == 'comment-utf8':
                            tencoding = 'utf_8'
                        else:
                            tencoding = encoding
                        descrtxt = bin2unicode(tdescrtxt,tencoding)
                        flag = True
                if not flag:
                    if 'source' in torrent:
                        s = torrent['source']
                        if s != '':
                            if s == 'BC':
                                s = 'Received from other user'
                            descrtxt = "Source: "+s

                        flag = True
            elif 'description' in torrent:
                descrtxt = torrent['description']
                flag = True
            else:    
                descrtxt = 'Found at other Tribler user \n\nNo more info available'
                self.moreFileInfo.Hide()
                flag = True
             
            if not flag:
                if 'source' in torrent:
                    s = torrent['source']
                    if s == 'BC':
                        s = 'Received from other user'
                    descrtxt = "Source: "+s

        elif torrent.get('web2'):
            print 'tb > NO MORE INFO'
            descrtxt = 'Found at a video website \n\nNo more info available'
            self.moreFileInfo.Hide()
        
#        self.Description.SetLabel(descrtxt)
#        self.Description.Wrap(-1)       

        self.guiUtility.standardDetails.setDownloadbutton(torrent=torrent, item = self.download)        

            

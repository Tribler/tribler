import wx
import wx.xrc as xrc
import random
from Tribler.Core.Utilities.utilities import *
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.tribler_topButton import tribler_topButton
from Tribler.Core.CacheDB.CacheDBHandler import MyDBHandler
from Tribler.Main.vwxGUI.IconsManager import IconsManager
from Tribler.Main.Dialogs.socnetmyinfo import MyInfoWizard
from Tribler.Core.CacheDB.CacheDBHandler import MyPreferenceDBHandler
from Tribler.Core.CacheDB.CacheDBHandler import BarterCastDBHandler
from Tribler.Main.vwxGUI.TriblerStyles import TriblerStyles
from Tribler.Core.Utilities.unicode import bin2unicode
#from Tribler.vwxGUI.filesItemPanel import *
from Tribler.Main.vwxGUI.filesItemPanel import FilesItemPanel
#from Tribler.unicode import bin2unicode
from Tribler.Core.Utilities.unicode import *
#from Tribler.vwxGUI.filesItemPanel import ThumbnailViewer
#from Tribler.vwxGUI.standardDetails import *
from Tribler.Core.Overlay.MetadataHandler import MetadataHandler
from time import time
import urllib

DEBUG = False

class fileDetailsOverviewPanel(wx.Panel):
    def __init__(self, *args, **kw):        
        self.initDone = False
        
        self.elementsName = [ 'title', 'description', 'detailsInfo', 'detailsInfoHeader', 'includedFiles', 'includedFilesHeader', 'thumbField', 'download',
                             'desc','descHeader','similarFiles','similarFilesHeader','recommendedFiles','recommendedFilesHeader',
                             'popularityField1', 'popularityField2','similarItems','recommendedItems','includedFilesList','playAddMore',
                             'size', 'quality', 'spoken lang.', 'incl. subtitles', 'creation date', 'popularity', 'fit to taste', 'keywords',
                             'sizeField', 'qualityField', 'spoken lang.Field', 'incl. subtitlesField', 'creation dateField', 'fit to tasteField', 'keywordsField',
                             'moderationDisabled','moderationEnabled']

        self.elements = {}
       
        self.data = {} #data related to profile information, to be used in details panel
        

        #self.mm = MugshotManager.getInstance() 
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility        
        self.moderationState = False;
        
        
        self.firstTimeInitiate = False
        self.simItems = []
        self.recomItems = []        
        self.activeSim = None
        self.activeRem = None
        self.actualSize = None        
        
        self.SimItemsExist = False
        self.RecomItemsExist = False
        self.includedFilesListExist = False
        self.filelistText = []
        self.CBItem = []        
        self.hSizers = []

        self.fileItemSim = []
        self.fileItemRec = []

#        self.filesItemPanel = filesItemPanel
#        self.standardDetails = standardDetails.getInstance()
#        self.standardDetails.setTorrentThumb = standardDetails.setTorrentThumb
        
        self.metadatahandler = MetadataHandler.getInstance()
#        self.ThumbnailViewer = ThumbnailViewer
        self.triblerStyles = TriblerStyles.getInstance()
        
        
        if len(args) == 0: 
            pre = wx.PrePanel() 
            # the Create step is done by XRC. 
            self.PostCreate(pre) 
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate) 
        else:
            wx.Panel.__init__(self, *args, **kw) 
            self._PostInit()     
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        
        event.Skip()
        return True
    
    def _PostInit(self):
        self.bartercast_db = BarterCastDBHandler()
        self.mydb = MyPreferenceDBHandler()
       
       
        self.initDone = True
        
        
    def addComponents(self):
        self.title = self.getGuiElement('title')        
        self.description = self.getGuiElement('description')        
        self.download = self.getGuiElement('download')        
        
        self.detailsInfoHeader = self.getGuiElement('detailsInfoHeader')        
        self.detailsInfo = self.getGuiElement('detailsInfo')
        
        self.includedFilesHeader = self.getGuiElement('includedFilesHeader')        
        self.includedFiles = self.getGuiElement('includedFiles')        
        
#        self.descHeader = self.getGuiElement('descHeader')        
#        self.desc = self.getGuiElement('desc') 
        
        self.similarFilesHeader = self.getGuiElement('similarFilesHeader')        
        self.similarFiles = self.getGuiElement('similarFiles') 
        
        self.recommendedFilesHeader = self.getGuiElement('recommendedFilesHeader')        
        self.recommendedFiles = self.getGuiElement('recommendedFiles') 

        
        self.size = self.getGuiElement('size')
        self.quality = self.getGuiElement('quality')
        self.spokenLang = self.getGuiElement('spoken lang.')
        self.inclSubtitles = self.getGuiElement('incl. subtitles')
        self.creationDate = self.getGuiElement('creation date')
        self.popularity = self.getGuiElement('popularity')
        self.fitToTaste = self.getGuiElement('fit to taste')
        self.keywords = self.getGuiElement('keywords')
        
        self.sizeField = self.getGuiElement('sizeField')
        self.qualityField = self.getGuiElement('qualityField')
        self.spokenLangField = self.getGuiElement('spoken lang.Field')
        self.inclSubtitlesField = self.getGuiElement('incl. subtitlesField')
        self.creationDateField = self.getGuiElement('creation dateField')
#        self.popularityField = self.getGuiElement('popularityField')
        self.seedersField = self.getGuiElement('popularityField1')
        self.leechersField = self.getGuiElement('popularityField2')
        
        self.fitToTasteField = self.getGuiElement('fit to tasteField')
        self.keywordsField = self.getGuiElement('keywordsField') 
        
        self.moderationDisabled = self.getGuiElement('moderationDisabled')
        self.moderationEnabled = self.getGuiElement('moderationEnabled')
        self.moderationDisabled.Bind(wx.EVT_LEFT_UP, self.clickedButtonEnable)
        self.moderationEnabled.Bind(wx.EVT_LEFT_UP, self.clickedButtonDisable)

        self.includedFilesList = self.getGuiElement('includedFilesList')            
        self.similarItems = self.getGuiElement('similarItems') 
        self.recommendedItems = self.getGuiElement('recommendedItems') 
        
        self.similarItems.mm = self.mm
        self.recommendedItems.mm = self.mm
        
        self.playAddMore = self.getGuiElement('playAddMore')
#        self.moderationEnabled.Bind(wx.EVT_LEFT_UP, self.clickedButtonDisable)
        self.playAddMore.Bind(wx.EVT_LEFT_UP, self.playAddMoreClicked)
        
#        print 'similarItems= %s' % self.similarItems            
        

    def getGuiElement(self, name):
        if not self.elements.has_key(name) or not self.elements[name]:
            print "[fileDetailsOverviewPanel] gui element %s not available" % name
            return None
        return self.elements[name]
    
    def indexXRCelements(self):
        for element in self.elementsName:
            xrcElement = xrc.XRCCTRL(self, element)
            if not xrcElement:
                print 'fileDetailsOverviewPanel: Error: Could not identify xrc element:',element
            self.elements[element] = xrcElement        
    
    def setData(self, infohash):
        self.data = self.data_manager.getTorrents([infohash])[0]
        if self.firstTimeInitiate == False :
            self.indexXRCelements()
            self.addComponents()
            
    #        (torrent_dir,torrent_name) = self.metadatahandler.get_std_torrent_dir_name(torrent)
    #        torrent_filename = os.path.join(torrent_dir, torrent_name)
    #        self.filesItemPanel.loadMetadata(self.data,torrent_filename)
    #        
    #        print loadAzureusMetadataFromTorrent()   
    #        self.info = self.data['info'] 
        
            # Styling and set Static text.
            self.triblerStyles.setHeaderText(self.title)     
            self.triblerStyles.setLightText(self.description, text= '---')        
            
            self.triblerStyles.titleBar(self.detailsInfoHeader)     
            self.triblerStyles.titleBar(self.detailsInfo)
            
            self.triblerStyles.titleBar(self.includedFilesHeader)
            self.triblerStyles.titleBar(self.includedFiles)
            
#            self.triblerStyles.titleBar(self.descHeader)
#            self.triblerStyles.titleBar(self.desc)
            
            self.triblerStyles.titleBar(self.similarFilesHeader)
            self.triblerStyles.titleBar(self.similarFiles)
            
            self.triblerStyles.titleBar(self.recommendedFilesHeader)
            self.triblerStyles.titleBar(self.recommendedFiles)
            
            # sending item name also, to make it possible to translate in TriblerStyles.py
            self.triblerStyles.setDarkText(self.size, text= self.getGuiElement('size').GetName())        
            self.triblerStyles.setDarkText(self.quality, text= self.getGuiElement('quality').GetName())
            self.triblerStyles.setDarkText(self.spokenLang, text= self.getGuiElement('spoken lang.').GetName())
            self.triblerStyles.setDarkText(self.inclSubtitles, text= self.getGuiElement('incl. subtitles').GetName())
            self.triblerStyles.setDarkText(self.creationDate, text= self.getGuiElement('creation date').GetName())
            self.triblerStyles.setDarkText(self.popularity, text= self.getGuiElement('popularity').GetName())
            self.triblerStyles.setDarkText(self.fitToTaste, text= self.getGuiElement('fit to taste').GetName())
            self.triblerStyles.setDarkText(self.keywords, text= self.getGuiElement('keywords').GetName())
            # set torrent data:
            self.triblerStyles.setLightText(self.sizeField, text= '---')        
            self.triblerStyles.setLightText(self.qualityField, text= '---')
            self.triblerStyles.setLightText(self.spokenLangField, text= '---')
            self.triblerStyles.setLightText(self.inclSubtitlesField, text= '---')
            self.triblerStyles.setLightText(self.creationDateField, text= '---')
            self.triblerStyles.setLightText(self.seedersField, text= '---')
            self.triblerStyles.setLightText(self.leechersField, text= '---')
            self.triblerStyles.setLightText(self.fitToTasteField, text= '---')
            self.triblerStyles.setLightText(self.keywordsField, text= '---')        
        
        
        self.clickedButtonDisable(event = None)
#        print "the data of the torrent ==== %s" % self.data       
        
        # ==========================================================================
#       #check if this is a corresponding item from type point of view
#        if item.get('infohash') is None:
#            return #no valid torrent
#        torrent = item

        # ========   THUMB ======== 
        # (by setting the thumb also the metadata is added!
        self.guiUtility.standardDetails.setTorrentThumb( 'filesMode', self.data, self.getGuiElement('thumbField'))
        
        
        # ========   TITLE ========
        self.title.SetLabel(self.data.get('content_name', 'no title available'))
        self.title.Wrap(-1) # doesn't appear to work
          
        # ========   DOWNLOAD / PLAY BUTTON ========
#        print 'tb>>>>>>>>>>>>>>>>>>>>>> self.data'
#        print self.data
        # setDownloadbutton(self, torrent, tab = None, item = ''):
        self.guiUtility.standardDetails.setDownloadbutton(self.data, item = self.download)        
        # ========   DESCRIPTION ========
        descrtxt = ''
        flag = False
        if not self.data.get('web2'):
            if 'metadata' in self.data:
#                metadata = self.info
                metadata = self.data['metadata']



                encoding = None
                if 'encoding' in metadata and metadata['encoding'].strip():
                    encoding = metadata['encoding']

                flag = False
                for key in ['comment','comment-utf8','Description']: # reverse priority
                    if key in metadata: # If vuze torrent
                        print 'tb Vuze torrent----------------------------'
                        tdescrtxt = metadata[key]
                        if key == 'comment-utf8':
                            tencoding = 'utf_8'
                        else:
                            tencoding = encoding
                        descrtxt = bin2unicode(tdescrtxt,tencoding)
                        flag = True
                if not flag:
                    if 'source' in self.data:
                        s = self.data['source']
                        if s != '':
                            if s == 'BC':
                                s = 'Received from other user'
                            descrtxt = "Source: "+s

                        flag = True
        else:
            descrtxt = self.data['description']
            flag = True
         
        if not flag:
            if 'source' in self.data:
                s = self.data['source']
                if s == 'BC':
                    s = 'Received from other user'
                descrtxt = "Source: "+s
        
#        self.description.SetDefaultStyle()
#        print self.description.GetNumberOfLines()


        

#        self.description.setText(text= ' bla bla bla bla bla bla  bla bla bla bla bla bla  bla bla bla bla bla bla  bla bla bla bla bla bla  bla bla bla bla bla bla ')
        self.description.setText(descrtxt)
#        self.description.editSetToggle(False)

        self.description.Refresh()



        
        # ========   SIZE / LENGTH ========
        if not self.data.get('web2'):
            self.sizeField.SetLabel(self.utility.size_format(self.data['length']))
        else:
            self.sizeField.SetLabel(self.data['length'])
       
        # ========   CREATION DATE ========
        if self.data.get('date',0):
            self.creationDateField.SetLabel(friendly_time(self.data['date']))
        else:
            self.creationDateField.SetLabel('?')
        
        # ========   POPULARITY ========    
        if self.data.get('web2'):
            print 'tb web2'
            #view = self.getGuiObj('views')
            #view.Show()
            #pop = self.getGuiObj('popularity')
            #pop.Hide()
            #pop.GetParent().Layout()

##            viewsField = self.getGuiObj('popularityField1')
##            viewsField.SetLabel(str(torrent['views']) + " views")
##            viewsField.SetToolTipString('')
##            
##            self.getGuiObj('popularityField2').Hide()
##            self.getGuiObj('up').Hide()                    
##            self.getGuiObj('down').Hide()
##            self.getGuiObj('refresh').Hide()
            

##            viewsField.GetParent().Layout()
##            viewsField.SetSize((100,18))

        else:

#            self.getGuiObj('popularityField2').Show()
#            self.getGuiObj('up').Show()
#            self.getGuiObj('down').Show()
#            self.getGuiObj('refresh').Show()

            if self.data.has_key('seeder'):
                seeders = self.data['seeder']
#                seedersField = self.getGuiObj('popularityField1')
#                leechersField = self.getGuiObj('popularityField2')
                
                if seeders > -1:
                    self.seedersField.SetLabel('%d' % seeders)
                    self.seedersField.SetToolTipString(self.utility.lang.get('seeder_tool') % seeders)
#                    self.getGuiElement('up').SetToolTipString(self.utility.lang.get('seeder_tool') % seeders)
                    self.leechersField.SetLabel('%d' % self.data['leecher'])
#                    self.getGuiElement('down').SetToolTipString(self.utility.lang.get('leecher_tool') % self.data['leecher'])
                    self.leechersField.SetToolTipString(self.utility.lang.get('leecher_tool') % self.data['leecher'])
                    
                else:
                    self.seedersField.SetLabel('?')
                    self.seedersField.SetToolTipString('')
                    self.leechersField.SetLabel('?')
                    self.leechersField.SetToolTipString('')
#                    self.getGuiElement('up').SetToolTipString('')
#                    self.getGuiElement('down').SetToolTipString('')
#                    self.seedersField.SetSize((36,18))
                    
                refreshString = '%s: %s' % (self.utility.lang.get('last_checked'), friendly_time(self.data.get('last_check_time')))
#                self.getGuiElement('refresh').SetToolTipString(refreshString)
#            self.seedersField.GetParent().Layout()
            
#        # ========   INCLUDED FILES   ========  
#        
        filelist = self.guiUtility.filesList(self.data, self.metadatahandler)
        self.filesListRendering(filelist)
            
        # ========   'SIMILAR' AND 'PEOPLE WHO LIKE THIS ALSO LIKE' ITEMS ========  
    
        self.simItems = []
        self.simItems = self.data_manager.getSimilarTitles(self.data, 5)        
        self.recomItems = []
#        sim_torrents = self.data_manager.getSimItems(infohash, 8)
        self.recomHashes = self.data_manager.getSimItems(infohash, num=5)        
        for hash in self.recomHashes:
            self.recomItems.append(self.data_manager.getTorrents([hash]))
        

        self.setSimItems()
        self.setRecomItems()
        
        # Call a function to retrieve similar torrent data
##        wx.CallAfter(self.fillSimTorrentsList, item['infohash'])
##        wx.CallAfter(self.fillSimTitlesList, item)
        # Show or hide download button in detailstab
        
                
#         Set tastheart and ranking
##        rank = torrent.get('simRank', -1)
##        self.getGuiObj('TasteHeart').setRank(rank)
##        self.setRankToRecommendationField(rank)
##        
##    elif self.getGuiObj('files_detailsTab').isSelected():
##        tab = 'filesTab_files'
##        filesList = self.getGuiObj('includedFiles', tab = tab)
##        filesList.setData(torrent,self.metadatahandler)
##        self.getGuiObj('filesField', tab = tab).SetLabel('%d' % filesList.getNumFiles())
##        # Remove download button for libraryview
##        self.setDownloadbutton(torrent, tab = tab)
##        
##        # Set tracker info
##        trackerField = self.getGuiObj('trackerField', tab = tab)
##        trackerField.Wrap(-1)
##        if torrent.has_key('tracker'):
##            trackerString = torrent['tracker']
##            short = getShortTrackerFormat(trackerString)
##            trackerField.SetLabel(short)
##            trackerField.SetToolTipString(trackerString)
##        else:
##            trackerField.SetLabel('')
##            trackerField.SetToolTipString('')
##        
##        
##        
#        self.SetAutoLayout(1)
        # hide unused items:        
###        self.quality.Hide()
###        self.spokenLang.Hide()
###        self.inclSubtitles.Hide()                
###        self.keywords.Hide()        
###        
###        self.qualityField.Hide()
###        self.spokenLangField.Hide()
###        self.inclSubtitlesField.Hide() 
###        self.keywordsField.Hide()
        
        self.activeSim = None
        self.activeRem = None
        self.firstTimeInitiate = True
        
        

        
    def mouseAction2(self, event, itemName=''):     
        self.fileItemSim[itemName].select(rowIndex = itemName, colIndex='')
        self.fileItemSim[itemName].SetSize((-1, 140)) 
        if self.activeSim != None:            
            self.fileItemSim[self.activeSim].deselect(rowIndex = self.activeSim, colIndex='')
            self.fileItemSim[self.activeSim].SetSize((-1, 22))        
        
        self.activeSim = itemName
        self.similarItems.Layout()
        self.actualSize = self.GetSize()
        self.Layout()
        
    def mouseAction3(self, event, itemName=''):     
        self.fileItemRec[itemName].select(rowIndex = itemName, colIndex='')
        self.fileItemRec[itemName].SetSize((-1, 140)) 
        if self.activeRem != None:            
            self.fileItemRec[self.activeRem].deselect(rowIndex = self.activeRem, colIndex='')
            self.fileItemRec[self.activeRem].SetSize((-1, 22))        
        
        self.activeRem = itemName
        self.recommendedItems.Layout()
        self.actualSize = self.GetSize()
        self.Layout()

    def setSimItems(self, itemName=''):
        if self.firstTimeInitiate == False :
            self.vSizerSimItems = wx.BoxSizer(wx.VERTICAL)
        
        if self.activeSim  != None:
            self.fileItemSim[self.activeSim].deselect(rowIndex = self.activeSim, colIndex='')
            self.fileItemSim[self.activeSim].SetSize((-1, 22))    
        
        i=0    
        for torrent in self.simItems:
            # item aanmaken
            if len(self.fileItemSim) <= i:
                self.fileItemSim.append(FilesItemPanel(self.similarItems, 'keyfun', name=i))                
                # add to an empty Sizer
                self.vSizerSimItems.Add(self.fileItemSim[i], 0, wx.ALL|wx.EXPAND|wx.FIXED_MINSIZE, 2)  
             
            self.fileItemSim[i].setData(torrent)
            self.fileItemSim[i].thumb.setTorrent(torrent)
            self.fileItemSim[i].Show()
            self.fileItemSim[i].SetSize((-1, 22))
            self.fileItemSim[i].Layout()         
            i = i + 1
            
        for j in range(i,len(self.fileItemSim)):
            self.fileItemSim[j].Hide()
        
        if self.SimItemsExist == False:
            self.similarItems.SetSizer(self.vSizerSimItems)
            self.SimItemsExist = True
        
        self.similarItems.SetSize((-1, 5*22+140))    
        



    def setRecomItems(self, itemName=''):
        #        self.recomItems.DestroyChildren()
        if self.firstTimeInitiate == False :
            self.vSizerRecomItems = wx.BoxSizer(wx.VERTICAL)

          
        if self.activeRem  != None:
            self.fileItemRec[self.activeRem].deselect(rowIndex = self.activeRem, colIndex='')
            self.fileItemRec[self.activeRem].SetSize((-1, 22))    
        
        s=0    
        for torrent in self.recomItems:
            # item aanmaken
            if len(self.fileItemRec) <= s :
                self.fileItemRec.append(FilesItemPanel(self.recommendedItems, 'keyfun', name=s))                
                # add to an empty Sizer
                self.vSizerRecomItems.Add(self.fileItemRec[s], 0, wx.ALL|wx.EXPAND|wx.FIXED_MINSIZE, 2)  
              
            self.fileItemRec[s].setData(torrent[0])
            self.fileItemRec[s].thumb.setTorrent(torrent[0])
            self.fileItemRec[s].Show()
            self.fileItemRec[s].SetSize((-1, 22))
            self.fileItemRec[s].Layout()         
            s = s + 1
            
        for t in range(s,len(self.fileItemRec)):
            self.fileItemRec[t].Hide()
        
        if self.RecomItemsExist == False:
            self.recommendedItems.SetSizer(self.vSizerRecomItems)
            self.RecomItemsExist = True

        self.recommendedItems.SetSize((-1, 5*22+140)) 
        
        
        
    def clickedButtonEnable(self, event): 

        if self.moderationState != True:
            self.description.editSetToggle(True)
            
            self.moderationEnabled.Show()
            self.moderationDisabled.Hide()                        
            
            self.moderationState = True
            self.Layout()

        if event != None:
            event.Skip() 
            
    def clickedButtonDisable(self, event):  
       
        if self.moderationState != False:
            self.description.editSetToggle(False)
       
            self.moderationEnabled.Hide()
            self.moderationDisabled.Show()                        
            
            self.moderationState = False            
            self.Layout()
        
        if event != None:
            event.Skip()
            
    
        
    def filesListRendering(self, filelist):
        # Add the filelist to the GUI
        if self.firstTimeInitiate == False :
            self.vSizerFilelist = wx.BoxSizer(wx.VERTICAL)
#            
        p=0                       
        for f in filelist[:10]:
            # item aanmaken                
            if len(self.filelistText) <= p : 
                self.hSizers.append(wx.BoxSizer(wx.HORIZONTAL))
                
                self.CBItem.append(wx.CheckBox(self.includedFilesList,-1))
                self.CBItem[p].Bind(wx.EVT_CHECKBOX, self.CBClicked)
                self.hSizers[p].Add(self.CBItem[p], 0, wx.ALL|wx.EXPAND|wx.FIXED_MINSIZE, 0)                     

                self.filelistText.append(wx.StaticText(self.includedFilesList,-1))                    
                self.triblerStyles.setDarkText(self.filelistText[p], text= '')
                self.hSizers[p].Add(self.filelistText[p], 1, wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE, 4)                     
                
                
                self.vSizerFilelist.Add(self.hSizers[p], 0, wx.ALL|wx.EXPAND|wx.FIXED_MINSIZE, 2)  
                
                           
            self.CBItem[p].SetValue(True)                
            
            self.filelistText[p].SetLabel(f[0])
            self.filelistText[p].SetToolTipString(f[0] + ' - ' + f[1])                
#                
            self.CBItem[p].Show()
            self.filelistText[p].Show() 
            self.hSizers[p].Layout()        
            self.vSizerFilelist.Layout()
#                
            p = p + 1
#            
        # self.selectedFiles = list of selected files in the Torrent
        self.selectedFiles =[]

        self.selectedFiles = self.filelistText[:]    
                        
        for t in range(p,len(self.CBItem)):                
            self.CBItem[t].Hide()
            self.filelistText[t].Hide()
            del self.selectedFiles[p]
        
        if self.includedFilesListExist == False:
            self.includedFilesList.SetSizer(self.vSizerFilelist)
            self.includedFilesListExist = True

            
    
    def CBClicked(self, event):              

        clickedBC = event.GetEventObject()
        indexNo = self.CBItem.index(clickedBC)
        if clickedBC.GetValue(): # if state to checked:
            self.selectedFiles[indexNo] = self.filelistText[indexNo]            
        else: # if state to UNchecked:
            self.selectedFiles[indexNo] = ''            
        
                
    def playAddMoreClicked(self, event):   
        event.Skip()
  
        for object in self.guiUtility.frame.LeftMenu.menu:
            if object.name == 'LIBRARY':
                playlistList =  object.sublist[:-1]
                break
        
        addToPlaylist = wx.Menu() 
        self.utility.makePopup(addToPlaylist, None, '', extralabel ='Download in:', status="active")
        for item in playlistList:            
            self.utility.makePopup(addToPlaylist, self.addToPlaylist, '', extralabel = item, status="active")
        
        addToPlaylist.AppendSeparator()    
        self.utility.makePopup(addToPlaylist, None, '', extralabel = 'Download as:', status="")
        self.utility.makePopup(addToPlaylist, self.addToPlaylist, '', extralabel = 'Playlist', status="")        
        self.utility.makePopup(addToPlaylist, self.addToPlaylist, '', extralabel = 'Playlist and subscribe', status="")
            
        self.PopupMenu(addToPlaylist, (-1,-1)) 
#            return (changeViewMouse)

    def addToPlaylist(self, event): 
        print 'tb > addToPlaylist CLICKED'
        
        
        
        

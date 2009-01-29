import wx
import wx.xrc as xrc
import random
from Tribler.Core.Utilities.utilities import *
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.TriblerStyles import TriblerStyles
from Tribler.Core.Utilities.unicode import bin2unicode
from Tribler.Main.vwxGUI.filesItemPanel import FilesItemPanel
from Tribler.Core.Utilities.unicode import *
from Tribler.Main.vwxGUI.standardPager import *
from Tribler.Main.vwxGUI.standardGrid import *
import urllib

DEBUG = False

class playlistOverviewPanel(wx.Panel):
    def __init__(self, *args, **kw):        
        self.initDone = False
        
        self.elementsName = [ 'title', 'description', 'detailsCreator', 'detailsCreatorHeader', 'thumbField',
                              'download','play','playAdd','playAddMore','includedFilesList','standardPager','playlistGrid',
                              'desc','descHeader','included','includedHeader','subscribers','subscribersHeader'
                              ]

        self.elements = {}
       
        self.data = {} #data related to profile information, to be used in details panel
        

        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility        
        self.data_manager = TorrentDataManager.getInstance(self.utility)
        
        self.firstTimeInitiate = False
        
        self.includedFilesListExist = False
        self.CBItem = []
        self.hSizers = []
        self.filelistText = []
        
        self.triblerStyles = TriblerStyles.getInstance()        
        self.metadatahandler = MetadataHandler.getInstance()
        
        
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
#        self.setData()
        self.initDone = True
        
        
    def addComponents(self):
        self.title = self.getGuiElement('title')        
        self.description = self.getGuiElement('description')        
        self.download = self.getGuiElement('download')        
        
#        self.descHeader = self.getGuiElement('descHeader')        
#        self.desc = self.getGuiElement('desc') 
        
        self.detailsCreatorHeader = self.getGuiElement('detailsCreatorHeader')        
        self.detailsCreator = self.getGuiElement('detailsCreator')
        
        self.includedHeader = self.getGuiElement('includedHeader')        
        self.included = self.getGuiElement('included')        
        
        self.subscribersHeader = self.getGuiElement('subscribersHeader')        
        self.subscribers = self.getGuiElement('subscribers') 
        
        self.playAddMore = self.getGuiElement('playAddMore')
        
        self.includedFilesList = self.getGuiElement('includedFilesList')            
        
        self.standardPager = self.getGuiElement('standardPager') 
        
        self.playlistGrid = self.getGuiElement('playlistGrid')

#        self.playAddMore.Bind(wx.EVT_LEFT_UP, self.playAddMoreClicked)
        
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
#        self.data = self.data_manager.getTorrents([infohash])[0]

        if self.firstTimeInitiate == False :
            print 'tb > in SETDATA'
            self.indexXRCelements()
            self.addComponents()
            

        
            # Styling and set Static text.
            self.triblerStyles.titleBar(self.detailsCreatorHeader)     
            self.triblerStyles.titleBar(self.detailsCreator)
            
#            self.triblerStyles.titleBar(self.descHeader)
#            self.triblerStyles.titleBar(self.desc)
            
            self.triblerStyles.titleBar(self.includedHeader)
            self.triblerStyles.titleBar(self.included)
            
            self.triblerStyles.titleBar(self.subscribersHeader)
            self.triblerStyles.titleBar(self.subscribers)
            

        # ========   INCLUDED FILES   ========  
        
        self.filesList(self.data, self.metadatahandler)

            
            # sending item name also, to make it possible to translate in TriblerStyles.py
##            self.triblerStyles.setDarkText(self.size, text= self.getGuiElement('size').GetName())        
##            self.triblerStyles.setDarkText(self.quality, text= self.getGuiElement('quality').GetName())
##            self.triblerStyles.setDarkText(self.spokenLang, text= self.getGuiElement('spoken lang.').GetName())
##            self.triblerStyles.setDarkText(self.inclSubtitles, text= self.getGuiElement('incl. subtitles').GetName())
##            self.triblerStyles.setDarkText(self.creationDate, text= self.getGuiElement('creation date').GetName())
##            self.triblerStyles.setDarkText(self.popularity, text= self.getGuiElement('popularity').GetName())
##            self.triblerStyles.setDarkText(self.fitToTaste, text= self.getGuiElement('fit to taste').GetName())
##            self.triblerStyles.setDarkText(self.keywords, text= self.getGuiElement('keywords').GetName())
##            # set torrent data:
##            self.triblerStyles.setDarkText(self.sizeField, text= '---')        
##            self.triblerStyles.setDarkText(self.qualityField, text= '---')
##            self.triblerStyles.setDarkText(self.spokenLangField, text= '---')
##            self.triblerStyles.setDarkText(self.inclSubtitlesField, text= '---')
##            self.triblerStyles.setDarkText(self.creationDateField, text= '---')
##            self.triblerStyles.setDarkText(self.seedersField, text= '---')
##            self.triblerStyles.setDarkText(self.leechersField, text= '---')
##            self.triblerStyles.setDarkText(self.fitToTasteField, text= '---')
##            self.triblerStyles.setDarkText(self.keywordsField, text= '---')        
        
        


        self.firstTimeInitiate = True
        
        
    def filesList(self, torrent, metadatahandler):
        # tb > code is copied from Tribler > vwxGUI > tribler>List.py [FilesList]
        # Get the file(s)data for this torrent

            
        if DEBUG:
            print >>sys.stderr,'tribler_List: setData of FilesTabPanel called'
        try:
            
            if torrent.get('web2') or 'query_permid' in torrent: # web2 or remote query result
                self.filelist = []
    #                self.DeleteAllItems()
                self.onListResize(None)
                return {}
    
            (torrent_dir,torrent_name) = metadatahandler.get_std_torrent_dir_name(torrent)
            torrent_filename = os.path.join(torrent_dir, torrent_name)
            if not os.path.exists(torrent_filename):
                if DEBUG:    
                    print >>sys.stderr,"tribler_List: Torrent: %s does not exist" % torrent_filename
                return {}
            
            metadata = self.utility.getMetainfo(torrent_filename)
            if not metadata:
                return {}
            info = metadata.get('info')
            if not info:
                return {}
            
            #print metadata.get('comment', 'no comment')
                
                
            filedata = info.get('files')
            if not filedata:
                filelist = [(dunno2unicode(info.get('name')),self.utility.size_format(info.get('length')))]
            else:
                filelist = []
                for f in filedata:
                    filelist.append((dunno2unicode('/'.join(f.get('path'))), self.utility.size_format(f.get('length')) ))
                filelist.sort()
                
                self.setIncludedFiles(filelist)   
                
            
            
            
            
        except:
            if DEBUG:
                print >>sys.stderr,'tribler_List: error getting list of files in torrent'
            print_exc()
            return {}
    
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
            
            
        self.PopupMenu(addToPlaylist, (-1,-1)) 
#            return (changeViewMouse)

    def addToPlaylist(self, event): 
        print 'tb > addToPlaylist CLICKED'
        
    def setIncludedFiles(self, filelist):
        # Add the filelist to the GUI
        if self.firstTimeInitiate == False :
            self.vSizerFilelist = wx.BoxSizer(wx.VERTICAL)
        
        p=0 
#        self.playlistGrid = playlistGrid()
#        pager = standardPager
        self.standardPager.setGrid(self.playlistGrid)
        
        print 'tb > self.playlistGrid = %s' % self.playlistGrid
#        grid.setData(self.data[self.mode].get('data'), resetPages = False)
#        filelist moet torrent zijn!
        torrentList = []
        for i in range(0, len(filelist)):        
            print i
            torrentList.append(self.data)
#            i = i +1
            
        self.playlistGrid.setData(torrentList , resetPages = True)

        for f in filelist[:7] :
            # item aanmaken                
##            if len(self.CBItem) <= p : 
##                self.hSizers.append(wx.BoxSizer(wx.HORIZONTAL))
##                
##                self.CBItem.append(wx.CheckBox(self.includedFilesList,-1))
##                self.CBItem[p].Bind(wx.EVT_CHECKBOX, self.CBClicked)
##                self.hSizers[p].Add(self.CBItem[p], 0, wx.ALL|wx.EXPAND|wx.FIXED_MINSIZE, 0)                     
##
##                self.filelistText.append(wx.StaticText(self.includedFilesList,-1))                    
##
##                self.hSizers[p].Add(self.filelistText[p], 1, wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE, 4)
##                self.vSizerFilelist.Add(self.hSizers[p], 0, wx.ALL|wx.EXPAND|wx.FIXED_MINSIZE, 2)  
##                           
##            self.CBItem[p].SetValue(True)                
##            
##            self.filelistText[p].SetLabel(f[0])
##            self.filelistText[p].SetToolTipString(f[0] + ' - ' + f[1])                
##            
##            self.CBItem[p].Show()
##            self.filelistText[p].Show()    
##            self.hSizers[p].Layout()        
##            self.vSizerFilelist.Layout()
               

            if self.playlistGrid.orientation == 'vertical':
                print 'tb > vertical'
                hSizer = self.playlistGrid.vSizer.GetItem(p%self.playlistGrid.currentRows+1).GetSizer()
                panel = hSizer.GetItem(p / self.playlistGrid.currentRows).GetWindow()
            else:
                print 'tb > horizontal'
                hSizer = self.playlistGrid.vSizer.GetItem(p/self.playlistGrid.cols+1).GetSizer()
                panel = hSizer.GetItem(p % self.playlistGrid.cols).GetWindow()
            
            
            panel.title.SetLabel(f[0])    
            panel.fileSize.SetLabel(f[1]) 
            panel.playListIconDef.Hide()   
            panel.toggleFilesItemDetailsSummary(visible=False)
            
            
#            panel.setData(data)
        
            
            p = p + 1
        
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
            
        self.includedFilesList.SetSize((-1,0))
        self.includedFilesList.Hide()


        
        
        
        

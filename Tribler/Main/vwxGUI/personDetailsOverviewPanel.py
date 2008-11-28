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
from Tribler.Main.vwxGUI.filesItemPanel import *
#from Tribler.vwxGUI.filesItemPanel import ThumbnailViewer
#from Tribler.vwxGUI.standardDetails import *
#from Tribler.Overlay.MetadataHandler import MetadataHandler
from time import time
from traceback import print_exc
import urllib

class personDetailsOverviewPanel(wx.Panel):
    def __init__(self, *args, **kw):
        print 'class personDetailsOverviewPanel'        
        self.initDone = False
        
        self.elementsName = [ 'title', 'description', 'detailsInfo', 'detailsInfoHeader', 'includedFiles', 'includedFilesHeader', 'thumbField', 'addAsFriend',
                             'lastConnected', 'discFiles', 'discPersons', 'numberOfDownloads', 'prefFiles', 'prefFilesHeader', 'prefItems','prefFilesCf', 'prefFilesHeaderCf', 'prefItemsCf',
                             'lastConnectedField', 'discFilesField', 'discPersonsField', 'numberOfDownloadsField']

        self.elements = {}
        self.data = {} #data related to profile information, to be used in details panel
        
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility        
        #self.PeerData_manager = PeerDataManager.getInstance(self.utility)
        #self.data_manager = TorrentDataManager.getInstance(self.utility)
#        self.filesItemPanel = filesItemPanel
#        self.standardDetails = standardDetails.getInstance()
#        self.standardDetails.setTorrentThumb = standardDetails.setTorrentThumb
        
#        self.metadatahandler = MetadataHandler.getInstance()
#        self.ThumbnailViewer = ThumbnailViewer
        self.firstTimeInitiate = False
        self.fileItemCf = []
        self.fileItemOf = [] 
        self.activeCf = None
        self.activeOf = None  
        self.actualSize = None
        
        self.cfListExist = False        
        self.ofListExist = False     
        
        self.cfList = []
        self.ofList = []
        
        self.triblerStyles = TriblerStyles.getInstance()
        self.mm = IconsManager.getInstance()
        
        
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
        self.addComponents()
        self.bartercast_db = BarterCastDBHandler()
        self.mydb = MyPreferenceDBHandler()
        self.mm = MugshotManager.getInstance()
        self.initDone = True
        
        
    def addComponents(self):
         
        self.title = self.getGuiElement('title')        
        self.description = self.getGuiElement('description')        
        self.addAsFriend = self.getGuiElement('addAsFriend')        
        
        self.detailsInfoHeader = self.getGuiElement('detailsInfoHeader')        
        self.detailsInfo = self.getGuiElement('detailsInfo')
        
        self.includedFilesHeader = self.getGuiElement('includedFilesHeader')        
        self.includedFiles = self.getGuiElement('includedFiles')        
        
        self.lastConnected = self.getGuiElement('lastConnected')
        self.discFiles = self.getGuiElement('discFiles')
        self.discPersons = self.getGuiElement('discPersons')
        self.numberOfDownloads = self.getGuiElement('numberOfDownloads')
        
        self.lastConnectedField = self.getGuiElement('lastConnectedField')
        self.discFilesField = self.getGuiElement('discFilesField')
        self.discPersonsField = self.getGuiElement('discPersonsField')
        self.numberOfDownloadsField = self.getGuiElement('numberOfDownloadsField')
        
        self.prefFiles = self.getGuiElement('prefFiles')
        self.prefFilesHeader = self.getGuiElement('prefFilesHeader')
        self.prefItems = self.getGuiElement('prefItems')
        self.prefItems.mm = self.mm
        
        self.prefFilesCf = self.getGuiElement('prefFilesCf')
        self.prefFilesHeaderCf = self.getGuiElement('prefFilesHeaderCf')
        self.prefItemsCf = self.getGuiElement('prefItemsCf')
        self.prefItemsCf.mm = self.mm
                
        

    def getGuiElement(self, name):
        if not self.elements.has_key(name) or not self.elements[name]:
            print "[fileDetailsOverviewPanel] gui element %s not available" % name
            print 'er is geen guiElement die zo heet'
            return None
        return self.elements[name]
    
    def indexXRCelements(self):
        for element in self.elementsName:
            xrcElement = xrc.XRCCTRL(self, element)
            if not xrcElement:
                print 'fileDetailsOverviewPanel: Error: Could not identify xrc element:',element
            self.elements[element] = xrcElement        
    
    def setData(self, permid):
        
        self.indexXRCelements()
        self.addComponents()
        self.data = self.PeerData_manager.getPeerData(permid)

        
#        (torrent_dir,torrent_name) = self.metadatahandler.get_std_torrent_dir_name(torrent)
#        torrent_filename = os.path.join(torrent_dir, torrent_name)
#        self.filesItemPanel.loadMetadata(self.data,torrent_filename)
#        
#        print loadAzureusMetadataFromTorrent()
        

        
        
        # Styling and set Static text.
        self.triblerStyles.setDarkText(self.title)     
        self.triblerStyles.setDarkText(self.description)
        
        # Styling and set Static text.
        self.triblerStyles.titleBar(self.detailsInfoHeader)     
        self.triblerStyles.titleBar(self.detailsInfo)
        
        self.triblerStyles.titleBar(self.includedFilesHeader)
        self.triblerStyles.titleBar(self.includedFiles)
        
        self.triblerStyles.titleBar(self.prefFiles)
        self.triblerStyles.titleBar(self.prefFilesHeader)
        
        self.triblerStyles.titleBar(self.prefFilesCf)
        self.triblerStyles.titleBar(self.prefFilesHeaderCf)
        
        # sending item name also, to make it possible to translate in TriblerStyles.py
        self.triblerStyles.setDarkText(self.lastConnected, text= self.getGuiElement('lastConnected').GetName())        
        self.triblerStyles.setDarkText(self.discFiles, text= self.getGuiElement('discFiles').GetName())
        self.triblerStyles.setDarkText(self.discPersons, text= self.getGuiElement('discPersons').GetName())
        self.triblerStyles.setDarkText(self.numberOfDownloads, text= self.getGuiElement('numberOfDownloads').GetName())

        # set torrent data:
        self.triblerStyles.setDarkText(self.lastConnectedField, text= '---')        
        self.triblerStyles.setDarkText(self.discFilesField, text= '---')
        self.triblerStyles.setDarkText(self.discPersonsField, text= '---')
        self.triblerStyles.setDarkText(self.numberOfDownloadsField, text= '---')
        
        self.triblerStyles.setDarkText(self.prefItems, text= '---')        
        self.triblerStyles.setDarkText(self.prefItemsCf, text= '---')        

    
        # ========   THUMB ======== 
        # (thumb code copied  from standardDetails)

        try:
            bmp = None
            # Check if we have already read the thumbnail and metadata information from this torrent file
            if self.data.get('metadata'):
                bmp = self.data['metadata'].get('ThumbnailBitmap')
            else:
                pass
#                    guiserver = GUIServer.getInstance()
#                    guiserver.add_task(lambda:self.loadMetadata(item),0)
            if not bmp:
                bmp = self.mm.get_default('personsMode','DEFAULT_THUMB')
            
            thumbField = self.getGuiElement("thumbField")
            thumbField.setBitmap(bmp)
            width, height = thumbField.GetSize()
            d = 1
            thumbField.border = [wx.Point(0,d), wx.Point(width-d, d), wx.Point(width-d, height-d), wx.Point(d,height-d), wx.Point(d,0)]
            thumbField.Refresh()
#                wx.CallAfter(thumbField.Refresh)
            
        except:
            print_exc()
            
        #self.guiUtility.standardDetails.setTorrentThumb( 'filesMode', self.data, self.getGuiElement('thumbField'))
        
        
        # ========   TITLE ========
        self.title.SetLabel(self.data.get('content_name',''))
        self.title.Wrap(-1) # doesn't appear to work
          
        # ========   FRIEND BUTTON ========
        
        if self.data.get('friend') is not None:
            if self.data['friend']:
                isfriend = self.mm.get_default('personsMode','ISFRIEND_BITMAP')
                isfriend_clicked = self.mm.get_default('personsMode','ISFRIEND_CLICKED_BITMAP')
                self.addAsFriend.switchTo(isfriend,isfriend_clicked)
            else:
                self.addAsFriend.switchBack()
                

#        self.guiUtility.standardDetails.setDownloadbutton(self.data, item = self.download)        
        
        # ========   DESCRIPTION ========
###        descrtxt = ''
###        flag = False
###        if not self.data.get('web2'):
###            if 'metadata' in self.data:
####                metadata = self.info
###                metadata = self.data['metadata']
###
###
###
###                encoding = None
###                if 'encoding' in metadata and metadata['encoding'].strip():
###                    encoding = metadata['encoding']
###
###                flag = False
###                for key in ['comment','comment-utf8','Description']: # reverse priority
###                    if key in metadata: # If vuze torrent
###                        print 'tb Vuze torrent----------------------------'
###                        tdescrtxt = metadata[key]
###                        if key == 'comment-utf8':
###                            tencoding = 'utf_8'
###                        else:
###                            tencoding = encoding
###                        descrtxt = bin2unicode(tdescrtxt,tencoding)
###                        flag = True
###                if not flag:
###                    if 'source' in self.data:
###                        s = self.data['source']
###                        if s != '':
###                            if s == 'BC':
###                                s = 'Received from other user'
###                            descrtxt = "Source: "+s
###
###                        flag = True
###        else:
###            descrtxt = self.data['description']
###            flag = True
###         
###        if not flag:
###            if 'source' in self.data:
###                s = self.data['source']
###                if s == 'BC':
###                    s = 'Received from other user'
###                descrtxt = "Source: "+s
###        
###        
###        self.description.SetLabel(descrtxt)
###        self.description.Wrap(-1)        
        
        self.description.SetLabel('')
        
        # ========  LAST CONNECTED ========
        if self.data.get('online'):
             self.lastConnectedField.SetLabel( 'online')
        elif self.data.get('last_connected') is not None:
            if self.data['last_connected'] < 0:
                self.lastConnectedField.SetLabel('never seen')
            else:
                self.lastConnectedField.SetLabel('conn.  %s' % friendly_time(self.data['last_connected']))
        else:
            self.lastConnectedField.SetLabel('unknown')
               
        # ========  DISCOVERED TORRENTS ========
        if 'ntorrents' in self.data:
            n = unicode(self.data['ntorrents'])
            if not n or n == '0':
                n = '?'
            self.discFilesField.SetLabel(n)
        
        # ========  DISCOVERED PEERS ========
        if 'npeers' in self.data:
            n = unicode(self.data['npeers'])
            if not n or n=='0':
                n = '?'
            self.discPersonsField.SetLabel(n)
        
        # ========   NUMBER OF DOWNLOADS ======== 
        
        hash_list = self.guiUtility.peer_manager.getPeerHistFiles(permid)
        nprefs = max(self.data.get('nprefs',0), len(hash_list))

        self.numberOfDownloadsField.SetLabel(str(nprefs)) 
        
        # ========   PREF ITEMS / DOWNLOAD HISTORY ======== 
        # code is copied from standardDetails.fillTorrentLists

        self.ofList = []
        self.cfList = []
        
        torrent_list = []
                
        hash_list = self.guiUtility.peer_manager.getPeerHistFiles(permid)
        torrent_list = self.data_manager.getTorrents(hash_list)
        print 'tb > length hash_list = %s' % len(hash_list)
        print 'tb > length torrent_list = %s' % len(torrent_list)
        
        for torrent in torrent_list:
            if torrent.get('myDownloadHistory', False):
                if len(self.cfList) < 5 :
                    self.cfList.append(torrent)
            else:
                if len(self.ofList) < 5 :
                    self.ofList.append(torrent)  
      
        self.setCfList()
        self.setOfList()
        
        
        self.firstTimeInitiate = True
        
    def mouseAction4(self, event, itemName=''):     
        print itemName
        self.fileItemOf[itemName].select(rowIndex = itemName, colIndex='')
        self.fileItemOf[itemName].SetSize((-1, 140)) 
        if self.activeOf != None:            
            self.fileItemOf[self.activeOf].deselect(rowIndex = self.activeOf, colIndex='')
            self.fileItemOf[self.activeOf].SetSize((-1, 22))        
        
        self.activeOf = itemName
        self.prefItems.Layout()
        self.actualSize = self.GetSize()
        print 'tb > self.actualSize() 1= %s' % self.actualSize
        self.Layout()
        print 'tb > self.actualSize() 2= %s' % self.actualSize
        
    def mouseAction5(self, event, itemName=''):     
        print itemName
        self.fileItemCf[itemName].select(rowIndex = itemName, colIndex='')
        self.fileItemCf[itemName].SetSize((-1, 140)) 
        if self.activeCf != None:            
            self.fileItemCf[self.activeCf].deselect(rowIndex = self.activeCf, colIndex='')
            self.fileItemCf[self.activeCf].SetSize((-1, 22))        
        
        self.activeCf = itemName
        self.prefItemsCf.Layout()
        self.actualSize = self.GetSize()
        print 'tb > self.actualSize() 1= %s' % self.actualSize
        self.Layout()
        print 'tb > self.actualSize() 2= %s' % self.actualSize
        

    def setOfList(self, itemName=''):
        #        self.recomItems.DestroyChildren()
        if self.firstTimeInitiate == False :
            print 'tb > FIRST TIME setOfList'
            self.vSizerOfListItems = wx.BoxSizer(wx.VERTICAL)
          
        if self.activeOf  != None:
            self.fileItemOf[self.activeOf].deselect(rowIndex = self.activeOf, colIndex='')
            self.fileItemOf[self.activeOf].SetSize((-1, 22))    
        
        s=0 
#        print 'tb > self.ofList = %s' % self.ofList   
        for torrent in self.ofList:
            
            # item aanmaken
            if len(self.fileItemOf) <= s :
                self.fileItemOf.append(FilesItemPanel(self.prefItems, 'keyfun', name=s))                
                print self.fileItemOf[s].GetParent()
                # invoegen in bepaalde (lege) sizer
                self.vSizerOfListItems.Add(self.fileItemOf[s], 0, wx.ALL|wx.EXPAND|wx.FIXED_MINSIZE, 2)  
              
            self.fileItemOf[s].setData(torrent)
            self.fileItemOf[s].thumb.setTorrent(torrent)
            self.fileItemOf[s].Show()
            self.fileItemOf[s].SetSize((-1, 22))
            self.fileItemOf[s].Layout()         
            s = s + 1
            
        for u in range(s,len(self.fileItemOf)):
            self.fileItemOf[u].Hide()
        
        if self.ofListExist == False:
            self.prefItems.SetSizer(self.vSizerOfListItems)
            self.ofListExist = True
        
        self.prefItems.SetSize((-1, 5*22+140)) 
        
    def setCfList(self, itemName=''):
        #        self.recomItems.DestroyChildren()
        if self.firstTimeInitiate == False :
            print 'tb > FIRST TIME setCfList'
            self.vSizerCfListItems = wx.BoxSizer(wx.VERTICAL)
          
        if self.activeCf  != None:
            self.fileItemCf[self.activeCf].deselect(rowIndex = self.activeCf, colIndex='')
            self.fileItemCf[self.activeCf].SetSize((-1, 22))    
        
        t=0 
#        print 'tb > self.CfList = %s' % self.cfList   
        for torrent in self.cfList:
            
            # item aanmaken
            if len(self.fileItemCf) <= t:
                self.fileItemCf.append(FilesItemPanel(self.prefItemsCf, 'keyfun', name=t))                
                print self.fileItemCf[t].GetParent()
                # invoegen in bepaalde (lege) sizer
                self.vSizerCfListItems.Add(self.fileItemCf[t], 0, wx.ALL|wx.EXPAND|wx.FIXED_MINSIZE, 2)  
              
            self.fileItemCf[t].setData(torrent)
            self.fileItemCf[t].thumb.setTorrent(torrent)
            self.fileItemCf[t].Show()
            self.fileItemCf[t].SetSize((-1, 22))
            self.fileItemCf[t].Layout()         
            t = t + 1
            
        for v in range(t,len(self.fileItemCf)):
            self.fileItemCf[v].Hide()
        
        if self.cfListExist == False:
            self.prefItemsCf.SetSizer(self.vSizerCfListItems)
            self.cfListExist = True
        
        self.prefItemsCf.SetSize((-1, 5*22+140)) 
            
            
    def addAsFriendAction(self):
#        print 'tb > AddAsFriend in personDetailsOverviewPanel'
        
        if self.data.get('friend') is not None:
            if self.data['friend']:
                isfriend = self.mm.get_default('personsMode','ISFRIEND_BITMAP')
                isfriend_clicked = self.mm.get_default('personsMode','ISFRIEND_CLICKED_BITMAP')
                self.addAsFriend.switchTo(isfriend,isfriend_clicked)
            else:
                self.addAsFriend.switchBack()
        # add the current user selected in details panel as a friend
###        if self.mode in ["personsMode","friendsMode"]:
###            peer_data = self.item
###            if peer_data is not None and peer_data.get('permid'):
###                #update the database
####                    if not self.peer_manager.isFriend(peer_data['permid']):
####                        self.contentFrontPanel.frienddb.deleteFriend(self.data['permid'])
####                    else:
###                if self.guiUtility.peer_manager.isFriend(peer_data['permid']):
###                    bRemoved = self.guiUtility.peer_manager.deleteFriendwData(peer_data)
###                    if DEBUG:
###                        print >>sys.stderr,"standardDetails: removed friendship with",`peer_data['content_name']`,":",bRemoved
###                else:
###                    bAdded = self.guiUtility.peer_manager.addFriendwData(peer_data)
###                    if DEBUG:
###                        print >>sys.stderr,"standardDetails: added",`peer_data['content_name']`,"as friend:",bAdded
###                
###                #should refresh?
###                self.guiUtility.selectPeer(peer_data)
        
#    def updateNumFilesInTextFields(self, cfList, ofList):
#        numItems = [cfList.GetItemCount(), ofList.GetItemCount()]
#        self.getGuiObj('commonFiles').SetLabel(self.utility.lang.get('commonFiles') % numItems[0])
#        nprefs = max(self.getData().get('nprefs',0), numItems[1])
#        self.getGuiObj('alsoDownloaded').SetLabel(self.utility.lang.get('alsoDownloaded') % (numItems[1], nprefs))
    
        
        
        
        

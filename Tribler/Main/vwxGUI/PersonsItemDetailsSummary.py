import wx, os
from Tribler.Main.vwxGUI.tribler_topButton import tribler_topButton, SwitchButton
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.TriblerStyles import TriblerStyles
from Tribler.Main.vwxGUI.TextButton import *
#from Tribler.Main.vwxGUI.torrentManager import TorrentDataManager
#from Tribler.vwxGUI.filesItemPanel import ThumbnailViewer
#from Tribler.Overlay.MetadataHandler import MetadataHandler




class PersonsItemDetailsSummary(wx.Panel):
    
    def __init__(self, parent, mode):
        wx.Panel.__init__(self, parent, -1)
        self.guiUtility = GUIUtility.getInstance()
#        self.metadatahandler = MetadataHandler.getInstance()
#        self.thumbSummary = thumbSummary
        self.utility = self.guiUtility.utility 
        self.data_manager = None # TorrentDataManager.getInstance(self.utility)
        
        self.mode = mode
        self.addComponents()
        
        self.setData()
        
        
    def addComponents(self):
        self.triblerStyles = TriblerStyles.getInstance()                
        self.SetMinSize((300,40))
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)               
        
        self.vSizer = wx.BoxSizer(wx.VERTICAL)  
        
        if self.mode == 'persons':
            self.thumbSummary = self.Parent.ThumbnailViewer(self.Parent, 'personsItemSummary')
        elif self.mode == 'friends':
            self.thumbSummary = self.Parent.FriendThumbnailViewer(self.Parent, 'personsItemSummary')
        self.thumbSummary.setBackground(wx.BLACK)
        self.thumbSummary.SetSize((80,80))
        
        self.vSizer.Add(self.thumbSummary, 0, wx.LEFT, 10)
        self.hSizer.Add(self.vSizer, 0, wx.TOP, 25) 
        
        self.hSizer.Add([5,1],1,wx.ALL,0)
              
        self.vSizer2 = wx.BoxSizer(wx.VERTICAL)
        self.vSizer2.Add([100,1],0,wx.ALL,0)
        self.discFiles            = wx.StaticText(self, -1, 'Discovered files:')
        self.discPersons          = wx.StaticText(self, -1, 'Discovered persons:')
        self.numberDownloads      = wx.StaticText(self, -1, 'Number of downloads')
       
        self.triblerStyles.setDarkText(self.discFiles)                
        self.triblerStyles.setDarkText(self.discPersons)                
        self.triblerStyles.setDarkText(self.numberDownloads)                

#        self.vSizer2.Add([100,10], 0, wx.BOTTOM|wx.FIXED_MINSIZE, 1)
        self.vSizer2.Add(self.discFiles, 0, wx.BOTTOM, 1)        
        self.vSizer2.Add(self.discPersons, 0, wx.BOTTOM, 1)        
        self.vSizer2.Add(self.numberDownloads, 0, wx.BOTTOM, 1)        
                       
        self.hSizer.Add(self.vSizer2, 0, wx.TOP|wx.RIGHT|wx.LEFT|wx.EXPAND, 3)
        
        self.vSizer3 = wx.BoxSizer(wx.VERTICAL)
        self.vSizer3.Add([50,1],0,wx.ALL,0)
        self.theDiscFiles        = wx.StaticText(self, -1, 'good (DVD)', wx.Point(0,0),wx.Size(50,-1), wx.ALIGN_RIGHT | wx.ST_NO_AUTORESIZE )
        self.theDiscPersons      = wx.StaticText(self, -1, 'English', wx.Point(0,0),wx.Size(50,-1), wx.ALIGN_RIGHT | wx.ST_NO_AUTORESIZE )
        self.theNumberDownloads  = wx.StaticText(self, -1, '13 included',wx.Point(0,0),wx.Size(50,-1), wx.ALIGN_RIGHT | wx.ST_NO_AUTORESIZE )       
        self.moreInfo            = TextButton(self, name = "more info >")

        self.triblerStyles.setDarkText(self.theDiscFiles)                
        self.triblerStyles.setDarkText(self.theDiscPersons)                
        self.triblerStyles.setDarkText(self.theNumberDownloads)                

#        self.vSizer3.Add([100,10], 0, wx.BOTTOM|wx.FIXED_MINSIZE, 1)
        self.vSizer3.Add(self.theDiscFiles, 0, wx.BOTTOM, 1)        
        self.vSizer3.Add(self.theDiscPersons, 0, wx.BOTTOM, 1)        
        self.vSizer3.Add(self.theNumberDownloads, 0, wx.BOTTOM, 1)        
        self.vSizer3.Add(self.moreInfo, 0, wx.BOTTOM|wx.EXPAND, 1)
        self.hSizer.Add(self.vSizer3, 0, wx.TOP|wx.RIGHT|wx.EXPAND, 3)

        self.SetSizer(self.hSizer)
        self.SetAutoLayout(1);  
        self.Layout()
        
    def setData(self):        
        item = self.Parent.data
#        descriptionText = self.Parent.data['metadata'].get('Description')
#        if descriptionText != None:
#            self.Description.SetLabel(descriptionText)
#            self.Description.Wrap(-1)
##            self.Description.Wrap(300)
#        else:   
#            self.Description.SetLabel('no description available')
#npeers
#ntorrents
#nprefs
        self.thumbSummary.setData(self.Parent.data, summary='filesItemSummary')
        if 'npeers' in item:
            n = unicode(item['npeers'])
            if not n or n=='0':
                n = '?'
            self.theDiscFiles.SetLabel(n)
        if 'ntorrents' in item:
            n = unicode(item['ntorrents'])
            if not n or n == '0':
                n = '?'
            self.theDiscPersons.SetLabel(n)
#        if 'nprefs' in item:


        permid = item['permid']
        hash_list = self.guiUtility.peer_manager.getPeerHistFiles(permid)
        nprefs = max(item.get('nprefs',0), len(hash_list))
        
        print 'tb> hashlist = %s' % len(hash_list)
        print 'tb> npref    = %s' % item.get('nprefs',0)
        print 'tb> nprefs    = %s' % nprefs
            
        self.theNumberDownloads.SetLabel(str(nprefs)) 



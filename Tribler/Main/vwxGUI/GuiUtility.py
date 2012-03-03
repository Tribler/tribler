# Written by Jelle Roozenburg, Maarten ten Brinke, Arno Bakker, Lucian Musat 
# Modified by Niels Zeilemaker
# see LICENSE.txt for license information

import random
import wx
import os
import sys
from wx import xrc

from Tribler.__init__ import LIBRARYNAME

from Tribler.Category.Category import Category
from Tribler.Core.BuddyCast.buddycast import BuddyCastFactory
from Tribler.Core.CacheDB.SqliteCacheDBHandler import UserEventLogDBHandler
from Tribler.Core.Search.SearchManager import split_into_keywords,\
    fts3_preprocess
from Tribler.Main.Utility.GuiDBHandler import startWorker
from Tribler.Main.vwxGUI.SearchGridManager import TorrentManager, ChannelManager, LibraryManager
from Tribler.Video.VideoPlayer import VideoPlayer
from time import time
from Tribler.Main.vwxGUI import forceWxThread
from Tribler.Main.Utility.GuiDBTuples import RemoteChannel
from Tribler.Main.vwxGUI.TorrentStateManager import TorrentStateManager

DEBUG = False

class GUIUtility:
    __single = None
    
    def __init__(self, utility = None, params = None):
        if GUIUtility.__single:
            raise RuntimeError, "GUIUtility is singleton"
        GUIUtility.__single = self 
        
        # do other init
        self.utility = utility
        self.vwxGUI_path = os.path.join(self.utility.getPath(), LIBRARYNAME, 'Main', 'vwxGUI')
        self.utility.guiUtility = self
        self.params = params
        self.frame = None

        # videoplayer
        self.videoplayer = VideoPlayer.getInstance()
        self.useExternalVideo = False

        # current GUI page
        self.guiPage = 'home'
        # previous pages
        self.oldpage = []

        # port number
        self.port_number = None

        # firewall
        self.firewall_restart = False # ie Tribler needs to restart for the port number to be updated

        # Recall improves by 20-25% by increasing the number of peers to query to 20 from 10 !
        self.max_remote_queries = 20    # max number of remote peers to query
        
        self.current_search_query = ''
    
    def getInstance(*args, **kw):
        if GUIUtility.__single is None:
            GUIUtility(*args, **kw)
        return GUIUtility.__single
    getInstance = staticmethod(getInstance)
    
    def register(self):
        self.torrentsearch_manager = TorrentManager.getInstance(self)
        self.channelsearch_manager = ChannelManager.getInstance()
        self.library_manager = LibraryManager.getInstance(self)
        self.torrentstate_manager = TorrentStateManager.getInstance(self)
        
        self.torrentsearch_manager.connect(self.utility.session, self.library_manager, self.channelsearch_manager)
        self.channelsearch_manager.connect(self.utility.session, self.torrentsearch_manager)
        self.library_manager.connect(self.utility.session, self.torrentsearch_manager, self.channelsearch_manager)
        self.torrentstate_manager.connect(self.torrentsearch_manager, self.library_manager, self.channelsearch_manager)
    
    def ShowPlayer(self, show):
        if self.frame.videoparentpanel:
            if show != self.frame.videoparentpanel.IsShown():
                self.frame.videoparentpanel.Show(show)
    
    @forceWxThread
    def ShowPage(self, page, *args):
        if page == 'settings':
            xrcResource = os.path.join(self.vwxGUI_path, 'settingsDialog.xrc')
            res = xrc.XmlResource(xrcResource)
            dialog = res.LoadDialog(None, 'settingsDialog')
            if not dialog: #failed to load dialog
                return

            dialog.Centre()
            dialog.ShowModal()
            dialog.Destroy()
            self.frame.top_bg.selectTab(page)
        
        elif page != self.guiPage:
            self.frame.top_bg.selectTab(page)

            self.oldpage.append(self.guiPage)
            if len(self.oldpage) > 3:
                self.oldpage.pop(0)
                
            self.frame.Freeze()
            
            if page == 'search_results':
                #Show list
                self.frame.searchlist.Show()
                
            elif self.guiPage == 'search_results':
                #Hide list
                self.frame.searchlist.Show(False)
            
            if page == 'channels':
                if self.frame.channelcategories:
                    selectedcat = self.frame.channelcategories.GetSelectedCategory()
                else:
                    selectedcat = ''

                if selectedcat == 'My Channel':
                    self.frame.channelcategories.Select(1)
                    
                self.frame.channelselector.ShowItems(True)
                self.frame.channellist.Show()
                self.frame.channelcategories.Quicktip('All Channels are ordered by popularity. Popularity is measured by the number of Tribler users which have marked this channel as favorite.')
                    
            elif self.guiPage == 'channels':
                self.frame.channellist.Show(False)
                self.frame.channelselector.ShowItems(False)
            
            if page == 'mychannel':
                self.frame.channelcategories.Quicktip('This is your channel, other Tribler users can find this channel by searching for your username')
                
                #Show list
                self.frame.managechannel.SetChannelId(self.channelsearch_manager.channelcast_db._channel_id)
                self.frame.managechannel.Show()
                
            elif self.guiPage == 'mychannel':
                self.frame.managechannel.Show(False)
                self.frame.managechannel.Reset()
                
            if page == 'managechannel':
                self.frame.managechannel.Show()
                
            elif self.guiPage == 'managechannel':
                self.frame.managechannel.Show(False)
                self.frame.managechannel.Reset()
            
            if page == 'selectedchannel':
                self.frame.selectedchannellist.Show()

            elif self.guiPage == 'selectedchannel':
                self.frame.selectedchannellist.Show(False)
                if self.frame.channelcategories and page not in ['playlist','managechannel']:
                    self.frame.selectedchannellist.Reset()
            
            if page == 'playlist':
                self.frame.playlist.Show()
                
            elif self.guiPage == 'playlist':
                self.frame.playlist.Show(False)
                self.frame.playlist.Reset()
                
            if page == 'my_files':
                #Open infohash
                if args:
                    self.frame.librarylist.GetManager().expand(args[0])
                
                #Show list
                self.frame.librarylist.Show()
            elif self.guiPage == 'my_files':
                #Hide list
                self.frame.librarylist.Show(False)
            
            if page == 'home':
                self.frame.home.ResetSearchBox()
                self.frame.home.Show()
            elif self.guiPage == 'home':
                self.frame.home.Show(False)
            
            if page == 'stats':
                self.frame.stats.Show()
            elif self.guiPage == 'stats':
                self.frame.stats.Show(False)
            
            #show player on these pages
            if not self.useExternalVideo:
                if page in ['my_files', 'mychannel', 'selectedchannel', 'channels', 'search_results', 'playlist', 'managechannel']:
                    self.ShowPlayer(True)
                else:
                    self.ShowPlayer(False)
            
            self.guiPage = page
            self.frame.Layout()
            self.frame.Thaw()
    
        #Set focus to page
        if page == 'search_results':
            self.frame.searchlist.Focus()
            
            if args:
                self.frame.searchlist.total_results = None
                self.frame.searchlist.SetKeywords(args[0])
            
        elif page == 'channels':
            self.frame.channellist.Focus()
        elif page == 'selectedchannel':
            self.frame.selectedchannellist.Focus()
        elif page =='my_files':
            self.frame.librarylist.Focus()

    @forceWxThread
    def GoBack(self, scrollTo = None, topage = None):
        if topage:
            self.oldpage.pop()
        else:
            if len(self.oldpage) > 0:
                topage = self.oldpage.pop()
            else:
                return
        
        if topage == 'channels':
            category = self.frame.channellist.GetManager().category
            categories = ['Popular','New','Favorites','All','My Channel', 'Updated', 'Search']
            if category in categories:
                category = categories.index(category) + 1
                self.frame.channelcategories.Select(category, False)
        
        if topage == 'search_results':
            self.frame.top_bg.selectTab('results')
        elif topage in ['channels', 'selectedchannel', 'mychannel']:
            self.frame.top_bg.selectTab('channels')
        else:
            self.frame.top_bg.selectTab(topage)
        
        self.ShowPage(topage)
        self.oldpage.pop() #remove curpage from history
        
        if scrollTo:
            self.ScrollTo(scrollTo)
    
    def dosearch(self, input = None):
        if input == None:
            sf = self.frame.top_bg.searchField
            if sf is None:
                return
            
            input = sf.GetValue()
        
        if input:
            input = input.strip()
            if input == '':
                return
        else:
            return
        self.frame.top_bg.searchField.SetValue(input)
            
        if input.startswith("http://"):
            if self.frame.startDownloadFromUrl(str(input)):
                self.frame.top_bg.searchField.Clear()
                self.ShowPage('my_files')
            
        elif input.startswith("magnet:"):
            if self.frame.startDownloadFromMagnet(str(input)):
                self.frame.top_bg.searchField.Clear()
                self.ShowPage('my_files')
                
        else:
            fts3feaures, old_keywords = fts3_preprocess(input)
            remotekeywords = split_into_keywords(old_keywords)
            remotekeywords = [keyword for keyword in remotekeywords if len(keyword) > 1]
            
            safekeywords = ' '.join(remotekeywords + fts3feaures)
            
            if len(safekeywords)  == 0:
                self.Notify('Please enter a search term', wx.ART_INFORMATION)
                
            else:
                self.frame.top_bg.StartSearch()
                self.current_search_query = remotekeywords
                if DEBUG:
                    print >>sys.stderr,"GUIUtil: searchFiles:", remotekeywords, time()
                
                self.frame.searchlist.Freeze()         
               
                self.torrentsearch_manager.setSearchKeywords(remotekeywords, fts3feaures)
                self.channelsearch_manager.setSearchKeywords(remotekeywords)
                
                self.frame.searchlist.Reset()
                self.ShowPage('search_results', safekeywords)
                
                #We now have to call thaw, otherwise loading message will not be shown.
                self.frame.searchlist.Thaw()
                
                #Peform local search
                self.torrentsearch_manager.set_gridmgr(self.frame.searchlist.GetManager())
                self.channelsearch_manager.set_gridmgr(self.frame.searchlist.GetManager())
                
                wx.CallAfter(self.torrentsearch_manager.refreshGrid)
                
                if len(remotekeywords) > 0:
                    #Start remote search
                    #Arno, 2010-02-03: Query starts as Unicode
                    q = u'SIMPLE '
                    for kw in remotekeywords:
                        q += kw+u' '
                    q = q.strip()
                    
                    nr_peers_connected = self.utility.session.query_connected_peers(q, self.sesscb_got_remote_hits, self.max_remote_queries)
                    
                    #Indicate expected nr replies in gui, use local result as first
                    self.frame.searchlist.SetMaxResults(nr_peers_connected+1, remotekeywords)
                    self.frame.searchlist.NewResult()
                    
                    if len(input) > 1: #do not perform remote channel search for single character inputs
                        q = 'CHANNEL k '
                        for kw in remotekeywords:
                            q += kw+' '
                        self.utility.session.query_connected_peers(q,self.sesscb_got_channel_hits)
    
    @forceWxThread
    def showChannelCategory(self, category, show = True):
        manager = self.frame.channellist.GetManager()
        manager.SetCategory(category, True)
        
        if show:
            self.ShowPage('channels')
            
    @forceWxThread
    def showLibrary(self, show = True):
        manager = self.frame.librarylist.GetManager()
        manager.refresh()
        
        if show:
            self.ShowPage('my_files')
    
    def showChannelFromId(self, channel_id):
        def db_callback():
            channel = self.channelsearch_manager.getChannel(channel_id)
            self.showChannel(channel)
            
        startWorker(None, db_callback)
    
    def showChannelFromDispCid(self, channel_cid):
        def db_callback():
            channel = self.channelsearch_manager.getChannelByCid(channel_cid)
            self.showChannel(channel)
            
        startWorker(None, db_callback)
        
    def showChannelFromPermid(self, channel_permid):
        def db_callback():
            channel = self.channelsearch_manager.getChannelByPermid(channel_permid)
            self.showChannel(channel)
            
        startWorker(None, db_callback)
        
    @forceWxThread
    def showChannel(self, channel):
        if channel:
            self.frame.top_bg.selectTab('channels')
            
            manager = self.frame.selectedchannellist.GetManager()
            manager.refresh(channel)
            
            self.ShowPage('selectedchannel')
            
            if isinstance(channel, RemoteChannel):
                self.showChannelFromPermid(channel.permid)
            
    def showChannels(self):
        self.frame.top_bg.selectTab('channels')
        self.ShowPage('channels')
    
    @forceWxThread
    def showChannelResults(self, data_channel):
        self.frame.top_bg.selectTab('channels')
        self.frame.channelcategories.DeselectAll()
        self.frame.channelcategories.searchSelected = True
        
        def subscribe_latestupdate_sort(a, b):
            val = cmp(a.modified, b.modified)
            if val == 0:
                return cmp(a.name, b.name)
            return val
        
        data = data_channel.values()
        data.sort(subscribe_latestupdate_sort, reverse = True)
        
        manager = self.frame.channellist.GetManager()
        manager.SetCategory('searchresults')
        manager.refresh(data)
        
        self.ShowPage('channels')
    
    @forceWxThread
    def showManageChannel(self, channel):
        self.frame.managechannel.SetChannel(channel)
        self.ShowPage('managechannel')
    
    @forceWxThread
    def showPlaylist(self, data):
        self.frame.playlist.Set(data)
        self.ShowPage('playlist')
        
    def OnList(self, goto_end, event = None):
        lists = {'channels': self.frame.channellist,'selectedchannel': self.frame.selectedchannellist ,'mychannel': self.frame.managechannel, 'search_results': self.frame.searchlist, 'my_files': self.frame.librarylist}
        if self.guiPage in lists and lists[self.guiPage].HasFocus():
            lists[self.guiPage].ScrollToEnd(goto_end)
        elif event:
            event.Skip()
    
    def ScrollTo(self, id):
        lists = {'channels': self.frame.channellist,'selectedchannel': self.frame.selectedchannellist ,'mychannel': self.frame.managechannel, 'search_results': self.frame.searchlist, 'my_files': self.frame.librarylist}
        if self.guiPage in lists:
            lists[self.guiPage].ScrollToId(id)
            
    def Notify(self, msg, icon= -1):
        self.frame.top_bg.Notify(msg, icon)
     
    def sesscb_got_remote_hits(self,permid,query,hits):
        # Called by SessionCallback thread 

        if DEBUG:
            print >>sys.stderr,"GUIUtil: sesscb_got_remote_hits",len(hits)

        # 22/01/10 boudewijn: use the split_into_keywords function to split.  This will ensure
        # that kws is unicode and splits on all 'splittable' characters
        if len(hits) > 0:
            kwstr = query[len('SIMPLE '):]
            kws = split_into_keywords(kwstr)
            self.torrentsearch_manager.gotRemoteHits(permid, kws, hits)
        self.frame.searchlist.NewResult()
        
    def sesscb_got_channel_hits(self, permid, query, hits):
        '''
        Called by SessionCallback thread from RemoteQueryMsgHandler.process_query_reply.

        @param permid: the peer who returnd the answer to the query
        @param query: the keywords of the query that originated the answer
        @param hits: the complete answer retruned by the peer
        '''
        # Called by SessionCallback thread 
        if DEBUG:
            print >>sys.stderr,"GUIUtil: sesscb_got_channel_hits",len(hits)

        def callback(delayedResult, permid, query):
            dictOfAdditions = delayedResult.get()
            
            if len(dictOfAdditions) > 0:
                # 22/01/10 boudewijn: use the split_into_keywords function to
                # split.  This will ensure that kws is unicode and splits on
                # all 'splittable' characters
                kwstr = query[len("CHANNEL x "):]
                kws = split_into_keywords(kwstr)

                self.channelsearch_manager.gotRemoteHits(permid, kws, dictOfAdditions)
            
        # Let channelcast handle inserting items etc.
        channelcast = BuddyCastFactory.getInstance().channelcast_core
        channelcast.updateChannel(permid, query, hits, callback)

    def ShouldGuiUpdate(self):
        if self.frame.ready:
            return self.frame.GUIupdate
        return True

    #TODO: should be somewhere else
    def set_port_number(self, port_number):
        self.port_number = port_number
    def get_port_number(self):
        return self.port_number
    
    def toggleFamilyFilter(self, state = None): 
        catobj = Category.getInstance()
        ff_enabled = not catobj.family_filter_enabled()
        #print 'Setting family filter to: %s' % ff_enabled
        if state is not None:
            ff_enabled = state    
        catobj.set_family_filter(ff_enabled)
        
    def getFamilyFilter(self):
        catobj = Category.getInstance()
        return catobj.family_filter_enabled()  
    
    def set_firewall_restart(self,b):
        self.firewall_restart = b

# Written by Lucian Musat
# see LICENSE.txt for license information

"""Module that supposable creates a view of persons similar to the view of files,
with all persons available in main view and an information bar to the right """

from ContentFrontPanel import GridPanel,DetailPanel,ImagePanel
from Utility.utility import Utility
from Tribler.CacheDB import CacheDBHandler, SynDBHandler
from Tribler.unicode import dunno2unicode
import wx, math, time, os, sys, threading
from traceback import print_exc
#from abcfileframe import TorrentDataManager
from Tribler.utilities import *
from safeguiupdate import DelayedInvocation
from wx.lib.stattext import GenStaticText as StaticText
from Tribler.unicode import *
from copy import deepcopy
from Tribler.utilities import friendly_time, show_permid
import copy
from Utility.constants import *
import traceback
from threading import Thread
from time import time, ctime
#BORDER_EXPAND = wx.ALL|wx.GROW
#BORDER = wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.ALIGN_LEFT

        
def setCustomFont( component, type):
    font = component.GetFont()
    default_size = font.GetPointSize()
    #print "font default size=",default_size
    if default_size > 12:
        normal_size = default_size - 1
        small_size = default_size - 2
    else:
        normal_size = default_size
        small_size = default_size
    if type == "title":
        font.SetPointSize(default_size)
        font.SetWeight(wx.BOLD)
    elif type == "normal":
        font.SetPointSize(normal_size)
    elif type == "small":
        font.SetPointSize(small_size)
        font.SetWeight(wx.BOLD)
    component.SetFont(font)

def getAgeingValue(old_time):
    try:    
        old_time = int(old_time)
        if old_time < 0 :
            return 0
        curr_time = time()
        diff = int(curr_time - old_time)
    except: 
        return 0
    if diff < 60:
        return 6048 - diff
    elif diff < 3600:
        return 6048 - 60 + 6 - int(diff/10)
    if diff < 604800:
        return 6048 - 360 + 36 - int(diff/100)
    else:   
        return 0
    
def getAgeingColor(old_time):
    curr_time = time()
    try:    
        old_time = int(old_time)
        diff = int(curr_time - old_time)
    except: 
        return 'grey'
    if diff < 3600: 
        return "#719b6a" #"green"
    elif diff < 86400:
        return "#ddd76f" #"yellow"
    elif diff < 604800:
        return "#dda16c" #"orange"
    else:   
        return "#9b301b" #"red"

DEBUG = False
def debug(message):
    if DEBUG:
        print message

class PersonFrontPanel(wx.Panel, DelayedInvocation):
    """
        Combines a GridPanel, CategoryPanel and DetailPanel
        to some extent, the copy of ContentFrontPanel
    """
    def __init__(self, parent):
        
        self.utility = parent.utility
        self.imagepath = os.path.join(self.utility.getPath(), 'icons')+'/'
        wx.Panel.__init__(self, parent, -1)
        #self.type = 'similarity'#similarity' #?
        DelayedInvocation.__init__(self)
        self.doneflag = threading.Event()
        self.neverAnyContent = True
        
        self.categorykey = ''  #no category
        self.itemkey = 'person_item'
        #self.data_manager = TorrentDataManager.getInstance(self.utility) #?
        #self.mypref_db = self.utility.mypref_db
        #self.torrent_db = self.utility.torrent_db

        self.top20similar = []
#        self.count_AddData = 0
        self.MAX_CALLS = 50 #max number of calls that are done during an treat callback event
        ## initialization
        self.MIN_CALLBACK_INT = 1 #min callback interval: minimum time in seconds between two invocations on the gui from the callback
        self.start_callback_int = -1 #init the time variable for the callback function
        self.callback_dict = {} #empty list for events
        self.data_not_ready = True #indicates that the data array isn't yet initialized so no changes should be done on it by the database callback function
        self.peersdb = SynDBHandler.SynPeerDBHandler(updateFun = self.callbackPeerChange)#CacheDBHandler.PeerDBHandler()
        self.prefdb = CacheDBHandler.PreferenceDBHandler()
        self.mydb = CacheDBHandler.MyPreferenceDBHandler()
        self.tordb = CacheDBHandler.TorrentDBHandler()
        self.frienddb = CacheDBHandler.FriendDBHandler()
        self.MAX_MIN_PEERS_NUMBER = 1900
        self.MAX_MAX_PEERS_NUMBER = 2100

        self.addComponents()

        searchingContentStub = {'content_name':self.utility.lang.get('searching_content')}
        self.grid.setData([searchingContentStub])
        
        
    def callbackPeerChange(self, permid, mode):
        """callback function to be notified when changes are made in the peers database
            mode is add, update or delete
        """
        
        start_time = time()
        #get updated peer data from database
        # mode = {add, update, delete}
        #return
        # instead of treating each message when it arrives, just put them in a hash
        # that has the permid as key and mode as value and when some time passed
        # invoke an event
        if self.start_callback_int == -1:
            self.start_callback_int = start_time
        #add the new event
        #check if already another opperation existing for this person
#        if permid in self.callback_dict:
#            index = find_content_in_dictlist(self.grid.data,{'permid':permid},'permid')
#            peer_name = show_permid_short(permid)
#            if index >= 0 and self.grid.data[index].get('content_name')!=None:
#                peer_name = self.grid.data[index].get('content_name')
#            debug( "peer %s already callback with %s" % (peer_name, self.callback_dict[permid]))
#===============================================================================
#        if len(self.callback_dict)==50:
#            traceback.print_stack()
#===============================================================================
        self.callback_dict[permid] = mode
        if start_time - self.start_callback_int > self.MIN_CALLBACK_INT and not self.data_not_ready:
            treat_dict = {}
            count = 0
            for k,v in self.callback_dict.iteritems():
                treat_dict[k]=v
                count = count + 1
                if count >= self.MAX_CALLS:
                    break
            for k,v in treat_dict.iteritems():
                del self.callback_dict[k]
            #send the callback event
            self.invokeLater(self.treatCallback, [treat_dict])
            #reset the start time
            self.start_callback_int = start_time
            #self.callback_dict = {}
        return
  
        end_time = time()
        print "callback took",(end_time-start_time),"s"
    #only needed if category panel is present
    #def reorder(self, type):
        #self.type = type
        #self.sortData()
        
    def treatCallback(self, permid_dict):
#        debug("treat callback with %d peers" % (len(permid_dict)))
#        self.count_AddData = 0
        for permid, mode in permid_dict.iteritems():
            peer_data = None
            if mode in ['update', 'add']:
                #first get the new data from database
                peer_data = self.peersdb.getPeer(permid)
                #extra check, the permid should already be there
                if not peer_data or peer_data['connected_times'] == 0:
                    continue
                if peer_data.get('permid')==None:
                    peer_data['permid'] = permid
                #arrange the data some more: add content_name, rank and so on
                self.preparePeer(peer_data)

            if mode in ['update', 'delete', 'hide']:    # update the detail panel
                if self.detailPanel.showsPeer(permid):
                    # if mode is 'delete' or 'hide', peer_data is None, then it cleans the detail panel
                    self.detailPanel.setData(peer_data)
            
            if mode in ['update', 'add']:   # update the item panel
                self.addData(peer_data)
            else:
                #print "**** callback in persons", mode, len(self.grid.data), ctime(time())
                self.deleteData(permid)
#        debug("add data called %d times" % (self.count_AddData))
        
    def addComponents(self):
        self.SetBackgroundColour(wx.WHITE)
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        gridColumns = 3
        
        self.detailPanel = PeerDetailPanel(self, self.utility) # DetailPanel(self, self.utility)
        self.grid = GridPanel(self, gridColumns)
        #change the cell panel in staticgridpanel
        def createCellPanel():
            return PeerPanelUserFriendly(self.grid.staticGrid)
        self.grid.staticGrid.createCellPanel = createCellPanel
        def updateSelection():
            """Deselect all torrentPanels, but the one selected in detailPanel
            If no torrent is selected in detailPanel, let first in grid be selected
            changed to use permid not title
            """            
            obj = self.grid.staticGrid
            #title = None
            pid = None
            # Select first item
            if not obj.detailPanel.data:
                try:
                    firstItem = obj.panels[0][0].data
                    if firstItem:
                        obj.detailPanel.setData(firstItem)
#                        title = obj.detailPanel.data.get('content_name')
                        pid = obj.detailPanel.data.get('permid')
                except:
                    pass
            else:
#                title = self.detailPanel.data.get('content_name')
                pid = obj.detailPanel.data.get('permid')
            for row in obj.panels:
                for pan in row:
                    try:
                        panelid = pan.data['permid']
#                        paneltitle = pan.data['content_name']
                    except:
                        panelid = None
#                        paneltitle = None
                    if panelid != pid or panelid == None:
#                    if paneltitle != title or paneltitle == None:
                        pan.deselect()
                    else:
                        pan.select()        
        self.grid.staticGrid.updateSelection = updateSelection
        #categories = self.data_manager.category.getCategoryKeys()
        #ourCategories = ['Video', 'VideoClips', 'Audio', 'Picture', 'Compressed', 'Document', 'other', 'xxx']
        #double check our categories
        #for cat in ourCategories:
        #    if cat not in categories:
        #        ourCategories.remove(cat)
        #self.categoryPanel = CategoryPanel(self, ourCategories, self.utility.lang.get('mypref_list_title'))
        vSizer = wx.BoxSizer(wx.VERTICAL)
        #vSizer.Add(self.categoryPanel, 0, BORDER_EXPAND, 1)
        vSizer.Add(self.grid, 1, wx.ALL|wx.GROW, 1)
        
        self.hSizer.Add(vSizer, 3, wx.ALL|wx.GROW, 1)
        self.hSizer.Add(self.detailPanel, 1, wx.ALL|wx.GROW, 1)
        
        self.SetSizer(self.hSizer);self.SetAutoLayout(1);self.Layout();
        self.Refresh()
        
    def addData(self, peer_data):
        """When a new peer is discovered, the grid is not directly reordered. 
        The new peer is added at the end of the gridlist
        This function also updates current info"""
#        start_time = time()
#        if DEBUG:
#            print 'add/update data for',repr(peer_data)
#        self.count_AddData = self.count_AddData + 1
        i = find_content_in_dictlist(self.grid.data, peer_data, 'permid')
        if i != -1:
            self.grid.data[i] = peer_data
            self.grid.setData(self.grid.data, False)
            self.neverAnyContent = False
        else:
            if peer_data.get('permid') and peer_data['connected_times'] > 0: #check if this is a valid peer to be added
                # Check if we have to remove the dummy content
                if len(self.grid.data) == 1 and self.grid.data[0].get('content_name') == self.utility.lang.get('searching_content'):
                    del self.grid.data[0]
                    # set the correct information in the detail panel
                    #self.detailPanel.setData(torrent)
                    self.neverAnyContent = False
                # Only add healthy peers to grid
                # but insert them at their place based on rank value... ?
                self.grid.data.append(peer_data)
                self.grid.setData(self.grid.data, False)
#        end_time = time()
#        print "addData took",(end_time-start_time),"s"
        
    def deleteData(self, permid):
        # removes item from list, wrong name
        remove_torrent_from_list(self.grid.data, {'permid':permid}, 'permid')
        self.grid.setData(self.grid.data, False)

    def checkFilesStatus(self, localdata):
        # add some other informations: like user's files and active torrents
        # for that, get the torrents data
        for i in xrange(len(localdata)):
            try:
                files = self.prefdb.getPrefList(localdata[i]['permid'])
                #get informations about each torrent file based on it's hash
                #compute contors for torrents that have only hashvalue (with status unknown), the ones that are invalid and the ones that are valid
                unknownTCounter = 0
                validTCounter = 0
                invalidTCounter = 0
                torrents_info = self.tordb.getTorrents(files)
                for torrent in torrents_info:
                    if (not 'torrent_name' in torrent) or (not 'info' in torrent) or (len(torrent['info']) == 0) or (not 'name' in torrent['info']):
                        unknownTCounter += 1
                    elif torrent['status'] == 'dead':
                        invalidTCounter += 1
                    elif torrent['status'] == 'good':
                        validTCounter += 1
                    else:
                        unknownTCounter += 1
                localdata[i]['torrents_count'] = {'good':validTCounter,'unknown':unknownTCounter,'dead':invalidTCounter}
                # check to see what npref means, it should: npref = validTCounter+unknownTCounter+invalidTCounter
                #if localdata[i]['npref'] == validTCounter+unknownTCounter+invalidTCounter: 
                #    bEqual = True 
                #else: 
                #    bEqual = False
                #print 'for peer',localdata[i]['content_name'],'npref = validTCounter+unknownTCounter+invalidTCounter is', bEqual
                # prints True
            except:
                localdata[i]['torrents_count'] = {'good':0,'unknown':0,'dead':0}
                
    def preparePeer(self, peer_data):
        if peer_data['name']!=None and len(peer_data['name'])>0:
            peer_data['content_name']=dunno2unicode(peer_data['name'])
        else:
            peer_data['content_name']= 'peer %s' % show_permid_short(peer_data['permid'])#'[%s:%s]' % (localdata[i]['ip'],str(localdata[i]['port']))
        peer_data['friend'] = self.frienddb.isFriend(peer_data['permid'])#permid in self.friend_list
        # compute the maximal value for similarity
        # in order to be able to compute top-n persons based on similarity
        if peer_data.get('similarity'):
            if peer_data['similarity']>self.MaxSimilarityValue:
                self.MaxSimilarityValue = peer_data['similarity'] #should recompute percents
        else:
            peer_data['similarity']=0
        if self.MaxSimilarityValue > 0:
            peer_data['similarity_percent'] = int(peer_data['similarity']*100.0/self.MaxSimilarityValue)
        else:
            peer_data['similarity_percent'] = 0
        #recompute rank
        #peer_data['rank_value'] = self.compute_rankval(peer_data)
        #check to see if top20 needs to be updated
#===============================================================================
#        j = 0
#        while j<len(self.top20similar):
#            if self.top20similar[j]['similarity'] < peer_data['similarity']:
#                break
#            j = j+1
#        self.top20similar.insert(j,peer_data)
#        # check if too many
#        if len(self.top20similar)>20:
#            self.top20similar = self.top20similar[:20]
#===============================================================================
        if self.updateTopList([peer_data], self.top20similar, 'similarity'):
            #refresh the grid
            self.grid.setData(self.grid.data, False)
        
    def prepareData(self, peer_list=None):
        # first, obtain values
        ##update
        myprefs = self.mydb.getPrefList()
        if peer_list is None:
            peer_list = self.peersdb.getPeerList()
        key = ['permid', 'name', 'ip', 'similarity', 'last_seen', 'connected_times', 'buddycast_times', 'port']
        tempdata = self.peersdb.getPeers(peer_list, key)

        self.MaxSimilarityValue = -1
        localdata = []
        #select only tribler peers
        for i in xrange(len(tempdata)):
            if tempdata[i].get('permid') and tempdata[i]['connected_times'] > 0:
                peer_data = tempdata[i]
                if peer_data['name']!=None and len(peer_data['name'])>0:
                    peer_data['content_name']=dunno2unicode(peer_data['name'])
                else:
                    peer_data['content_name']= 'peer %s' % show_permid_short(peer_data['permid'])#'[%s:%s]' % (localdata[i]['ip'],str(localdata[i]['port']))
                peer_data['friend'] = self.frienddb.isFriend(peer_data['permid'])#permid in self.friend_list
                # compute the maximal value for similarity
                # in order to be able to compute top-n persons based on similarity
                if peer_data.get('similarity'):
                    if peer_data['similarity']>self.MaxSimilarityValue:
                        self.MaxSimilarityValue = peer_data['similarity']
                else:
                    peer_data['similarity']=0
                localdata.append(peer_data)
        
        # compute similarity rank based on similarity with this peer relative to the greatest similarity value
        #compute the similarity rank
        # for that, create a separate ordered list with only the first 20 most similar peers
#        self.top20similar = []
        for i in xrange(len(localdata)):
            #compute the similarity percent
            if self.MaxSimilarityValue > 0:
                localdata[i]['similarity_percent'] = int(localdata[i]['similarity']*100.0/self.MaxSimilarityValue)
            else:
                localdata[i]['similarity_percent'] = 0
#            j = 0
#            while j<len(self.top20similar):
#                if self.top20similar[j]['similarity'] < localdata[i]['similarity']:
#                    break
#                j = j+1
#            self.top20similar.insert(j,localdata[i])
#            # check if too many
#            if len(self.top20similar)>20:
#                self.top20similar = self.top20similar[:20]
#        for i in range(len(self.top20similar)):
#            print "top",i,"is",self.top20similar[i]['content_name']
                
        #checkFilesStatus(localdata)
         
        #save the data information
        return localdata

    def compute_rankval(self, peer_data):
        """computes a rank value for a peer used for ordering the peers based on
        friendship, similarity, name and last seen status 
        it codifies all these parameters on bits, in the order of significance:
        1bit + 7bits + 1bit + 13bits
        returns the number obtained, the bigger the number, higher the rank
        """
        rank_value = 0
        if peer_data.get('friend')!=None and peer_data['friend']==True:
            rank_value = rank_value + 1
        # add similarity
        rank_value = (rank_value << 7)
        if peer_data.get('similarity_percent')!= None:
            rank_value = rank_value + int(peer_data['similarity_percent'])
        # add name ordering
        rank_value = (rank_value << 1)
        if peer_data.get('content_name')!=None and not peer_data['content_name'].startswith('peer'):
            rank_value = rank_value + 1
        # add last seen
        rank_value = (rank_value << 13)
        if peer_data.get('last_seen')!= None:
            rank_value = rank_value + getAgeingValue(peer_data['last_seen'])
#        if DEBUG:
#            print "peer",peer_data['content_name'],(peer_data.get('friend') and "is" or "is not"),\
#            "friend, with a similarity of",peer_data['similarity_percent'],"%, and last seen",\
#            friendly_time(peer_data['last_seen']),"resulting rank value:",rank_value
        return rank_value
          
  
    def updateTopList(self, data_list, top_list, key, equal_key='permid', max_list_length=20):
        """for each element in data_list, add it to top_list ordered descending based on the key
        it returns true or false if changes have been made to top_list"""
        bChange = False
        for element in data_list:
            #check where to add the element, and also where is already inserted
            index = 0
            llen = len(top_list)
            indexInsertAt = llen
            indexIsAt = -1
            while index < llen:
                if top_list[index][equal_key] == element[equal_key]:
                    indexIsAt = index
                if top_list[index][key] < element[key]:
                    indexInsertAt = index
                if indexIsAt != -1 and indexInsertAt < llen:
                    break #both indexes are computed so no reason to continue
                index = index + 1
            if indexInsertAt != indexIsAt: #if on the same position, do nothing
                if indexIsAt != -1 and indexIsAt < llen-1 and element[key] == top_list[indexIsAt+1][key]:
                    continue #if is equal with the ones until insertion point, no need to do it
                if indexIsAt != -1:
                    #move from one position to another
                    top_list.pop(indexIsAt)
                    if indexIsAt < indexInsertAt:
                        indexInsertAt = indexInsertAt - 1
                    bChange = True #there is a change in the list
                if indexInsertAt < max_list_length: #don't insert an element that will be removed
                    top_list.insert(indexInsertAt, element)
                    bChange = True #there is a change in the list
            #reduce the size of the list
            while len(top_list)>max_list_length:
                top_list.pop()
        #print len(top_list), [ elem['content_name'] for elem in top_list]
        return bChange
  
    def sortData(self, filtered):
        """ rewritten almost from scratch 
            gets the data, it orders it and if there is no data shows the 'searching_content' stub
            the ordering method is not based on only one criterion, but several
            based on the compute_rankval function
            it also limits the number of peers to 2000
        """
        #for peer in filtered:
        #    peer['rank_value'] = self.compute_rankval(peer)
            
        filtered = sort_dictlist(filtered, 'similarity', 'decrease')
        
        self.updateTopList(filtered, self.top20similar, 'similarity')
        #limit the number of peers so that it wouldn't occupy alot of memory
        #max_number = int((self.MAX_MAX_PEERS_NUMBER+self.MAX_MIN_PEERS_NUMBER)/2)
        #if len(filtered)>max_number:
        #    filtered = filtered[:max_number]
        if filtered:
            self.neverAnyContent = False
        elif self.neverAnyContent:
            searchingContentStub = {'content_name':self.utility.lang.get('searching_content')}
            filtered.append(searchingContentStub)
        self.grid.setData(filtered)
        self.data_not_ready = False
      
class PeerDetailPanel(wx.Panel):
    """
    This panel shows peer details for the current selected peer in the grid. 
    Details contain: Name, status(?), icon(?), email(?), overall download(?),
    overall upload(?), attributes(from cache), download history (from buddycast),
    friends (taste buddies or connections or even friends...) as icons, and other
    available info 
    """
    def __init__(self, parent, utility):
        wx.Panel.__init__(self, parent, -1, style=wx.SIMPLE_BORDER)

        self.utility = utility
        self.parent = parent
        self.data = None
        self.torrentsList = [] #list of infohashes that are in the other files list
        self.oldSize = None
        self.addComponents()
        self.Centre()
        self.Show()

    def addComponents(self):
        self.Show(False)
        self.SetBackgroundColour(wx.WHITE)
        self.Bind(wx.EVT_SIZE, self.onResize)
        
        vSizerAll = wx.BoxSizer(wx.VERTICAL)
        
        hSizerTop = wx.BoxSizer(wx.HORIZONTAL)
        
        vSizerTopName = wx.BoxSizer(wx.VERTICAL)
        
        # Set title
        self.title = StaticText(self,-1,"")#,wx.Point(3,111),wx.Size(49,13))
        setCustomFont(self.title, "title")
        #add title to sizer
        vSizerTopName.Add(self.title, 0, wx.BOTTOM|wx.EXPAND, 2)
        
        # Set status
        hSizerStatus = wx.BoxSizer(wx.HORIZONTAL)
        self.statusPic = ColorImgPanel(self, 20, 20, "grey")
        self.statusPic.SetToolTipString(self.utility.lang.get("peer_status_tooltip", giveerror=False))
        self.statusTxt = StaticText(self, -1, 'never seen online')
        setCustomFont(self.statusTxt, "small")
        self.statusTxt.SetToolTipString(self.utility.lang.get("peer_status_tooltip", giveerror=False))
        hSizerStatus.Add(self.statusPic, 0, wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, 5)
        hSizerStatus.Add(self.statusTxt, 0, 0, 0)

        #add status to sizer
        vSizerTopName.Add(hSizerStatus, 0,0,0)#1, wx.ALL|wx.EXPAND|wx.ALIGN_LEFT|wx.ALIGN_TOP, 1)
 
        # Add friend icon, disabled...
        self.isFriendPic = ImagePanel(self)
        self.isFriendPic.SetEnabled(False)
        self.isFriendPic.SetBitmap("joe24.png")
        self.isFriendPic.SetToolTipString(self.utility.lang.get("peer_friend_tooltip", giveerror=False))
        #add friend status to sizer
        vSizerTopName.Add(self.isFriendPic, 0,wx.ALL,3)
        
        #add name sizer to top sizer
        hSizerTop.Add(vSizerTopName, 1, wx.EXPAND, 2)
        
        #Set icon
        self.peerIcon = ImagePanel(self)
        self.peerIcon.SetWindowStyle(wx.SIMPLE_BORDER)
        self.peerIcon.SetBitmap("tribler.jpg")
        #add icon to sizer
        hSizerTop.Add(self.peerIcon, 0, 0, 0)
        
        vSizerAll.Add(hSizerTop, 0, wx.EXPAND, 0)
        
        #add the info sizer
        infoText = wx.StaticText(self, -1, "info")
        setCustomFont( infoText, "small")
        vSizerAll.Add(infoText, 0, wx.EXPAND, 0)

#        vSizerInfo = wx.StaticBoxSizer(infoText, wx.VERTICAL)
        vSizerInfo = wx.BoxSizer(wx.VERTICAL)
        
        #add the profile text
        profileText = StaticText(self, -1, "profile")
        setCustomFont( profileText, "small")
        
        vSizerInfo.Add( profileText, 1, wx.EXPAND|wx.BOTTOM|wx.TOP, 4)
        
        # Set attributes
        self.connected_times = StaticText(self,-1,"")
        setCustomFont( self.connected_times, "small")
        self.connected_times.SetToolTipString(self.utility.lang.get("peer_connected_times_tooltip", giveerror=False))
        #add text to sizer
        vSizerInfo.Add(self.connected_times, 0, wx.ALL|wx.EXPAND, 2)
        
        self.buddycast_times = StaticText(self,-1,"")
        setCustomFont( self.buddycast_times, "small")
        self.buddycast_times.SetToolTipString(self.utility.lang.get("peer_buddycast_times_tooltip", giveerror=False))
        #add text to sizer
        vSizerInfo.Add(self.buddycast_times, 0, wx.ALL|wx.EXPAND, 2)
        
        hSizerSim = wx.BoxSizer(wx.HORIZONTAL)
        self.simPic = ImagePanel(self)
        self.simPic.SetBitmap("love.png")
        self.simPic.SetToolTipString(self.utility.lang.get("peer_similarity_tooltip", giveerror=False))
        self.simTxt = StaticText(self, -1, '? %')
        setCustomFont(self.simTxt, "small")
        self.simTxt.SetToolTipString(self.utility.lang.get("peer_similarity_tooltip", giveerror=False))
        hSizerSim.Add(self.simTxt, 0, wx.RIGHT, 5)
        hSizerSim.Add(self.simPic, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        #add text to sizer
        vSizerInfo.Add(hSizerSim, 0, wx.ALL|wx.EXPAND, 2)

        #add the library text
        libraryText = StaticText(self, -1, "library")
        setCustomFont( libraryText, "small")
        
        vSizerInfo.Add( libraryText, 1, wx.EXPAND|wx.BOTTOM|wx.TOP, 4)

        #add files that you and this peer have
        vSizerComFiles = wx.BoxSizer(wx.VERTICAL)
        
        common_files = StaticText(self,-1,"Same files:")
        setCustomFont( common_files, "small")
        common_files.SetToolTipString(self.utility.lang.get("peer_common_files_tooltip", giveerror=False))
        vSizerComFiles.Add( common_files, 0, wx.TOP|wx.BOTTOM, 3)
        #add common files list
        self.cfList = wx.ListCtrl( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.LC_REPORT|wx.SIMPLE_BORDER|wx.LC_SINGLE_SEL|wx.LC_NO_HEADER )
        self.cfList.SetSizeHints( -1, 50, -1, 50, incW=-1, incH=-1)
        self.cfList.InsertColumn(0, 'torrent')
        #self.cfList.SetColumnWidth(0, wx.LIST_AUTOSIZE)
        self.cfList.Bind(wx.EVT_SIZE, self.onListResize)
        self.cfList.Bind(wx.EVT_LIST_ITEM_SELECTED, self.onListSelected)
        #self.cfList.Bind(wx.EVT_LEFT_DCLICK, self.onListDClick)
        
        if sys.platform == 'win32':
            #print 'Using windows code'
            vSizerComFiles.Add(self.cfList, 1, wx.ALL|wx.GROW, 1)
        else:
            #print 'Using unix code'
            cfListSizer = wx.BoxSizer(wx.HORIZONTAL)
            cfListSizer.Add(self.cfList, 1, wx.ALL|wx.GROW, 0)
            vSizerComFiles.Add(cfListSizer, 1, wx.ALL|wx.GROW, 1)
        
        vSizerInfo.Add(vSizerComFiles, 0, wx.EXPAND, 2)

        #add files that only this peer has
        vSizerOtherFiles = wx.BoxSizer(wx.VERTICAL)
        
        other_files = StaticText(self,-1,"This person also downloaded:")
        setCustomFont( other_files, "small")
        other_files.SetToolTipString(self.utility.lang.get("peer_other_files_tooltip", giveerror=False))
        vSizerOtherFiles.Add( other_files, 0, wx.TOP|wx.BOTTOM, 3)
        #add common files list
        self.ofList = wx.ListCtrl( self, wx.ID_ANY, wx.DefaultPosition, wx.Size(10,150), wx.LC_REPORT|wx.SIMPLE_BORDER|wx.LC_NO_HEADER|wx.LC_SINGLE_SEL )
        self.ofList.InsertColumn(0, 'torrent')
        #self.cfList.SetColumnWidth(0, wx.LIST_AUTOSIZE)
        self.ofList.Bind(wx.EVT_SIZE, self.onListResize)
        self.ofList.Bind(wx.EVT_LIST_ITEM_SELECTED, self.onListSelected)
        self.ofList.Bind(wx.EVT_LEFT_DCLICK, self.onListDClick)
        
        if sys.platform == 'win32':
            #print 'Using windows code'
            vSizerOtherFiles.Add(self.ofList, 1, wx.ALL|wx.GROW, 1)
        else:
            #print 'Using unix code'
            ofListSizer = wx.BoxSizer(wx.HORIZONTAL)
            ofListSizer.Add(self.ofList, 1, wx.ALL|wx.GROW, 0)
            vSizerOtherFiles.Add(ofListSizer, 1, wx.ALL|wx.GROW, 1)
        
        vSizerInfo.Add(vSizerOtherFiles, 0, wx.EXPAND, 2)
        
        vSizerAll.Add( vSizerInfo, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, 2)


        self.SetSizer(vSizerAll);self.SetAutoLayout(1);self.Layout();
        for window in self.GetChildren():
            window.SetBackgroundColour(wx.WHITE)
        self.title.SetBackgroundColour(wx.Colour(220,220,220))
        infoText.SetBackgroundColour(wx.WHITE)
        #infoText.SetBackgroundColour(wx.Colour(235,235,235))
        profileText.SetBackgroundColour('#c2d7e0')
        libraryText.SetBackgroundColour('#c2d7e0')
        self.Refresh()   
        
    def setData(self, peer):
        #print 'DetailPanel.setData called by: %s' % threading.currentThread()
        # set bitmap, rating, title
        # should set empty details when there is no peer selected or the current peer was deleted
        if peer == None:
            peer = {}
        
        self.data = peer
        
        try:
            if peer.get('content_name') != None:
                self.title.SetLabel(peer['content_name'])
            else:
                self.title.SetLabel('')
            if peer.get('last_seen')!=None:
                if peer['last_seen'] < 0:
                    self.statusTxt.SetLabel("never seen online")
                    self.statusPic.changeColor('grey')
                else:
                    self.statusTxt.SetLabel("last seen\n"+friendly_time(peer['last_seen']))
                    self.statusPic.changeColor(getAgeingColor(peer['last_seen']))
            else:
                self.statusTxt.SetLabel('')
                self.statusPic.changeColor('grey')
            if peer.get("connected_times")!=None:
                self.connected_times.SetLabel("Connected times: "+str(peer["connected_times"]))
            else:
                self.connected_times.SetLabel("Connected times: ")
            if peer.get("buddycast_times")!=None:
                self.buddycast_times.SetLabel("Exchanges: "+str(peer["buddycast_times"]))
            else:
                self.buddycast_times.SetLabel("Exchanges: ")

            if peer.get('friend')!=None and peer['friend']==True:
                self.isFriendPic.SetEnabled(True)
            else:
                self.isFriendPic.SetEnabled(False)
                
            if peer.get('similarity_percent')!=None:
                self.simTxt.SetLabel('Similarity: '+str(int(peer['similarity_percent']))+"%")
            else:
                self.simTxt.SetLabel('Similarity: none')
                
            #get torrents list
            if self.data.has_key('permid'):
                self.fillTorrentLists()
                    
            self.GetSizer().Layout()
        except:
            print >>sys.stderr,'peer detail panel: Could not set data'
            print_exc(file=sys.stderr)
            print >>sys.stderr,"peer detail panel: data to set was",self.data

    def status_sort(self, t1, t2):
        val = []
        for t in [t1,t2]:
            if t['status'] == 'good':
                val.append(1)
            elif t['status'] == 'unknown':
                val.append(0)
            elif t['status'] == 'dead':
                val.append(-1)
        if len(val)==2:
            return cmp(val[1],val[0])
        return 0        

    def fillTorrentLists(self):
        try:
            # get my download history
            hist_torr = self.parent.mydb.getPrefList()
            #print hist_torr
            files = self.parent.prefdb.getPrefList(self.data['permid'])
            #live_files = self.torrent_db.getLiveTorrents(files)
            #get informations about each torrent file based on it's hash
            torrents_info = self.parent.tordb.getTorrents(files)
            for torrent in torrents_info[:]:
                if (not 'info' in torrent) or (len(torrent['info']) == 0) or (not 'name' in torrent['info']):
                    torrents_info.remove(torrent)
            #sort torrents based on status: { downloading (green), seeding (yellow),} good (blue), unknown(black), dead (red); 
            torrents_info.sort(self.status_sort)
            torrents_info = filter( lambda torrent: not torrent['status'] == 'dead', torrents_info)
            #tempdata[i]['torrents_list'] = torrents_info
            self.ofList.DeleteAllItems()
            self.cfList.DeleteAllItems()
            self.torrentsList = []
            for f in torrents_info:
                #print f
                the_list = None
                infohash = f.get('infohash')
                if infohash in hist_torr:
                    the_list = self.cfList
                else:
                    the_list = self.ofList
                index = the_list.InsertStringItem(sys.maxint, f['info']['name'])
                if the_list == self.ofList:
                    self.torrentsList.append(infohash)
                color = "black"
                if f['status'] == 'good':
                    color = "blue"
                elif f['status'] == 'unknown':
                    color = "black"
                elif f['status'] == 'dead':
                    color = "red"
                the_list.SetItemTextColour(index, color)
                #the_list.SetItemData( index, infohash)
                #self.ofList.SetStringItem(index, 1, f[1])
            if self.cfList.GetItemCount() == 0:
                index = self.cfList.InsertStringItem(sys.maxint, "No common files with this person.")
                try:
                    font = self.cfList.GetItemFont(index)
                    font.SetStyle(wx.FONTSTYLE_ITALIC)
                    self.cfList.SetItemFont(index, font)
                except:
                    pass
                self.cfList.SetItemTextColour(index, "#f0c930")
            if self.ofList.GetItemCount() == 0:
                index = self.ofList.InsertStringItem(sys.maxint, "No files advertised by this person.")
                try:
                    font = self.ofList.GetItemFont(index)
                    font.SetStyle(wx.FONTSTYLE_ITALIC)
                    self.ofList.SetItemFont(index, font)
                except:
                    pass
                self.ofList.SetItemTextColour(index, "#f0c930")
            self.onListResize(None) 
        except Exception, e:
            print e
            print_exc()
            self.ofList.DeleteAllItems()
            self.cfList.DeleteAllItems()
            self.torrentsList = []
            index = self.ofList.InsertStringItem(sys.maxint, "Error getting files list")
            self.ofList.SetItemTextColour(index, "dark red")
                
    def onListDClick(self, event):
        if event!=None:
            list = event.GetEventObject()
            item = list.GetFirstSelected()
            if item != -1 and item < len(self.torrentsList):
                #show the other panel, and select the file 
                #print "show ",list.GetItemText(item)
                infohash = self.torrentsList[item] #list.GetItemData(item)
                torrent = self.parent.tordb.getTorrent(infohash)
                torrent['infohash'] = infohash
                if self.utility.frame!=None and self.utility.frame.window!=None and self.utility.frame.window.split!=None:
                    abcpanel = self.utility.frame.window
                    abcpanel.contentPanel1.download(torrent)

                #self.utility.actions[ACTION_FILES].action()
            event.Skip()
        
    def onListResize(self, event):
        if event!=None:
            list = event.GetEventObject()
            size = list.GetClientSize()
            list.SetColumnWidth( 0, size.width)
            list.ScrollList(-100, 0) # Removes HSCROLLBAR
        else:
            list = self.cfList
            size = list.GetClientSize()
            list.SetColumnWidth( 0, size.width)
            list.ScrollList(-100, 0) # Removes HSCROLLBAR
            list = self.ofList
            size = list.GetClientSize()
            list.SetColumnWidth( 0, size.width)
            list.ScrollList(-100, 0) # Removes HSCROLLBAR
        if event!=None:
            event.Skip()
                   
    def onListSelected(self, event):
        item = event.GetItem()
        if DEBUG:
            print >>sys.stderr,"contentpanel: onListSelected",item
            print >>sys.stderr,"contentpanel: onListSelected",item.GetState()
        item.SetState(wx.LIST_STATE_SELECTED)
             
    def showsPeer(self, permid):
        return self.data is not None and self.data.get('permid', '') == permid
    
#===============================================================================
#    def breakup(self, str, ctrl, depth=0):
#        if depth > 10:
#            return str
#        
#        charWidth = ctrl.GetTextExtent(str)[0]/len(str)
#        begin = self.GetSize()[0] / charWidth - 5 # first part of the string where we break it
#        #print 'There should fit %d chars'% begin
#        
#        if len(str)<=max(begin, 5) or '\n' in str[:begin+1]:
#            return str
#        
#        for char in [' ', '.','_','[',']','(', '-', ',']:
#            i = str.find(char, begin -10)
#            if i>0 and i<=begin:
#                return str[:i]+'\n'+self.breakup(str[i:], ctrl, depth+1)
#        
#        return str[:begin]+'\n'+self.breakup(str[begin:], ctrl, depth+1)
#===============================================================================
            
    def mouseAction(self, event):
        obj = event.GetEventObject()
        if not self.data:
            return
        if obj == self.downloadPic:
            self.parent.download(self.data)
        elif obj == self.refreshButton and self.refreshButton.isEnabled():
            self.swarmText.SetLabel(self.utility.lang.get('refreshing')+'...')
            self.swarmText.Refresh()
            
            self.parent.refresh(self.data)
        #print "Clicked"
    
    def onResize(self, event):
        # redo set data for new breakup
        event.Skip(True)
#        if self.oldSize and (event.GetSize()[0] == self.oldSize[0]):
#            return
#        if not self.data:
#            return
#        self.oldSize = event.GetSize()
#        value = self.data.get('content_name', '')
        #self.title.SetLabel(self.breakup(value, self.title))
        #self.title.SetMinSize((100, 80))

class ColorImgPanel(wx.Panel):
    """draws a rectangle filling it with the specified color, and with a black
    border around it, and with the size given at birth"""
    def __init__(self, parent, width, height, color):
        wx.Panel.__init__(self, parent, -1)
        self.width = width
        self.height = height 
        self.color = color
        self.SetMinSize(wx.Size(width, height))
        wx.EVT_PAINT(self, self.OnPaint)
        self.Show()
        
    def OnPaint(self, evt):
        dc = wx.PaintDC(self)
        dc.SetPen(wx.Pen("grey"))
        dc.SetBrush(wx.Brush(self.color))
        #a normal font that seem to work fine on several platforms...
        #dc.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        dc.DrawRectangle( 0, 0, self.width, self.height)
    
    def changeColor(self, new_color):
        self.color = new_color
        self.Refresh()
        
#TORRENTPANEL_BACKGROUND = None
        
class PeerPanel(wx.Panel):
    """
    TorrentPanel shows one content item inside the StaticGridPanel
    Currently, TorrentPanel only shows torretname, seeders, leechers and size
    """
    def __init__(self, parent):
#        global TORRENTPANEL_BACKGROUND
        
        wx.Panel.__init__(self, parent, -1)
        self.detailPanel = parent.parent.detailPanel
        self.contentFrontPanel = parent.parent.parent
        self.utility = parent.parent.utility
        self.parent = parent
        self.data = None
        self.datacopy = None
        self.titleLength = 37 # num characters
        self.selected = False
        self.warningMode = False
        self.oldCategoryLabel = None
        self.addComponents()
        #self.Centre()
        self.Show()
        
    def addInfoComponent(self, type, image=None, hSizer=None):
        """ function addInfoComponent( string type, string image)
        type is one of: 'content_name', 'similarity', 'last_seen', 'connected_times', 
            'buddycast_times', 'torrents_count', 'friend'
        image is the name of the image that should be displayed next to the
            information, or None for nothing
        hSizer is the horizontal sizer that will contain the info components
        Function creates several components, brought together to represent a
            piece of information. It then adds them as a dictionary
            { text - static text, picture - image panel, image - image file name }
            to the self.infoComponents dictionary, with type as key
            """
        text = StaticText(self, -1, '')
        text.SetFont(self.fontInfo)
        if image!=None:
            picture = ImagePanel(self)
            picture.SetBitmap(image)
        else:
            picture = None
        self.infoComponents[type] = {'text':text,'picture':picture,'image':image}
        if hSizer!=None:
            if picture!=None:
                hSizer.Add(picture, 0, wx.RIGHT, 1)
            hSizer.Add(text, 0, wx.RIGHT, 15)             

    def addComponents(self):
        self.Show(False)
        #self.SetMinSize((50,50))
        self.selectedColour = wx.Colour(120,208,245)
        self.unselectedColour = wx.WHITE
        
        self.vSizer = wx.StaticBoxSizer(wx.StaticBox(self,-1,""),wx.VERTICAL)
        
        self.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        self.Bind(wx.EVT_KEY_UP, self.keyTyped)
        
        self.fontTitle = wx.Font(12,wx.FONTFAMILY_ROMAN,wx.FONTSTYLE_NORMAL,wx.BOLD,face="Verdana")
        self.fontInfo = wx.Font(9,wx.FONTFAMILY_ROMAN,wx.FONTSTYLE_NORMAL,wx.NORMAL,face="Verdana")
        # Add title
        self.title =StaticText(self,-1,"")
        #self.title.SetBackgroundColour(wx.WHITE)
        self.title.SetFont(self.fontTitle)
        self.title.SetMinSize((50,20))
        self.vSizer.Add(self.title, 0, BORDER_EXPAND, 3)
        
        # Add information about peer: 
        # last seen with a clock, 
        # connected_times with a plug, 
        # buddycast times with packets, 
        # similarity with stars,
        # friendship with heart
        # torrents exchanged... valid, unknown and dead from the history of peer
        
        # For that, create a dictionary that contains each attribute to be shown:
        self.infoComponents = {}

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.addInfoComponent( "last_seen", "clock24.png", hSizer)
        self.addInfoComponent( "connected_times", "connect24.png", hSizer)
        self.addInfoComponent( "buddycast_times", "buddycast24.png", hSizer)
        self.vSizer.Add(hSizer, 0, wx.ALL, 3)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.addInfoComponent( "similarity", "star24.png", hSizer)
        self.addInfoComponent( "friend", "friend24.png", hSizer)
        self.addInfoComponent( "torrents_count", "files24.png", hSizer)
        self.vSizer.Add(hSizer, 0, wx.ALL, 3)

        #self.SetBackgroundColour(wx.WHITE)

        self.SetSizer(self.vSizer);
        self.SetAutoLayout(1);
        self.Layout();
        self.Refresh()
        
        for window in self.GetChildren():
            window.Bind(wx.EVT_LEFT_UP, self.mouseAction)
            window.Bind(wx.EVT_KEY_UP, self.keyTyped)
                             
    def setData(self, peer):
        # set bitmap, rating, title
        
        def getValue(key, peer):
            value = peer[key]
            if key == "last_seen":
                return friendly_time(value)
            #elif key == "connected_times":
            elif key == "friend":
                if value == True:
                    return "Yes"
                else:
                    return "No"
            elif key == 'similarity':
                return "%d%%" % value
            elif key == "torrents_count":
                return "%d OK, %d ?, %d NOK" % (value['good'],value['unknown'],value['dead'])
            return value
        
        def checkValue(key, peer):
            value = peer.get(key)
            if value == None:
                return False
            if key == "friend":
                return True
            elif key == "similarity":
                return True
            elif key == "torrents_count":
                return value['good']+value['unknown']+value['dead'] > 0
            return value > 0
                    
        try:
            if self.datacopy['permid'] == peer['permid']:
                # Do not update torrents that have no new seeders/leechers/size
                if (self.datacopy['last_seen'] == peer['last_seen'] and
                    self.datacopy['connected_times'] == peer['connected_times'] and
                    self.datacopy['buddycast_times'] == peer['buddycast_times'] and #this should also include updating the number of torrents from this user (number changed => buddycast_messages changed...)
                    self.datacopy['similarity'] == peer['similarity'] and
                    self.datacopy['name'] == peer['name'] and
                    self.datacopy['ip'] == peer['ip'] and
                    self.datacopy.get('friend') == peer.get('friend')):
                    return
        except:
            pass
        
        self.data = peer
        self.datacopy = deepcopy(peer)
        
        if peer == None:
            self.vSizer.GetStaticBox().Show(False)
            peer = {}
        else:
            self.vSizer.GetStaticBox().Show(True)
    
        if peer.get('content_name'):
            title = peer['content_name'][:self.titleLength]
            #print 'title set to ',title
            self.title.Enable(True)
            self.title.SetLabel(title)
            #self.title.Wrap(-1) # no wrap
            self.title.SetToolTipString(peer['content_name'])
        else:
            self.title.SetLabel('')
            self.title.SetToolTipString('')
            self.title.Enable(False)
            
        def getUtilText( key, isNever, isLabel):
            """ gets the text from utility.lang corresponding to:
                (isNever?"never_":"") + key + (isLabel?"_label":"_tooltip")
            """
            query = ''
            if isNever:
                query = "never_"
            query = query+key
            if isLabel:
                query = query+"_label"
            else:
                query = query+"_tooltip"
            ret = self.utility.lang.get(query, giveerror=False)
            if ret == '':
                if isNever:
                    return "Never seen online"
                if isLabel:
                    return key
            return ret
            
        # iterate through each info component and update values
        for key in self.infoComponents:
            #print "key=",key,"infos=",self.infoComponents[key]
            infos = self.infoComponents[key]
            if peer.get(key) != None: 
                if infos['picture']!=None: infos['picture'].SetEnabled(True)
                infos['text'].Enable(True)
                if not checkValue(key,peer):
                    infos['text'].SetLabel(getUtilText(key, isNever=True, isLabel=True))
                    infos['text'].SetToolTipString(getUtilText(key, isNever=True, isLabel=False))
                else:
                    if infos['picture']!=None: infos['picture'].SetBitmap(infos['image'])
                    infos['text'].Enable(True)    
                    infos['text'].SetLabel("%s\n%s" % (getUtilText(key, isNever=False, isLabel=True),getValue(key,peer)))
                    infos['text'].SetToolTipString(getUtilText(key, isNever=False, isLabel=False))
            else:
                infos['text'].SetLabel('')
                infos['text'].Enable(False)
                infos['text'].SetToolTipString('')
                if infos['picture']!=None: infos['picture'].SetEnabled(False)
                
      
        self.Layout()
        self.Refresh()
        self.parent.Refresh()
        
    def select(self):
        self.selected = True
        old = self.title.GetBackgroundColour()
        if old != self.selectedColour:
            self.title.SetBackgroundColour(self.selectedColour)
            self.Refresh()
        
        
    def deselect(self):
        self.selected = False
        old = self.title.GetBackgroundColour()
        if old != self.unselectedColour:
            self.title.SetBackgroundColour(self.unselectedColour)
            self.Refresh()
    
    def keyTyped(self, event):
        if self.selected:
            key = event.GetKeyCode()
            if (key == wx.WXK_DELETE):
                if self.data:
                    if DEBUG:
                        print >>sys.stderr,'contentpanel: deleting'
                    contentPanel = self.parent.parent.parent
                    contentPanel.deleteTorrent(self.data)
        event.Skip()
        
    def mouseAction(self, event):
        print "Clicked base"
        self.SetFocus()
        if self.data:
            try:
                title = self.detailPanel.data['content_name']
            except:
                title = None
            if self.data.get('content_name','') != title:
                self.detailPanel.setData(self.data)
                self.parent.updateSelection()

class RatingImagePanel(wx.Panel):
    """draws the image specified and a number as rating"""
    def __init__(self, parent, data_panel, image_src):
        wx.Panel.__init__(self, parent, -1)
        self.data_panel = data_panel
        path = os.path.join(self.data_panel.utility.getPath(), 'icons', image_src)
        if not os.path.exists(path):
            if DEBUG:
                print >>sys.stderr,'RatingImagePanel: Image file: %s does not exist' % path
            self.bitmap = None
        else:
            bm = wx.Bitmap(path,wx.BITMAP_TYPE_ANY)
            image = wx.ImageFromBitmap(bm)
            image.Rescale(20,20)
            bm = image.ConvertToBitmap()
            self.bitmap = bm
            self.SetMinSize(self.bitmap.GetSize())
        wx.EVT_PAINT(self, self.OnPaint)
        self.Show()

    def OnPaint(self, evt):
        dc = wx.PaintDC(self)
        if self.bitmap:
            dc.DrawBitmap(self.bitmap, 0,0, True)
            #get ranking
            try:
                rank = str(data_panel.getRank())
            except:
                rank = "15"
            
            width,height = self.bitmap.GetSize()
#            dc.SetBrush(wx.WHITE_BRUSH)
#            dc.DrawEllipse(width/2-6, height/2-6, 12, 12)
            dc.SetTextForeground(wx.BLACK)
            font = self.data_panel.GetFont()
            font.SetPointSize(8)
            dc.SetFont(font)
#            dc.SetPen(wx.BLACK_PEN)
            dc.DrawLabel(rank, wx.Rect(width/2-10, height/2-10, 20, 20), alignment=wx.ALIGN_CENTER)
            
    def SetEnabled(self, e):
        pass
            
class AdvImagePanel(wx.Panel):
    """shows a bitmap; when disabled it show a grayscale version of the bitmap"""
    def __init__(self, parent, enable_tooltip=None, disable_tooltip=None, size=None):
        wx.Panel.__init__(self, parent, -1)
        self.size = size
        self.utility = parent.utility
        self.bitmap = None  # wxPython image
        self.graybm = None
        self.enabled = True
        self.en_tt = enable_tooltip
        self.di_tt = disable_tooltip
        if enable_tooltip:
            self.SetToolTipString(enable_tooltip)
        wx.EVT_PAINT(self, self.OnPaint)
        self.path = None
        self.Show()
        
    def ConvertToGreyscale(self, image):
        """convert manually to grey scale
        lr=0.299, lg=0.587, lb=0.114
        Convert to greyscale image. Uses the luminance component (Y) of the image. 
        The luma value (YUV) is calculated using (R * lr) + (G * lg) + (B * lb), 
        defaults to ITU-T BT.601"""
        """if the platform function is not available, use this one"""
        if getattr(image,"ConvertToGreyscale", None)!=None:
            return image.ConvertToGreyscale()
        lr=0.299
        lg=0.587 
        lb=0.114
        grey_image = image.Copy()
        buffer = grey_image.GetDataBuffer()
        buflen = int(len(buffer)/3)
        for i in xrange(buflen):
            luminance = chr(int( ord(buffer[3*i])*lr + ord(buffer[3*i+1])*lg + ord(buffer[3*i+2])*lb ))
            buffer[3*i]= luminance#chr(int(ord(buffer[3*i])*lr))
            buffer[3*i+1]=luminance #chr(int(ord(buffer[3*i+1])*lg))
            buffer[3*i+2]= luminance #chr(int(ord(buffer[3*i+2])*lb))
        return grey_image

    def SetEnabled(self, e):
        if e != self.enabled:
            self.enabled = e
            if self.enabled:
                self.SetToolTipString(self.en_tt)
            else:
                self.SetToolTipString(self.di_tt)
            """
            if not self.enabled:
                self.SetMinSize((0,0))
            else:
                if self.bitmap:
                    self.SetMinSize(self.bitmap.GetSize())
                else:
                    self.SetMinSize((0,0))
            """
            self.Refresh(True)
            
    def isEnabled(self):
        return self.enabled
    
    def SetBitmap(self, filename):
        path = os.path.join(self.utility.getPath(), 'icons', filename)
        if self.path == path:
            return
        else:
            self.path = path
        if not os.path.exists(path):
            if DEBUG:
                print >>sys.stderr,'advimagepanel: Image file: %s does not exist' % path
            self.bitmap = None
            self.graybm = None
            return
        bm = wx.Bitmap(path,wx.BITMAP_TYPE_ANY)
        image = wx.ImageFromBitmap(bm)
        if self.size != None and bm != None:
            image.Rescale(self.size[0], self.size[1])
            bm = image.ConvertToBitmap()
        self.bitmap = bm
        if self.bitmap:
            self.SetMinSize(self.bitmap.GetSize())
        else:
            self.SetMinSize((0,0))
        grayimg = self.ConvertToGreyscale(image)
        if grayimg!=None:
            self.graybm = grayimg.ConvertToBitmap()
        #self.Refresh() # Do not refresh before panel is shown and inited
        
    def OnPaint(self, evt):
        dc = wx.PaintDC(self)
        if self.bitmap and self.enabled:
            dc.DrawBitmap(self.bitmap, 0,0, True)
        elif self.graybm and not self.enabled:
            dc.DrawBitmap(self.graybm, 0, 0, True)

class PeerPanelUserFriendly( wx.Panel):

    def __init__(self, parent):
        global TORRENTPANEL_BACKGROUND
        
        wx.Panel.__init__(self, parent, -1)
        self.detailPanel = parent.parent.detailPanel
        self.contentFrontPanel = parent.parent.parent
        self.utility = parent.parent.utility
        self.parent = parent
        self.data = None
        self.datacopy = None
        self.titleLength = 37 # num characters
        self.selected = False
        self.warningMode = False
        self.oldCategoryLabel = None
        self.addComponents()
        #self.Centre()
        self.Show()
        
    def select(self):
        self.selected = True
        old = self.title.GetBackgroundColour()
        if old != self.selectedColour:
            self.title.SetBackgroundColour(self.selectedColour)
            self.Refresh()
        
    def deselect(self):
        self.selected = False
        old = self.title.GetBackgroundColour()
        if old != self.unselectedColour:
            self.title.SetBackgroundColour(self.unselectedColour)
            self.Refresh()


    def mouseAction(self, event):
        self.SetFocus()
        if self.data:
            bFriendStatusChanged = False
            if event.GetEventObject() == self.isFriendPic:
                bFriendStatusChanged = True
                """notify main panel that this user should become a friend or should be removed from the friends list"""
            if bFriendStatusChanged:
                #change also the database
                if self.isFriendPic.isEnabled():
                    bFriend = False
                else:
                    bFriend = True
                self.data['friend']=bFriend
                self.isFriendPic.SetEnabled(bFriend)
                #update the database
                if self.contentFrontPanel.frienddb.isFriend(self.data['permid']):
                    self.contentFrontPanel.frienddb.deleteFriend(self.data['permid'])
                else:
                    self.contentFrontPanel.frienddb.addFriend(self.data['permid'])
            #check by peerid, not content_name
#===============================================================================
#            try:
#                title = self.detailPanel.data['content_name']
#            except:
#                title = None
#            if self.data.get('content_name') != title or bFriendStatusChanged:
#===============================================================================
            try:
                pid = self.detailPanel.data['permid']
            except:
                pid = None
            if self.data.get('permid') != pid or bFriendStatusChanged:
                self.detailPanel.setData(self.data)
                self.parent.updateSelection()
        event.Skip()
        
    def addComponents(self):
        #print "add components in user friendly peer panel"
        self.Show(False)
        self.emptyStaticBox = wx.StaticBox(self,-1,"", wx.Point(0,0), wx.Size(1,1))
        self.emptyStaticBox.SetBackgroundColour(wx.WHITE)
        self.SetBackgroundColour(wx.WHITE)

        #self.SetMinSize((50,50))
        self.selectedColour = wx.Colour(120,208,245)
        self.unselectedColour = wx.WHITE
        
        vSizerBig = wx.BoxSizer(wx.VERTICAL)

        inner_panel = wx.Panel(self)
        inner_panel.utility = self.utility
        inner_panel.SetBackgroundColour(wx.WHITE)
        self.inner_panel = inner_panel

#        self.vSizer = wx.StaticBoxSizer(wx.StaticBox(self, -1,""),wx.VERTICAL)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        
        self.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        self.Bind(wx.EVT_SIZE, self.onResize)
        
        # Add title
        self.title =StaticText(inner_panel,-1,"")#self,-1,"")
        self.title.SetBackgroundColour(wx.WHITE)
        setCustomFont( self.title, "title")
        #self.title.SetMinSize((50,20))

        vSizer.Add(self.title, 1, wx.ALL|wx.EXPAND, 3)
        
        # Add attributes horizontally
        hAttrSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.simPic = ImagePanel(inner_panel)#self)
        self.simPic.SetBitmap("love.png")
        self.simPic.SetToolTipString(self.utility.lang.get("peer_similarity_tooltip", giveerror=False))
        self.simTxt = StaticText(inner_panel, -1, '? %')#self, -1, '? %')
        self.simTxt.SetBackgroundColour(wx.WHITE)
        setCustomFont(self.simTxt, "normal")
        self.simTxt.SetToolTipString(self.utility.lang.get("peer_similarity_tooltip", giveerror=False))
        self.statusPic = ColorImgPanel(inner_panel, 17, 13, "grey")#self, 17, 13, "grey")
        self.statusPic.SetToolTipString(self.utility.lang.get("peer_status_tooltip", giveerror=False))
        self.statusTxt = StaticText(inner_panel, -1, 'never seen online')#self, -1, 'never seen online')
        self.statusTxt.SetBackgroundColour(wx.WHITE)
        setCustomFont(self.statusTxt, "normal")
        self.statusTxt.SetToolTipString(self.utility.lang.get("peer_status_tooltip", giveerror=False))
        # Add friend icon, disabled...
        tooltip_friend= self.utility.lang.get("peer_friend_tooltip", giveerror=False)
        tooltip_nofriend = self.utility.lang.get("peer_nofriend_tooltip", giveerror=False)
        self.isFriendPic = AdvImagePanel(inner_panel, tooltip_friend, tooltip_nofriend)#self)
        self.isFriendPic.SetEnabled(False)
        self.isFriendPic.SetBitmap("joe24.png")
#        self.isFriendPic.Bind(wx.EVT_LEFT_UP, self.friendAction)
        
        hAttrSizer.Add( self.isFriendPic, 0, wx.RIGHT, 15)
        hAttrSizer.Add(self.statusPic, 0, wx.RIGHT, 5)
        hAttrSizer.Add(self.statusTxt, 0, wx.RIGHT, 15)
        hAttrSizer.Add(self.simPic, 0, wx.RIGHT, 5)
        hAttrSizer.Add(self.simTxt, 0, wx.RIGHT, 15)
        
        vSizer.Add(hAttrSizer, 0, wx.ALL, 3)
        

        inner_panel.SetSizer(vSizer)
        inner_panel.SetAutoLayout(1);
        inner_panel.Layout();
        inner_panel.Refresh()
        #vSizerBig.Add(vSizer, 0, wx.ALL|wx.EXPAND, 4)
        vSizerBig.Add(inner_panel, 1, wx.ALL|wx.EXPAND, 4)

        self.SetSizer(vSizerBig);
        self.SetAutoLayout(1);
        self.Layout();
#        self.SetBackgroundColour(wx.WHITE)
        self.Refresh()
#        self.SetBackgroundColour(wx.WHITE)

        inner_panel.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        for window in inner_panel.GetChildren():
            window.Bind(wx.EVT_LEFT_UP, self.mouseAction)
            window.SetBackgroundColour(wx.WHITE)
        
    def getRank(self):
        """looks for the current data in the top 20 list and returns the index numeroted from 1"""
        try:
            permid = self.data['permid']
            for i in range(len(self.contentFrontPanel.top20similar)):
                if self.contentFrontPanel.top20similar[i]['permid'] == permid:
                    return (i+1)
        except:
            pass
#            print "error on getting rank"
        return -1
        
    def onResize(self, event):
        # redo set data for new breakup
        event.Skip(True)
        #if self.oldSize and (event.GetSize()[0] == self.oldSize[0]):
        #    return
        #if not self.data:
        #    return
        #self.oldSize = event.GetSize()
        #value = self.data.get('content_name', '')
        #self.title.SetLabel(self.breakup(value, self.title))
        #self.title.SetMinSize((100, 80))
        #print "new size:",event.GetSize()
        self.emptyStaticBox.SetSize(event.GetSize())
        #self.emptyStaticBox.Show()
        
    def setData(self, peer):
        # set bitmap, rating, title
        try:
            if self.datacopy['permid'] == peer['permid']:
                # Do not update torrents that have no new seeders/leechers/size
                if (self.datacopy['last_seen'] == peer['last_seen'] and
                    self.datacopy['connected_times'] == peer['connected_times'] and
                    self.datacopy['buddycast_times'] == peer['buddycast_times'] and #this should also include updating the number of torrents from this user (number changed => buddycast_messages changed...)
                    self.datacopy['similarity'] == peer['similarity'] and
                    self.datacopy['name'] == peer['name'] and
                    self.datacopy['ip'] == peer['ip'] and
                    self.datacopy['content_name'] == peer['content_name'] and
                    self.datacopy.get('friend') == peer.get('friend')):
                    return
        except:
            pass
        
        self.data = peer
        self.datacopy = deepcopy(peer)
        
        if peer == None:
            self.emptyStaticBox.Show(False)
            self.inner_panel.Show(False)
            peer = {}
        else:
            self.emptyStaticBox.Show(True)
            self.inner_panel.Show(True)

        if peer.get('content_name'):
            title = peer['content_name'][:self.titleLength]
            #print 'title set to ',title
            self.title.SetLabel(title)
            #self.title.Wrap(-1) # no wrap
            self.title.SetToolTipString(peer['content_name'])
        else:
            #self.title.SetLabel('')
            #self.title.SetToolTipString('')
            pass

        my_rank = self.getRank()
        if my_rank>0:
#        if peer.get('similarity_percent')!= None:
#            if peer['similarity_percent']>0:
#                self.simTxt.SetLabel("%d%%" % peer['similarity_percent'])
            self.simTxt.SetLabel("%d" % my_rank)
            self.simPic.Show(True)
        else:
            self.simTxt.SetLabel('')
            self.simPic.Show(False)
#        print peer['content_name'],"has rank value",peer['rank_value'],"and similarity rank",my_rank
#        else:
#            pass
            #self.simTxt.SetLabel('?%')
            #self.simTxt.SetLabel('')
            #self.simPic.Show(False)

        if peer.get('last_seen')!= None:
            self.statusPic.Enable(True)
            if peer['last_seen'] < 0:
                self.statusTxt.SetLabel("never seen online")
                self.statusPic.changeColor('grey')
            else:
                self.statusTxt.SetLabel("seen "+friendly_time(peer['last_seen']))
                self.statusPic.changeColor(getAgeingColor(peer['last_seen']))
        else:
            pass
            #self.statusTxt.SetLabel("never seen online")
            #self.statusTxt.SetLabel("")
            #self.statusPic.changeColor('grey')
            #self.statusPic.Enable(False)
            
        if peer.get('friend')!=None and peer['friend']==True:
            self.isFriendPic.SetEnabled(True)
        else:
            self.isFriendPic.SetEnabled(False)
      
        self.inner_panel.Layout()
        self.Layout()
        self.Refresh()
#        self.inner_panel.Layout()
#        self.inner_panel.Refresh()
        self.parent.Refresh()            
                
def __test():
		
    class TestFrame(wx.Frame):
        def __init__(self, parent):
            wx.Frame.__init__(self, parent, -1, "Test Run", wx.DefaultPosition, (600, 400))
            abcpath = os.path.abspath(os.path.dirname(sys.argv[0]))
            self.utility = Utility(abcpath)
            # A status bar to tell people what's happening
            self.CreateStatusBar(1)
            self.client = PersonFrontPanel(self)
            self.Show(True)

    class TestApp(wx.App):
        def OnInit(self):
            wx.InitAllImageHandlers()
            frame = TestFrame(None)
            #frame.Show(True)
            self.SetTopWindow(frame)
            return True

    #app = TestApp(0)
    #app.MainLoop()
    
    # test code for changing a function of a class or only an object
    class TestObiect:
        def __init__(self):
            pass
    
    class TestObiect2:
        def __init__(self):
            pass
    
    class TestObiect3:
        def __init__(self):
            pass
        
    class Test:
        def faObiect(self):
            return TestObiect()
        def faCeva(self):
            print "fac ceva"
            print "creez obiect: ",str(self.faObiect())
            print "fac altceva"
    
    t= Test()
    t.faCeva()
    def faObiect2(self):
        return TestObiect2()
    Test.faObiect=faObiect2
    t.faCeva()
    def faObiect3():
        return TestObiect3()
    t.faObiect=faObiect3
    t.faCeva()
    Test().faCeva()

if __name__ == '__main__':
    __test()

# Written by Jelle Roozenburg, Maarten ten Brinke, Lucian Musat 
# see LICENSE.txt for license information

import sys
import wx
import wx.xrc as xrc
from wx.lib.stattext import GenStaticText as StaticText

from binascii import hexlify
from time import sleep,time
import math
from traceback import print_exc, print_stack
import cStringIO
import urlparse
import threading

from font import *
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue

from Tribler.TrackerChecking.TorrentChecking import TorrentChecking
from Tribler.Video.VideoPlayer import VideoPlayer

from Tribler.Core.API import *
from Tribler.Core.Utilities.utilities import *

from Tribler.Video.utils import videoextdefaults

DETAILS_MODES = ['filesMode', 'libraryMode']

DEBUG = False

def showInfoHash(infohash):
    if infohash.startswith('torrent'):    # for testing
        return infohash
    try:
        n = int(infohash)
        return str(n)
    except:
        pass
    return encodestring(infohash).replace("\n","")
            
class standardDetails(wx.Panel):
    """
    Wrappers around details xrc panels
    """
    def __init__(self, *args):
        
        self.bartercastdb = None
        self.top_stats = None
        
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
        self.subscr_old_source = None
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility        
        self.torrent_db = self.utility.session.open_dbhandler(NTFY_TORRENTS)
        self.peer_db = self.utility.session.open_dbhandler(NTFY_PEERS)
        self.superpeer_db = self.utility.session.open_dbhandler(NTFY_SUPERPEERS)
        self.playList = []
      
                                    
        self.mode = None
        self.item = None
        self.bartercastdb = None
        self.lastItemSelected = {} #keeps the last item selected for each mode
        self.data = {} #keeps gui elements for each mode
        for mode in DETAILS_MODES+['status']:
            self.data[mode] = {} #each mode has a dictionary of gui elements with name and reference
            self.lastItemSelected[mode] = None
        self.currentPanel = None
        self.videoplayer = VideoPlayer.getInstance()

        self.addasfriendcount = 0
        self.addasfriendlast = 0
        

        # videodata
        self.videodata = None   
        

        self.guiUtility.initStandardDetails(self)
       
        

        
    def setMode(self, mode, item = None):
        
        if DEBUG:
            print >>sys.stderr,"standardDetails: setMode called, new mode is",mode,"old",self.mode
        
        if self.mode != mode:
            #change the mode, so save last item selected
            self.lastItemSelected[self.mode] = self.item
            self.mode = mode
        if item:
            self.setData(item)
        elif self.lastItemSelected[self.mode]:
            self.guiUtility.selectData(self.lastItemSelected[self.mode])
        else:
            self.setData(None)
    
    def getMode(self):
        return self.mode
            
        

    def getVideodata(self):
        return self.videodata


    def setVideodata(self, videodata):
        self.videodata = videodata

    
    def getData(self):
        return self.item
    
    def getIdentifier(self):
        if not self.item:
            return None
        try:
            if self.mode in ['filesMode','libraryMode']:
                return self.item['infohash']
            elif DEBUG:
                print >> sys.stderr,'standardDetails: Error in getIdentifier for mode %s, item=%s' % (self.mode,self.item)
        except:
            if DEBUG:
                print >> sys.stderr,'standardDetails: Error in getIdentifier for mode %s, item=%s' % (self.mode,self.item)
                
            print_exc()
        
    def setData(self, item):
        self.updateCallback(item) # update callback function on changing item
        self.item = item
        if item is None:
            item = {}
        if self.mode in ['filesMode', 'libraryMode']:
            #check if this is a corresponding item from type point of view
            if item.get('infohash') is None:
                return #no valid torrent
            torrent = item
                        
            title = torrent.get('name')
            title = title[:77]
            
        
        elif DEBUG:
            print >> sys.stderr,"standardDetails: setData: No entry for mode",self.mode
                    
            
    def refresh(self, torrent):
        if DEBUG:
            print >>sys.stderr,'standardDetails: refresh ' + repr(torrent.get('name', 'no_name'))
        check = TorrentChecking(torrent['infohash'])
        check.start()
        
 
    def _download_torrentfile_from_peers(self, torrent, callback, duplicate=True):
        """
        TORRENT is a dictionary containing torrent information used to
        display the entry on the UI. it is NOT the torrent file!

        CALLBACK is called when the torrent is downloaded. When no
        torrent can be downloaded the callback is ignored

        DUPLICATE can be True: the file will be downloaded from peers
        regardless of a previous/current download attempt (returns
        True). Or DUPLICATE can be False: the file will only be
        downloaded when it was not yet attempted to download (when
        False is returned no callback will be made)

        Returns True or False
        """
        def success_callback(*args):
            # empty the permids list to indicate that we are done
            if state[0]:
                if DEBUG: print >>sys.stderr,"standardDetails: _download_torrentfile_from_peers: received .torrent from peer after", time() - begin_timer, "seconds"
                state[0] = False
                callback(*args)

        def next_callback(timeout):
            """
            TIMEOUT: when TIMEOUT>=0 then will try another peer after TIMEOUT seconds.
            """
            if state[0] and state[1]:
                if DEBUG: print >>sys.stderr,"standardDetails: _download_torrentfile_from_peers: trying to .torrent download from peer.",len(state[1])-1,"other peers to ask"
                self.utility.session.download_torrentfile_from_peer(state[1].pop(0), torrent['infohash'], success_callback)
                if timeout >= 0:
                    next_callback_lambda = lambda:next_callback(timeout)
                    guiserver.add_task(next_callback_lambda, timeout)

        # return False when duplicate
        if not duplicate and torrent.get('query_torrent_was_requested', False):
            return False

        # return False when there are no sources to retrieve the
        # torrent from
        if not 'query_permids' in torrent:
            if DEBUG:
                print >> sys.stderr, "standardDetails: _download_torrentfile_from_peers: can not download .torrent file. No known source peers"
            return False

        torrent['query_torrent_was_requested'] = True
        guiserver = GUITaskQueue.getInstance()
        state = [True, torrent['query_permids'][:]]

        if DEBUG:
            begin_timer = time()

        # The rules and policies below can be tweaked to increase
        # performace. More parallel requests can be made, or the
        # timeout to ask more people can be decreased. All at the
        # expence of bandwith.
        if torrent['torrent_size'] > 50 * 1024:
            # this is a big torrent. to preserve bandwidth we will
            # request sequentially with a large timeout
            next_callback(3)
            
        elif 0 <= torrent['torrent_size'] <= 10 * 1024:
            # this is a small torrent. bandwidth is not an issue so
            # download in parallel
            next_callback(-1)
            next_callback(1)
            next_callback(1)

        else:
            # medium and unknown torrent size. 
            next_callback(1)
            next_callback(1)

        return True

    def torrent_is_playable(self, torrent=None, default=(None, []), callback=None):
        """
        TORRENT is a dictionary containing torrent information used to
        display the entry on the UI. it is NOT the torrent file!

        DEFAULT indicates the default value when we don't know if the
        torrent is playable. 

        CALLBACK can be given to result the actual 'playable' value
        for the torrent after some downloading/processing. The DEFAULT
        value is returned in this case. Will only be called if
        self.item == torrent

        The return value is a tuple consisting of a boolean indicating if the torrent is playable and a list.
        If the torrent is not playable or if the default value is returned the boolean is False and the list is empty.
        If it is playable the boolean is true and the list returned consists of the playable files within the actual torrent. 
        """
        if torrent is None:
            torrent = self.item

        if 'torrent_file_name' not in torrent or not torrent['torrent_file_name']:
            torrent['torrent_file_name'] = get_collected_torrent_filename(torrent['infohash']) 
        torrent_dir = self.utility.session.get_torrent_collecting_dir()
        torrent_filename = os.path.join(torrent_dir, torrent['torrent_file_name'])

        if os.path.isfile(torrent_filename):
            tdef = TorrentDef.load(torrent_filename)
            files = tdef.get_files(exts=videoextdefaults)
            if files:
                if DEBUG: print >>sys.stderr, "standardDetails:torrent_is_playable is playable"
                return (True, files)
            else:
                if DEBUG: print >>sys.stderr, "standardDetails:torrent_is_playable is NOT playable"
                return (False, [])

        elif callback:
            # unknown, figure it out and return the information using
            # a callback

            if 'query_permids' in torrent and not torrent.get('myDownloadHistory'):
                def sesscb_got_requested_torrent(infohash, metadata, filename):
                    if DEBUG: print >>sys.stderr, "standardDetails:torrent_is_playable Downloaded a torrent"
                    # test that we are still focussed on the same torrent
                    if torrent_filename.endswith(filename) and self.item == torrent:
                        # recursive call
                        playable = self.torrent_is_playable(torrent, default=default)
                        if DEBUG: print >>sys.stderr, "standardDetails:torrent_is_playable performing callback. is playable", playable
                        wx.CallAfter(callback, torrent, playable)
                self._download_torrentfile_from_peers(torrent, sesscb_got_requested_torrent)
            
        if DEBUG: print >>sys.stderr, "standardDetails:torrent_is_playable returning default", default
        return default


    def download(self, torrent = None, dest = None, secret = False, force = False, vodmode = False):
        if torrent is None:
            torrent = self.item
            
            
#        if self.GetName() == 'download':

        force = True
        if (torrent is None or torrent.get('myDownloadHistory')) and not force:
            print >>sys.stderr,"standardDetails: download: Bailout"
            return
            
        #print "**** standdetail: download", `torrent`
            
        # if torrent.get('web2'):
        #     if DEBUG:
        #         print >>sys.stderr,"standardDetails: download: Playing WEB2 video: " + torrent['url']
        #     self.videoplayer.play_url(torrent['url'])
        #     self.setDownloadbutton(torrent=self.item, item = self.downloadButton2)
        #     return True

        if 'query_permids' in torrent and not torrent.get('myDownloadHistory'):
            sesscb_got_requested_torrent_lambda = lambda infohash,metadata,filename:self.sesscb_got_requested_torrent(torrent,infohash,metadata,filename,vodmode)
            self._download_torrentfile_from_peers(torrent, sesscb_got_requested_torrent_lambda)

            # Show error if torrent file does not come in
            tfdownload_timeout_lambda = lambda:self.guiserv_tfdownload_timeout(torrent)
            guiserver = GUITaskQueue.getInstance()
            guiserver.add_task(tfdownload_timeout_lambda,20)
            
            # Show pending colour
            self.guiUtility.standardOverview.refreshGridManager()
            
            #self.setDownloadbutton(torrent=self.item, item = self.downloadButton2)
            #print >> sys.stderr, torrent, torrent.keys()
            return True

        torrent_dir = self.utility.session.get_torrent_collecting_dir()
        if DEBUG:
            print >> sys.stderr, 'standardDetails: download: got torrent to download', 'torrent_file_name' in torrent, torrent_dir, torrent['torrent_file_name'] 
        
        if 'torrent_file_name' not in torrent:
            torrent['torrent_file_name'] = get_collected_torrent_filename(torrent['infohash']) 
        torrent_filename = os.path.join(torrent_dir, torrent['torrent_file_name'])

        if torrent.get('name'):
            name = torrent['name']
        else:
            name = showInfoHash(torrent['infohash'])
        
        print >>sys.stderr,"standardDetails: download: Preparing to start:",`name`
        
        if os.path.isfile(torrent_filename):

            clicklog={'keywords': self.guiUtility.torrentsearch_manager.searchkeywords[self.mode],
                      'reranking_strategy': self.guiUtility.torrentsearch_manager.rerankingStrategy[self.mode].getID()}
            if "click_position" in torrent:
                clicklog["click_position"] = torrent["click_position"]

            
            # Api download
            d = self.utility.frame.startDownload(torrent_filename,destdir=dest,
                                                 clicklog=clicklog,name=name,vodmode=vodmode) ## remove name=name
            if d:
                if secret:
                    self.torrent_db.setSecret(torrent['infohash'], secret)

                if DEBUG:
                    print >>sys.stderr,'standardDetails: download: download started'
                # save start download time.
                #self.setDownloadbutton(torrent=self.item, item = self.downloadButton2)
                #torrent['download_started'] = time()
                #torrent['progress'] = 0.0
                self.setBelongsToMyDowloadHistory(torrent, True)
                return True        
            else:
                return False
        else:
        
            # Torrent not found            
            str = self.utility.lang.get('delete_torrent') % name
            dlg = wx.MessageDialog(self, str, self.utility.lang.get('delete_dead_torrent'), 
                                wx.YES_NO|wx.NO_DEFAULT|wx.ICON_INFORMATION)
            result = dlg.ShowModal()
            dlg.Destroy()
            if result == wx.ID_YES:
                infohash = torrent['infohash']
                self.torrent_db.deleteTorrent(infohash, delete_file=True, commit = True)
        
        
                
                return True
            else:
                return False

    def sesscb_got_requested_torrent(self,querytorrent,infohash,metadata,filename,vodmode):
        """ The torrent file requested from another peer came in.
        @param querytorrent The original torrent record as shown on the screen
        @param infohash The infohash of the torrent file.
        @param metadata The contents of the torrent file (still bencoded)
        @param vodmode Whether to download in VOD mode (lambda added)
        """
        # Called by SessionCallback thread
        print >>sys.stderr,"standardDetails: sesscb_got_requested_torrent:",`infohash`
        
        # Update the torrent record, and refresh the view afterwards such 
        # that it shows as a torrent being downloaded.
        querytorrent['torrent_file_name'] = filename
        self.setBelongsToMyDowloadHistory(querytorrent, True)
        
        wx.CallAfter(self.download,querytorrent,force=True,vodmode=vodmode)
        wx.CallAfter(self.guiUtility.standardOverview.refreshGridManager)

    def setBelongsToMyDowloadHistory(self,torrent, b):
        """Set a certain new torrent to be in the download history or not
        Should not be changed by updateTorrent calls"""

        # DB registration and buddycast notification is done in LaunchManyCore.add()
        # Currently no removal function.
        torrent['myDownloadHistory'] = True


    def guiserv_tfdownload_timeout(self,torrent):
        print >>sys.stderr,"standardDetails: tdownload_timeout: Did we receive",`torrent['name']`
        dbrecord = self.torrent_db.getTorrent(torrent['infohash'])
        d = self.getData()
        if d is not None:
            selinfohash = d.get('infohash',None)
            if dbrecord is None and torrent['infohash'] == selinfohash:
                print >>sys.stderr,"standardDetails: tdownload_timeout: Couldn't get torrent from peer",`torrent['name']`
                wx.CallAfter(self.tfdownload_timeout_error)
                
    def tfdownload_timeout_error(self):
        self.videoplayer.set_player_status("Error starting download. Could not get metadata from remote peer.")


        

    def updateCallback(self, item):
        "Update callback handling for this item"
        session = self.guiUtility.utility.session
        session.remove_observer(self.db_callback)
        if item is None:
            return
        if self.mode in ['filesMode', 'libraryMode']:
            session.add_observer(self.db_callback, NTFY_TORRENTS, [NTFY_UPDATE, NTFY_DELETE], item['infohash'])
        
    def db_callback(self,subject,changeType,objectID,*args):
        # called by threadpool thread
        #print >> sys.stderr, 'stdDetails: db_callback: %s %s %s %s' % (subject, changeType, `objectID`, args)
        db_handler = self.guiUtility.utility.session.open_dbhandler(subject)
        if subject == NTFY_PEERS:
            newitem = db_handler.getPeer(objectID)
        elif subject in (NTFY_TORRENTS):
            newitem = db_handler.getTorrent(objectID)
            
        
            
        wx.CallAfter(self.setData, newitem)

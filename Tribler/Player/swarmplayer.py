# Written by Arno Bakker, Choopan RATTANAPOKA, Jie Yang
# see LICENSE.txt for license information
#
# TODO: 
# * set 'download_slice_size' to 32K, such that pieces are no longer
#   downloaded in 2 chunks. This particularly avoids a bad case where you
#   kick the source: you download chunk 1 of piece X
#   from lagging peer and download chunk 2 of piece X from source. With the piece
#   now complete you check the sig. As the first part of the piece is old, this
#   fails and we kick the peer that gave us the completing chunk, which is the 
#   source.
#
#   Note that the BT spec says: 
#   "All current implementations use 2 15 , and close connections which request 
#   an amount greater than 2 17." http://www.bittorrent.org/beps/bep_0003.html
#
#   So it should be 32KB already. However, the BitTorrent (3.4.1, 5.0.9), 
#   BitTornado and Azureus all use 2 ** 14 = 16KB chunks.
#
# - See if we can use stream.seek() to optimize SwarmPlayer as well (see SwarmPlugin)

import os
import sys
import time
import tempfile
from traceback import print_exc
from cStringIO import StringIO

if sys.platform == "darwin":
    # on Mac, we can only load VLC/OpenSSL libraries
    # relative to the location of tribler.py
    os.chdir(os.path.abspath(os.path.dirname(sys.argv[0])))
try:
    import wxversion
    wxversion.select('2.8')
except:
    pass
import wx

from Tribler.__init__ import LIBRARYNAME
from Tribler.Core.API import *
from Tribler.Core.Utilities.unicode import bin2unicode
from Tribler.Core.Utilities.timeouturlopen import urlOpenTimeout

from Tribler.Video.defs import * 
from Tribler.Video.VideoPlayer import VideoPlayer, VideoChooser  
from Tribler.Video.VideoFrame import VideoFrame
from Tribler.Video.utils import videoextdefaults
from Tribler.Utilities.LinuxSingleInstanceChecker import *
from Tribler.Utilities.Instance2Instance import Instance2InstanceClient

from Tribler.Player.BaseApp import BaseApp

DEBUG = True
ONSCREENDEBUG = False
ALLOW_MULTIPLE = False

PLAYER_VERSION = '1.1.0'

I2I_LISTENPORT = 57894
PLAYER_LISTENPORT = 8620
VIDEOHTTP_LISTENPORT = 6879

class PlayerApp(BaseApp):
    def __init__(self, redirectstderrout, appname, params, single_instance_checker, installdir, i2iport, sport):

        BaseApp.__init__(self, redirectstderrout, appname, params, single_instance_checker, installdir, i2iport, sport)

        self.said_start_playback = False
        self.decodeprogress = 0

        
    def OnInit(self):
        try:
            # If already running, and user starts a new instance without a URL 
            # on the cmd line
            if not ALLOW_MULTIPLE and self.single_instance_checker.IsAnotherRunning():
                print >> sys.stderr,"main: Another instance running, no URL on CMD, asking user"
                torrentfilename = self.select_torrent_from_disk()
                if torrentfilename is not None:
                    i2ic = Instance2InstanceClient(I2I_LISTENPORT,'START',torrentfilename)
                    return False

            # Do common initialization
            BaseApp.OnInitBase(self)
        
            # Fire up the VideoPlayer, it abstracts away whether we're using
            # an internal or external video player.
            self.videoplayer = VideoPlayer.getInstance(httpport=VIDEOHTTP_LISTENPORT)
            playbackmode = PLAYBACKMODE_INTERNAL
            self.videoplayer.register(self.utility,preferredplaybackmode=playbackmode)
            
            # Open video window
            self.start_video_frame()

            # Load torrent
            if self.params[0] != "":
                torrentfilename = self.params[0]
                
                # TEST: just play video file
                #self.videoplayer.play_url(torrentfilename)
                #return True
                
            else:
                torrentfilename = self.select_torrent_from_disk()
                if torrentfilename is None:
                    print >>sys.stderr,"main: User selected no file"
                    self.OnExit()
                    return False


            # Start download
            if not self.select_file_start_download(torrentfilename):
                
                self.OnExit()
                return False

            return True
        
        except Exception,e:
            print_exc()
            self.show_error(str(e))
            self.OnExit()
            return False


    def start_video_frame(self):
        self.videoFrame = PlayerFrame(self,self.appname)
        self.Bind(wx.EVT_CLOSE, self.videoFrame.OnCloseWindow)
        self.Bind(wx.EVT_QUERY_END_SESSION, self.videoFrame.OnCloseWindow)
        self.Bind(wx.EVT_END_SESSION, self.videoFrame.OnCloseWindow)
        self.videoFrame.show_videoframe()

        if self.videoplayer is not None:
            self.videoplayer.set_videoframe(self.videoFrame)
        self.said_start_playback = False
        
        
    def select_torrent_from_disk(self):
        dlg = wx.FileDialog(None, 
                            self.appname+': Select torrent to play', 
                            '', # default dir
                            '', # default file
                            'TSTREAM and TORRENT files (*.tstream;*.torrent)|*.tstream;*.torrent', 
                            wx.OPEN|wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            filename = dlg.GetPath()
        else:
            filename = None
        dlg.Destroy()
        return filename


    def select_file_start_download(self,torrentfilename):
        tdef = TorrentDef.load(torrentfilename)
        print >>sys.stderr,"main: Starting download, infohash is",`tdef.get_infohash()`
        
        # Select which video to play (if multiple)
        videofiles = tdef.get_files(exts=videoextdefaults)
        print >>sys.stderr,"main: Found video files",videofiles
        
        if len(videofiles) == 0:
            print >>sys.stderr,"main: No video files found! Let user select"
            # Let user choose any file
            videofiles = tdef.get_files(exts=None)
            
        if len(videofiles) > 1:
            selectedvideofile = self.ask_user_which_video_from_torrent(videofiles)
            if selectedvideofile is None:
                print >>sys.stderr,"main: User selected no video"
                return False
            dlfile = selectedvideofile
        else:
            dlfile = videofiles[0]


        # Start video window if not open
        if self.videoFrame is None:
            self.start_video_frame()
        else:
            # Stop playing, reset stream progress info + sliders 
            self.videoplayer.stop_playback(reset=True)
            self.said_start_playback = False
        self.decodeprogress = 0

        # Display name and thumbnail
        cname = tdef.get_name_as_unicode()
        if len(videofiles) > 1:
            cname += u' - '+bin2unicode(dlfile)
        self.videoplayer.set_content_name(u'Loading: '+cname)
        
        try:
            [mime,imgdata] = tdef.get_thumbnail()
            if mime is not None:
                f = StringIO(imgdata)
                img = wx.EmptyImage(-1,-1)
                img.LoadMimeStream(f,mime,-1)
                self.videoplayer.set_content_image(img)
            else:
                self.videoplayer.set_content_image(None)
        except:
            print_exc()


        # Start actual download
        self.start_download(tdef,dlfile)
        return True



    def ask_user_which_video_from_torrent(self,videofiles):
        dlg = VideoChooser(self.videoFrame,self.utility,videofiles,title=self.appname,expl='Select which file to play')
        result = dlg.ShowModal()
        if result == wx.ID_OK:
            index = dlg.getChosenIndex()
            filename = videofiles[index]
        else:
            filename = None
        dlg.Destroy()
        return filename


    # ARNOTODO: see how VideoPlayer manages stopping downloads
    
    def sesscb_vod_event_callback(self,d,event,params):
        self.videoplayer.sesscb_vod_event_callback(d,event,params)
        
        
    def get_supported_vod_events(self):
        return self.videoplayer.get_supported_vod_events()


    #
    # Remote start of new torrents
    #
    def i2ithread_readlinecallback(self,ic,cmd):
        """ Called by Instance2Instance thread """
        
        print >>sys.stderr,"main: Another instance called us with cmd",cmd
        ic.close()
        
        if cmd.startswith('START '):
            param = cmd[len('START '):]
            torrentfilename = None
            if param.startswith('http:'):
                # Retrieve from web 
                f = tempfile.NamedTemporaryFile()
                n = urlOpenTimeout(url)
                data = n.read()
                f.write(data)
                f.close()
                n.close()
                torrentfilename = f.name
            else:
                torrentfilename = param
                
            # Switch to GUI thread
            wx.CallAfter(self.remote_start_download,torrentfilename)

    def remote_start_download(self,torrentfilename):
        """ Called by GUI thread """
        self.videoplayer.stop_playback(reset=True)

        self.remove_downloads_in_vodmode_if_not_complete()
        self.select_file_start_download(torrentfilename)


    #
    # Display stats in videoframe
    #
    def gui_states_callback(self,dslist,haspeerlist):
        """ Override BaseApp """
        (playing_dslist,totalhelping,totalspeed) = BaseApp.gui_states_callback(self,dslist,haspeerlist)
        
        # Don't display stats if there is no video frame to show them on.
        if self.videoFrame is None:
            return
        elif len(playing_dslist) > 0:
            ds = playing_dslist[0] # only single playing Download at the moment in swarmplayer 
            self.display_stats_in_videoframe(ds,totalhelping,totalspeed)


    def display_stats_in_videoframe(self,ds,totalhelping,totalspeed):
        # Display stats for currently playing Download
        
        videoplayer_mediastate = self.videoplayer.get_state()
        #print >>sys.stderr,"main: Stats: VideoPlayer state",videoplayer_mediastate
        
        [topmsg,msg,self.said_start_playback,self.decodeprogress] = get_status_msgs(ds,videoplayer_mediastate,appname,self.said_start_playback,self.decodeprogress)
        # Display helping info on "content name" line.
        self.videoplayer.set_content_name(topmsg)

        # Update status msg and progress bar
        self.videoplayer.set_player_status_and_progress(msg,ds.get_pieces_complete())
        
        # Toggle save button
        self.videoplayer.set_save_button(ds.get_status() == DLSTATUS_SEEDING, self.save_video_copy)    
            
        if False: # Only works if the sesscb_states_callback() method returns (x,True)
            peerlist = ds.get_peerlist()
            print >>sys.stderr,"main: Connected to",len(peerlist),"peers"
            for peer in peerlist:
                print >>sys.stderr,"main: Connected to",peer['ip'],peer['uprate'],peer['downrate']


    def videoserver_set_status_guicallback(self,status):
        """ Override BaseApp """
        if self.videoFrame is not None:
            self.videoFrame.set_player_status(status)

    #
    # Save button logic
    #
    def save_video_copy(self):
        # Save a copy of playing download to other location
        
        d = self.downloads_in_vodmode[0] # only single playing Download at the moment in swarmplayer 
        dest_files = d.get_dest_files()  
        dest_file = dest_files[0] # only single file at the moment in swarmplayer
        savethread_callback_lambda = lambda:self.savethread_callback(dest_file)
        
        t = Thread(target = savethread_callback_lambda)
        t.setName( self.appname+"Save"+t.getName() )
        t.setDaemon(True)
        t.start()
    
    def savethread_callback(self,dest_file):
        
        # Save a copy of playing download to other location
        # called by new thread from self.save_video_copy
        try:
            if sys.platform == 'win32':
                # Jelle also goes win32, find location of "My Documents"
                # see http://www.mvps.org/access/api/api0054.htm
                from win32com.shell import shell
                pidl = shell.SHGetSpecialFolderLocation(0,0x05)
                defaultpath = shell.SHGetPathFromIDList(pidl)
            else:
                defaultpath = os.path.expandvars('$HOME')
        except Exception, msg:
            defaultpath = ''
            print_exc()

        dest_file_only = os.path.split(dest_file[1])[1]
        
        print >> sys.stderr, 'Defaultpath:', defaultpath, 'Dest:', dest_file
        dlg = wx.FileDialog(self.videoFrame, 
                            message = self.utility.lang.get('savemedia'), 
                            defaultDir = defaultpath, 
                            defaultFile = dest_file_only,
                            wildcard = self.utility.lang.get('allfileswildcard') + ' (*.*)|*.*', 
                            style = wx.SAVE)
        dlg.Raise()
        result = dlg.ShowModal()
        dlg.Destroy()
        
        if result == wx.ID_OK:
            path = dlg.GetPath()
            print >> sys.stderr, 'Path:', path
            print >> sys.stderr, 'Copy: %s to %s' % (dest_file[1], path)
            if sys.platform == 'win32':
                try:
                    import win32file
                    win32file.CopyFile(dest_file[1], path, 0) # do succeed on collision
                except:
                    shutil.copyfile(dest_file[1], path)
            else:
                shutil.copyfile(dest_file[1], path)
    


def get_status_msgs(ds,videoplayer_mediastate,appname,said_start_playback,decodeprogress):

    topmsg = ''
    msg = ''
    
    logmsgs = ds.get_log_messages()
    logmsg = None
    if len(logmsgs) > 0:
        print >>sys.stderr,"main: Log",logmsgs[0]
        logmsg = logmsgs[-1][1]
        
    preprogress = ds.get_vod_prebuffering_progress()
    playable = ds.get_vod_playable()
    t = ds.get_vod_playable_after()
    
    #print >>sys.stderr,"main: playble",playable,"preprog",preprogress
    print >>sys.stderr,"main: ETA is",t,"secs"
    if t > float(2 ** 30):
        intime = "inf"
    elif t == 0.0:
        intime = "now"
    else:
        h, t = divmod(t, 60.0*60.0)
        m, s = divmod(t, 60.0)
        if h == 0.0:
            if m == 0.0:
                intime = "%ds" % (s)
            else:
                intime = "%dm:%02ds" % (m,s)
        else:
            intime = "%dh:%02dm:%02ds" % (h,m,s)
            
    #print >>sys.stderr,"main: VODStats",preprogress,playable,"%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%"

    if ds.get_status() == DLSTATUS_HASHCHECKING:
        genprogress = ds.get_progress()
        pstr = str(int(genprogress*100))
        msg = "Checking already downloaded parts "+pstr+"% done"
    elif ds.get_status() == DLSTATUS_STOPPED_ON_ERROR:
        msg = 'Error playing: '+str(ds.get_error())
    elif playable:
        if not said_start_playback:
            msg = "Starting playback..."
            
        if videoplayer_mediastate == MEDIASTATE_STOPPED and said_start_playback:
            if totalhelping == 0:
                topmsg = u"Please leave the "+appname+" running, this will help other "+appname+" users to download faster."
            else:
                topmsg = u"Helping "+str(totalhelping)+" "+appname+" users to download. Please leave it running in the background."
                
            # Display this on status line
            # TODO: Show balloon in systray when closing window to indicate things continue there
            msg = ''
            
        elif videoplayer_mediastate == MEDIASTATE_PLAYING:
            said_start_playback = True
            # It may take a while for VLC to actually start displaying
            # video, as it is trying to tune in to the stream (finding
            # I-Frame). Display some info to show that:
            #
            cname = ds.get_download().get_def().get_name_as_unicode()
            topmsg = u'Decoding: '+cname+' '+str(decodeprogress)+' s'
            decodeprogress += 1
            msg = ''
        elif videoplayer_mediastate == MEDIASTATE_PAUSED:
            msg = "Buffering... " + str(int(100.0*preprogress))+"%"
        else:
            msg = ''
            
    elif preprogress != 1.0:
        pstr = str(int(preprogress*100))
        npeers = ds.get_num_peers()
        npeerstr = str(npeers)
        if npeers == 0 and logmsg is not None:
            msg = logmsg
        else:
            msg = "Prebuffering "+pstr+"% done, eta "+intime+'  (connected to '+npeerstr+' people)'
            
        try:
            d = ds.get_download()
            tdef = d.get_def()
            videofiles = d.get_selected_files()
            if len(videofiles) == 0:
                videofile = None
            else:
                videofile = videofiles[0]
            if tdef.get_bitrate(videofile) is None:
                msg += '. This video may not play properly because its bitrate is unknown.'
        except:
            print_exc()
    else:
        msg = "Waiting for sufficient download speed... "+intime
        
    global ONSCREENDEBUG
    if msg == '' and ONSCREENDEBUG:
        uptxt = "up %.1f" % (totalspeed[UPLOAD])
        downtxt = " down %.1f" % (totalspeed[DOWNLOAD])
        peertxt = " peer %d" % (totalhelping)
        msg = uptxt + downtxt + peertxt

    return [topmsg,msg,said_start_playback,decodeprogress]



class PlayerFrame(VideoFrame):
    def __init__(self,parent,appname):
        VideoFrame.__init__(self,parent,appname+' '+PLAYER_VERSION,parent.iconpath,parent.videoplayer.get_vlcwrap(),parent.logopath)
        self.parent = parent
        self.closed = False

        dragdroplist = FileDropTarget(self.parent)
        self.SetDropTarget(dragdroplist)
        
        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
    
    def OnCloseWindow(self, event = None):
        
        print >>sys.stderr,"main: ON CLOSE WINDOW"

        # TODO: first event.Skip does not close window, second apparently does
        # Check how event differs

        if event is not None:
            nr = event.GetEventType()
            lookup = { wx.EVT_CLOSE.evtType[0]: "EVT_CLOSE", wx.EVT_QUERY_END_SESSION.evtType[0]: "EVT_QUERY_END_SESSION", wx.EVT_END_SESSION.evtType[0]: "EVT_END_SESSION" }
            if nr in lookup: 
                nr = lookup[nr]
            print >>sys.stderr,"main: Closing due to event ",nr
            event.Skip()
        else:
            print >>sys.stderr,"main: Closing untriggered by event"

        # This gets called multiple times somehow
        if not self.closed:
            self.closed = True
            self.parent.videoFrame = None

            self.parent.videoplayer.stop_playback()
            self.parent.remove_downloads_in_vodmode_if_not_complete()
            self.parent.restart_other_downloads()
            
        print >>sys.stderr,"main: Closing done"
        # TODO: Show balloon in systray when closing window to indicate things continue there


class FileDropTarget(wx.FileDropTarget):
    """ To enable drag and drop of .tstream to window """
 
    def __init__(self,app):
        wx.FileDropTarget.__init__(self) 
        self.app = app
      
    def OnDropFiles(self, x, y, filenames):
        for filename in filenames:
            self.app.remote_start_download(filename)
        return True


                
        
##############################################################
#
# Main Program Start Here
#
##############################################################
def run_playerapp(appname,params = None):
    if params is None:
        params = [""]
    
    if len(sys.argv) > 1:
        params = sys.argv[1:]
    
    if 'debug' in params:
        global ONSCREENDEBUG
        ONSCREENDEBUG=True
    if 'raw' in params:
        Tribler.Video.VideoPlayer.USE_VLC_RAW_INTERFACE = True
    
    # Create single instance semaphore
    # Arno: On Linux and wxPython-2.8.1.1 the SingleInstanceChecker appears
    # to mess up stderr, i.e., I get IOErrors when writing to it via print_exc()
    #
    siappname = appname.lower() # For backwards compatibility
    if sys.platform != 'linux2':
        single_instance_checker = wx.SingleInstanceChecker(siappname+"-"+ wx.GetUserId())
    else:
        single_instance_checker = LinuxSingleInstanceChecker(siappname)

    #print "[StartUpDebug]---------------- 1", time()-start_time
    if not ALLOW_MULTIPLE and single_instance_checker.IsAnotherRunning():
        if params[0] != "":
            torrentfilename = params[0]
            i2ic = Instance2InstanceClient(I2I_LISTENPORT,'START',torrentfilename)
            time.sleep(1)
            return
        
    arg0 = sys.argv[0].lower()
    if arg0.endswith('.exe'):
        installdir = os.path.abspath(os.path.dirname(sys.argv[0]))
    else:
        installdir = os.getcwd()  

    # Launch first single instance
    app = PlayerApp(0, appname, params, single_instance_checker, installdir, I2I_LISTENPORT, PLAYER_LISTENPORT)
    app.MainLoop()
    
    print >>sys.stderr,"Sleeping seconds to let other threads finish"
    time.sleep(2)
    
    if not ALLOW_MULTIPLE:
        del single_instance_checker


if __name__ == '__main__':
    run_playerapp("SwarmPlayer")


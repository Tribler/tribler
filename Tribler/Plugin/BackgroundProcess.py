# Written by Arno Bakker, Diego Rabioli
# see LICENSE.txt for license information
#
# Notes: 
# - Implement play while hashcheck?
#        Not needed when proper shutdown & restart was done.
# - load_checkpoint with DLSTATUS_DOWNLOADING for Plugin? 
#        Nah, if we start BG when plugin started we have a video to play soon,
#        so start others in STOPPED state (rather than switching them all
#        to off and restart one in VOD mode just after)
#

# History:
#
# NSSA API 1.0.1rc1
#
#     * Added INFO message to convey NSSA info to plugin for providing feedback
#       to the user.
#
# NSPlugin JavaScript API 1.0.1rc1
#     * Added input.p2pstatus read-only property giving the latest status as
#       reported by the NSSA.
#
# 

import os
import sys
import time
import random
import binascii
import tempfile
from base64 import b64encode
from traceback import print_exc,print_stack
from threading import Thread,currentThread,Lock

if sys.platform == "win32":
    import win32event
    import win32api

try:
    import wxversion
    wxversion.select('2.8')
except:
    pass
import wx

from Tribler.Core.API import *
from Tribler.Core.osutils import *
from Tribler.Utilities.LinuxSingleInstanceChecker import *
from Tribler.Utilities.Instance2Instance import InstanceConnectionHandler,InstanceConnection
from Tribler.Player.BaseApp import BaseApp
from Tribler.Player.swarmplayer import get_status_msgs

from Tribler.Video.defs import *
from Tribler.Video.utils import videoextdefaults
from Tribler.Video.VideoServer import VideoHTTPServer

from Tribler.Core.Statistics.StatusReporter import get_reporter_instance

# M23TRIAL
from Tribler.Plugin.LedbatTest import testSender
from Tribler.Plugin.LedbatTest import getStringFromPermID
from Tribler.Plugin.LedbatTest import isLedbatTestRunning
from Tribler.Core.simpledefs import *
totalUpldBytesDic = {}
totalUpldBytes = 0

DEBUG = True
ALLOW_MULTIPLE = False

I2I_LISTENPORT = 62062
BG_LISTENPORT = 8621
VIDEOHTTP_LISTENPORT = 6878

class BackgroundApp(BaseApp):

    def __init__(self, redirectstderrout, appname, params, single_instance_checker, installdir, i2iport, sport):
        
        BaseApp.__init__(self, redirectstderrout, appname, params, single_instance_checker, installdir, i2iport, sport)
        
        self.videoHTTPServer = VideoHTTPServer(VIDEOHTTP_LISTENPORT)
        self.videoHTTPServer.background_serve()
        self.videoHTTPServer.register(self.videoservthread_error_callback,self.videoservthread_set_status_callback)
        
        # Maps Downloads to a using InstanceConnection and streaminfo when it 
        # plays. So it contains the Downloads in VOD mode for which there is
        # active interest from a plugin.
        #
        # At the moment each Download is used/owned by a single IC and a new
        # request for the same torrent will stop playback to the original IC
        # and resume it to the new user.
        #
        self.dusers = {}   
        self.approxplayerstate = MEDIASTATE_STOPPED

        self.counter = 0 # counter for the stats reported periodically
        self.interval = 120 # report interval
        

        # M23TRIAL
        self.runvictor = False
        self.printtreat = False

        if sys.platform == "win32":
            # If the BG Process is started by the plug-in notify it with an event
            startupEvent = win32event.CreateEvent( None, 0, 0, 'startupEvent' )
            win32event.SetEvent( startupEvent )
            win32api.CloseHandle( startupEvent ) # TODO : is it possible to avoid importing win32api just to close an handler?

    def OnInit(self):
        try:
            # Do common initialization
            BaseApp.OnInitBase(self)
            print >>sys.stderr,"bg: Awaiting commands"
            return True

        except Exception,e:
            print_exc()
            self.show_error(str(e))
            self.OnExit()
            return False


    #
    # InstanceConnectionHandler interface. Called by Instance2InstanceThread
    #
    def external_connection_made(self,s):
        ic = BGInstanceConnection(s,self,self.readlinecallback,self.videoHTTPServer)
        self.singsock2ic[s] = ic
        if DEBUG:
            print >>sys.stderr,"bg: Plugin connection_made",len(self.singsock2ic),"++++++++++++++++++++++++++++++++++++++++++++++++"

    def connection_lost(self,s):
        if DEBUG:
            print >>sys.stderr,"bg: Plugin: connection_lost ------------------------------------------------" 

        ic = self.singsock2ic[s]
        InstanceConnectionHandler.connection_lost(self,s)
        wx.CallAfter(self.gui_connection_lost,ic)
        
    def gui_connection_lost(self,ic):
        # IC may or may not have been shutdown:
        # Not: sudden browser crashes
        # Yes: controlled stop via ic.shutdown()
        ic.shutdown() # idempotent
        
        # Now apply cleanup policy to the Download, but only after X seconds
        # so if the plugin comes back with a new request for the same stuff
        # we can give it to him pronto. This is expected to happen a lot due
        # to page reloads / history navigation.
        #
        ic_delayed_remove_if_lambda = lambda:self.i2ithread_delayed_remove_if_not_complete(ic)
        # h4x0r, abuse Istance2Instance server task queue for the delay
        self.i2is.add_task(ic_delayed_remove_if_lambda,20.0)
        
    def i2ithread_delayed_remove_if_not_complete(self,ic):
        if DEBUG:
            print >>sys.stderr,"bg: i2ithread_delayed_remove_if_not_complete"
        wx.CallAfter(self.gui_delayed_remove_if_not_complete,ic)
        
    def gui_delayed_remove_if_not_complete(self,ic):
        for d,duser in self.dusers.iteritems():
            if duser['uic'] == ic:
                # should not remove download if in the meantime a
                # new request for this content has been made.
                # In this case the Download is still used by the old IC.
                d.set_state_callback(self.sesscb_remove_playing_callback)
                break
            
    def remove_playing_download(self,d2remove):
        """ Called when sesscb_remove_playing_callback has determined that
        we should remove this Download, because it would take too much
        bandwidth to download it and the user is apparently no longer
        interested. 
        """
        BaseApp.remove_playing_download(self,d2remove)
        if d2remove in self.dusers:
            if DEBUG:
                print >>sys.stderr,"bg: remove_playing_download"
            if 'streaminfo' in self.dusers[d2remove]:
                stream = self.dusers[d2remove]['streaminfo']['stream']
                stream.close() # Close original stream. 
            del self.dusers[d2remove]
        
        
    def i2ithread_readlinecallback(self,ic,cmd):
        """ Called by Instance2Instance thread """
        wx.CallAfter(self.gui_readlinecallback,ic,cmd)
        
    def gui_readlinecallback(self,ic,cmd):
        """ Receive command from Plugin """
        
        if DEBUG:
            print >>sys.stderr,"bg: Got command:",cmd
        try:
            # START command
            if cmd.startswith( 'START' ):
                torrenturl = cmd.partition( ' ' )[2]
                if torrenturl is None:
                    raise ValueError('bg: Unformatted START command')
                else:
                    self.get_torrent_start_download(ic,torrenturl)
        
            # SHUTDOWN command
            elif cmd.startswith( 'SHUTDOWN' ):
                ic.shutdown()
            else:
                raise ValueError('bg: Unknown command: '+cmd)
        except:
            print_exc()
            ic.shutdown()
    
    
    def get_torrent_start_download(self,ic,url):
        """ Retrieve torrent file from url and start it in VOD mode, if not already """
        tdef  = TorrentDef.load_from_url(url)
        
        # Select which video to play (if multiple)
        if tdef.get_live():
            videofiles = tdef.get_files()
        else:
            videofiles = tdef.get_files(exts=videoextdefaults)
        if len(videofiles) == 1:
            dlfile = videofiles[0]
        elif len(videofiles) == 0:
            raise ValueError("bg: get_torrent_start_download: No video files found! Giving up")
        elif len(videofiles) > 1:
            raise ValueError("bg: get_torrent_start_download: Too many files found! Giving up")

        if DEBUG:
            print >>sys.stderr,"bg: get_torrent_start_download: Found video file",dlfile

        infohash = tdef.get_infohash()
        oldd = None
        for d in self.s.get_downloads():
            if d.get_def().get_infohash() == infohash:
                oldd = d
                break
        
        #
        # Start a new Download, or if it already exists, start playback from
        # beginning. This means that we don't currently support two ICs
        # playing the same video. That is, two browser windows cannot play the
        # same video.
        #
        if oldd is None or (oldd not in self.downloads_in_vodmode):
            # New Download, or Download exists, but not in VOD mode, restart
          
            if DEBUG:
                if oldd is None:
                    print >>sys.stderr,"bg: get_torrent_start_download: Starting new Download"
                else:
                    print >>sys.stderr,"bg: get_torrent_start_download: Restarting old Download in VOD mode"
            
            d = self.start_download(tdef,dlfile)
            duser = {'uic':ic}
            self.dusers[d] = duser
        else:
            # oldd is already running in VOD mode. If it's a VOD torrent we
            # don't need to restart, we can just seek(0) on the stream.
            # If it's a live torrent, we should tell EOF to any old IC and
            # continue playback to the new IC where it left off.
            #
            duser = self.dusers[d]
            olduic = duser['uic']
            olduic.shutdown()
            duser['uic'] = ic
            if 'streaminfo' not in duser:
                # Hasn't started playing yet, ignore.
                pass
            else:
                # Already playing. Tell previous owner IC to quit, let new IC 
                # start either from start (VOD) or where previous left off 
                # (live).
                if not tdef.get_live():
                    duser['streaminfo']['stream'].seek(0)
                ic.set_streaminfo(duser['streaminfo'])
                
                ic.start_playback(infohash)
                
        duser['said_start_playback'] = False
        duser['decodeprogress'] = 0
       

    #
    # DownloadStates
    #
    def gui_states_callback(self,dslist,haspeerlist):
        """ Override BaseApp """
        (playing_dslist,totalhelping,totalspeed) = BaseApp.gui_states_callback(self,dslist,haspeerlist)
        self.report_periodic_vod_stats(playing_dslist)
       
        for ds in playing_dslist:
            d = ds.get_download()
            duser = self.dusers[d]
            uic = duser['uic']
            
            # Generate info string for all
            [topmsg,msg,duser['said_start_playback'],duser['decodeprogress']] = get_status_msgs(ds,self.approxplayerstate,self.appname,duser['said_start_playback'],duser['decodeprogress'],totalhelping,totalspeed)
            info = msg
            
            try:
                # M23TRIAL
                if self.tbicon is not None:
                    t = self.tbicon.get_treatment()
                    
                    if not self.printtreat:
                        print >>sys.stderr,"m23seed: treatment is",t
                        self.printtreat = True
                    
                    if t == "awareness":
                        w = ds.get_vod_stats()
                        if 'npieces' in w:
                            print >>sys.stderr,"W",w['pos'],"==",w['firstpiece']+w['npieces']
                            if w['pos'] == w['firstpiece']+w['npieces']-1:  # -1 is to compensate for off by one error somewhere
                                info = "The SwarmPlugin will run until you shutdown your computer. If you want to stop it before then, right-click on the systray icon and select Exit"
            except:
                print_exc()
                    
            #if DEBUG:
            #    print >>sys.stderr, 'bg: 4INFO: Sending',info
            uic.info(info)
            
        # M23TRIAL
        if len(playing_dslist) == 1:
            ds = playing_dslist[0]
            if ds.get_status() == DLSTATUS_SEEDING:
                pass
                if self.runvictor == False:
                    self.runvictor = True
                    self.run_victor_test()
                
    def run_victor_test(self):
        if sys.platform == "win32":
            # Executed on MainThread, use separate for Victor's stuff.
            print >>sys.stderr,"m23trial: Starting Victor's test",currentThread().getName()
            self.victhread = VictorTestThread(self.installdir,self.s.get_permid())
            self.victhread.start()
        
            
    def sesscb_vod_event_callback( self, d, event, params ):
        """ Registered by BaseApp. Called by SessionCallbackThread """
        wx.CallAfter(self.gui_vod_event_callback,d,event,params)
        
    def gui_vod_event_callback( self, d, event, params ):
        if DEBUG:
            print >>sys.stderr,"bg: gui_vod_event_callback: Event: ", event
            print >>sys.stderr,"bg: gui_vod_event_callback: Params: ", params
        
        if event == VODEVENT_START:
            if params['filename']:
                stream = open( params['filename'], "rb" )
            else:
                stream = params['stream']
    
            blocksize = d.get_def().get_piece_length()
            streaminfo = { 'mimetype': params['mimetype'], 'stream': stream, 'length': params['length'],'blocksize':blocksize }
            
            duser = self.dusers[d]
            duser['streaminfo'] = streaminfo
            duser['uic'].set_streaminfo(duser['streaminfo'])
            duser['uic'].start_playback(d.get_def().get_infohash())
            
            self.approxplayerstate = MEDIASTATE_PLAYING
            
        elif event == VODEVENT_PAUSE:
            duser = self.dusers[d]
            duser['uic'].pause()
            self.approxplayerstate = MEDIASTATE_PAUSED
            
        elif event == VODEVENT_RESUME:
            duser = self.dusers[d]
            duser['uic'].resume()
            self.approxplayerstate = MEDIASTATE_PLAYING

    def get_supported_vod_events(self):
        return [ VODEVENT_START, VODEVENT_PAUSE, VODEVENT_RESUME ]

    #
    # VideoServer status/error reporting
    #
    def videoservthread_error_callback(self,e,url):
        """ Called by HTTP serving thread """
        wx.CallAfter(self.videoserver_error_guicallback,e,url)
        
    def videoserver_error_guicallback(self,e,url):
        print >>sys.stderr,"bg: Video server reported error",str(e)
        #    self.show_error(str(e))
        pass
        # ARNOTODO: schedule current Download for removal?

    def videoservthread_set_status_callback(self,status):
        """ Called by HTTP serving thread """
        wx.CallAfter(self.videoserver_set_status_guicallback,status)

    def videoserver_set_status_guicallback(self,status):
        print >>sys.stderr,"bg: Video server sets status callback",status
        # ARNOTODO: Report status to plugin

    #
    # reports vod stats collected periodically
    #
    def report_periodic_vod_stats(self,playing_dslist):
        #print >>sys.stderr, "VOD Stats"
        self.counter += 1
        if self.counter%self.interval == 0:
            event_reporter = get_reporter_instance()
            for ds in playing_dslist:
                dw = ds.get_download()
                b64_infohash = b64encode(dw.get_def().get_infohash())
                vod_stats = ds.get_vod_stats()
                #if vod_stats_has_key("prebuf"): event_reporter.add_event(b64_infohash, "prebufp:%d" % vod_stats['prebuf']) # prebuffering time that was needed
                if vod_stats.has_key("stall"): event_reporter.add_event(b64_infohash, "stall:%d" % vod_stats['stall']) # time the player stalled
                if vod_stats.has_key("late"): event_reporter.add_event(b64_infohash, "late:%d" % vod_stats['late']) # number of pieces arrived after they were due
                if vod_stats.has_key("dropped"): event_reporter.add_event(b64_infohash, "dropped:%d" % vod_stats['dropped']) # number of pieces lost
                if vod_stats.has_key("pos"): event_reporter.add_event(b64_infohash, "pos:%d" % vod_stats['pos']) # playback position

        # Added by Mugurel Ionut Andreica (UPB) for M23 Trial -- should report the amount of bytes uploaded on all the connections (so far)
        if (isLedbatTestRunning() == 1):
            global totalUpldBytes, totalUpldBytesDic
            #report upload-related information
            #print >>sys.stderr, "Ledbat test is running"
            
            try:
                event_reporter = get_reporter_instance()
                totalUpldSpeed = 0.0

                for ds in playing_dslist:
                    dw = ds.get_download()
                    infohash = dw.get_def().get_infohash()

                    #print >>sys.stderr, "cntDic=", len(totalUpldBytesDic.keys()), "; ds=", ds, "; dw=", dw, "; infohash=", infohash
                
                    upldSpeed = ds.get_current_speed(UPLOAD)
                    totalUpldSpeed += upldSpeed
                
                    ds_totalUpldBytes = ds.get_total_transferred(UPLOAD)
                    if (dw in totalUpldBytesDic.keys()):
                        totalUpldBytes -= totalUpldBytesDic[dw]
                    totalUpldBytesDic[dw] = ds_totalUpldBytes
                    totalUpldBytes += ds_totalUpldBytes

                # permid = getStringFromPermID(self.s.get_permid())
                b64_permid = b64encode(self.s.get_permid())
                event_reporter.add_event(b64_permid, "total_upload_speed:%.3f" % totalUpldSpeed)
                event_reporter.add_event(b64_permid, "total_uploaded_bytes:%d" % totalUpldBytes)

                print >>sys.stderr, "Reporting (permid=", getStringFromPermID(permid), ") => total_upload_speed=%.3f" % totalUpldSpeed, "; total_uploaded_bytes=%d" % totalUpldBytes
            except:
                print_exc()

class BGInstanceConnection(InstanceConnection):
    
    def __init__(self,singsock,connhandler,readlinecallback,videoHTTPServer):
        InstanceConnection.__init__(self, singsock, connhandler, readlinecallback)
        
        self.videoHTTPServer = videoHTTPServer
        self.urlpath = None
        self.cstreaminfo = {}
        self.shutteddown = False


    def set_streaminfo(self,streaminfo):
        """ Copy streaminfo contents and replace stream with a ControlledStream """
        """
        For each IC we create separate stream object and a unique path in the 
        HTTP server. This avoids nasty thread synchronization with the server
        when a new IC wants to play the same content. The Tribler Core stream
        does not allow multiple readers. This means we would have to stop
        the HTTP server from writing the stream to the old IC, before we
        can allow the new IC to read.
        
        We solved this as follows. The original Tribler Core stream is
        wrapped in a ControlledStream, one for each IC. When a new IC 
        wants to play we tell the old IC's ControlledStream to generate
        an EOF to the HTTP server, and tell the old IC to SHUTDOWN. We
        then either rewind the Tribler Core stream (VOD) or leave it (live)
        and tell the new IC to PLAY. The new ControlledStream will then
        be read by the HTTP server again.
        """
        self.cstreaminfo.update(streaminfo)
        stream = streaminfo['stream']
        cstream = ControlledStream(stream)
        self.cstreaminfo['stream'] = cstream

    def start_playback(self,infohash):
        """ Register cstream with HTTP server and tell IC to start reading """
        
        self.urlpath = '/'+binascii.hexlify(infohash)+'/'+str(random.random())
        self.videoHTTPServer.set_inputstream(self.cstreaminfo,self.urlpath)
        
        if DEBUG:
            print >> sys.stderr, "bg: Telling plugin to start playback of",self.urlpath
        
        self.write( 'PLAY '+self.get_video_url()+'\r\n' )


    def get_video_url(self):
        return 'http://127.0.0.1:'+str(self.videoHTTPServer.get_port())+self.urlpath

    def pause(self):
        self.write( 'PAUSE\r\n' )
        
    def resume(self):
        self.write( 'RESUME\r\n' )

    def info(self,infostr):
        self.write( 'INFO '+infostr+'\r\n' )        

    def shutdown(self):
        # SHUTDOWN Service
        if DEBUG:
            print >>sys.stderr,'bg: Shutting down connection to Plugin'
        if not self.shutteddown:
            self.shutteddown = True
            # Cause HTTP server thread to receive EOF on inputstream
            if len(self.cstreaminfo) != 0:
                self.cstreaminfo['stream'].close()
                self.videoHTTPServer.del_inputstream(self.urlpath)
            
            self.write( 'SHUTDOWN\r\n' )
            # Will cause BaseApp.connection_lost() to be called, where we'll
            # handle what to do about the Download that was started for this
            # IC.
            self.close() 


class ControlledStream:
    """ A file-like object that throws EOF when closed, without actually closing
    the underlying inputstream. See BGInstanceConnection.set_streaminfo() for
    an explanation on how this is used. 
    """
    def __init__(self,stream):
        self.stream = stream
        self.done = False # Event()
        
    def read(self,nbytes=None):
        if not self.done:
            return self.stream.read(nbytes)
        else:
            return '' # EOF

    def seek(self,pos,whence=os.SEEK_SET):
        self.stream.seek(pos,whence)
        
    def close(self):
        self.done = True
        # DO NOT close original stream



#M23TRIAL
class VictorTestThread(Thread):
    
    def __init__(self,installdir,permid):
        Thread.__init__(self)
        self.setName( "VictorTestThread"+self.getName())
        self.setDaemon(True)
        
        self.permid = permid
        self.prog = os.path.join(installdir,"leecher.exe")
        if not self.prog.startswith('"'):
            self.prog = '"'+self.prog+'"'

    def run(self):
        try:
            print >>sys.stderr,"m23trial: Running victor test on",currentThread().getName()

            [loghandle,logfilename] = tempfile.mkstemp()
            os.close(loghandle)

            """
            # TODO: make dynamic, e.g. read from website?
            hexhash = '31d86ad5fd8ac49792d3fca17326a7664c6f86e1'
            destfilename = 'test.mp4'
            destipport = '130.161.211.198:10000'
            myipport = '0.0.0.0:10020'

            tmpdir = tempfile.mkdtemp()
            fullfilename = os.path.join(tmpdir,destfilename)
            """

            #cmd = self.prog + " %s %s %s %s > %s 2>&1" % (hexhash, fullfilename, destipport, myipport, logfilename)
            cmd = self.prog + " > %s 2>&1" % logfilename
            print >>sys.stderr,"m23trial: victor test cmd is",cmd
            
            
            (child_stdin, child_stdout) = os.popen2(cmd,'b')  # DON'T FORGET 'b' OTHERWISE THINGS GO WRONG!
            
            # Sleep for 60 secs for program to complete, can't tell from OS with
            # Python on win32
            
            print >>sys.stderr,"m23trial: Giving Victor's program 30 secs to complete"
            time.sleep(30) 
            print >>sys.stderr,"m23trial: Time up"
            
            print >>sys.stderr,"m23trial: Reading Victor's log"
            # Dump logfile to ULANC
            logfile = open(logfilename, 'rb')
            data = logfile.read()
            logfile.close()

            from Tribler.Core.Statistics.StatusReporter import get_reporter_instance
            event_reporter = get_reporter_instance()
            event_reporter.add_event("Victor leecher", data )
            event_reporter.flush()
            
            # Fallback: print to log
            print >>sys.stderr,"m23trial: victor output",data

            print >>sys.stderr,"m23trial: Close child_in"
            child_stdin.close()
            print >>sys.stderr,"m23trial: Close child_out"
            child_stdout.close()
            
            
            print >>sys.stderr,"m23trial: Victor test done"
            
            # Mugurel's test
            print >>sys.stderr,"m23trial: Mugurel test start"
            
            testSender(self.permid)
            
            print >>sys.stderr,"m23trial: Mugurel test done"
            
            
            time.sleep(30000)
            
        except:
            print_exc()
            
            


##############################################################
#
# Main Program Start Here
#
##############################################################
def run_bgapp(appname,params = None):
    if params is None:
        params = [""]
    
    if len(sys.argv) > 1:
        params = sys.argv[1:]
    
    # Create single instance semaphore
    # Arno: On Linux and wxPython-2.8.1.1 the SingleInstanceChecker appears
    # to mess up stderr, i.e., I get IOErrors when writing to it via print_exc()
    #
    if sys.platform != 'linux2':
        single_instance_checker = wx.SingleInstanceChecker(appname+"-"+ wx.GetUserId())
    else:
        single_instance_checker = LinuxSingleInstanceChecker(appname)

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
    app = BackgroundApp(0, appname, params, single_instance_checker, installdir, I2I_LISTENPORT, BG_LISTENPORT)
    app.MainLoop()
    
    print >>sys.stderr,"Sleeping seconds to let other threads finish"
    time.sleep(2)

    if not ALLOW_MULTIPLE:
        del single_instance_checker
        
    # Ultimate catchall for hanging popen2's and what not
    os._exit(0)


if __name__ == '__main__':
    run_bgapp("SwarmPlugin")


import wx
import sys
import time
from traceback import print_exc
from Tribler.Video.utils import svcextdefaults, videoextdefaults
from Tribler.Core.API import *

DEBUG = True
# used to set different download speeds
DOWNLOADSPEED = 200

def svc_event_callback(d,event,params):
    if event == VODEVENT_START:

        stream = params["stream"]
        length   = params["length"]
        mimetype = params["mimetype"]

        # save stream on a temp file for verification
        f = open("stream","wb")

        while True:
            # Read data from the resulting stream.
            # Every stream.read() call will give back the available layers for the
            # following time slot.
            # The first 6 Bytes tell us the piece size. Therefore depending on the
            # size of the stream, knowing the piece size, we can see how many layers
            # are given back for that specific time slot.
            data = stream.read()
            print >>sys.stderr,"main: VOD ready callback: reading",type(data)
            print >>sys.stderr,"main: VOD ready callback: reading",len(data)
            if len(data) == 0:
                break
            f.write(data)
            time.sleep(2)

        # Stop the download
        if STOP_AFTER:
            d.stop()

        f.close()

        stream.close()


def state_callback(ds):
    try:
        d = ds.get_download()
        p = "%.0f %%" % (100.0*ds.get_progress())
        dl = "dl %.0f" % (ds.get_current_speed(DOWNLOAD))
        ul = "ul %.0f" % (ds.get_current_speed(UPLOAD))
        print >>sys.stderr,dlstatus_strings[ds.get_status() ],p,dl,ul,"====="
    except:
        print_exc()

    return (1.0,False)


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

    if torrentfilename.startswith("http") or torrentfilename.startswith(P2PURL_SCHEME):
        tdef = TorrentDef.load_from_url(torrentfilename)
    else:
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

# Ric: check if it as an SVC download. If it is add the enhancement layers to the dlfiles
def is_svc(dlfile, tdef):
    svcfiles = None

    if tdef.is_multifile_torrent():
        enhancement =  tdef.get_files(exts=svcextdefaults)
        # Ric: order the enhancement layer in the svcfiles list
        enhancement.sort()
        if tdef.get_length(enhancement[0]) == tdef.get_length(dlfile):
            svcfiles = [dlfile]
            svcfiles.extend(enhancement)

    return svcfiles

def run_test(params = None):

    if params is None:
        params = [""]

    if len(sys.argv) > 1:
        params = sys.argv[1:]
        torrentfilename = params[0]
    else:
        torrentfilename = self.select_torrent_from_disk()
        if torrentfilename is None:
            print >>sys.stderr,"main: User selected no file"
            self.OnExit()
            return False

    scfg = SessionStartupConfig()
    scfg.set_megacache( False )
    scfg.set_overlay( False )

    s = Session( scfg )

    tdef = TorrentDef.load(torrentfilename)
    dcfg = DownloadStartupConfig()


    # Select which video to play (if multiple)
    videofiles = tdef.get_files(exts=videoextdefaults)
    print >>sys.stderr,"main: Found video files",videofiles

    if len(videofiles) == 0:
        print >>sys.stderr,"main: No video files found! Let user select"
        # Let user choose any file

    if len(videofiles) > 1:
        print >>sys.stderr,"main: More then one video file found!!"
    else:
        videofile = videofiles[0]

    # Ric: check for svc
    if tdef.is_multifile_torrent():

        dlfiles = is_svc(videofile, tdef)

        if dlfiles is not None:
            print >>sys.stderr,"main: Found SVC video!!"
            dcfg.set_video_event_callback(svc_event_callback, svc=True)
            dcfg.set_selected_files(dlfiles)
    else:
        dcfg.set_video_event_callback(svc_event_callback)
        dcfg.set_selected_files([dlfile])


    # Ric: Set here the desired download speed
    dcfg.set_max_speed(DOWNLOAD,DOWNLOADSPEED)

    d = s.start_download( tdef, dcfg )

    d.set_state_callback(state_callback,getpeerlist=False)
    print >>sys.stderr,"main: Saving content to", d.get_dest_files()

    while True:
        time.sleep(360)
    print >>sys.stderr,"Sleeping seconds to let other threads finish"
    time.sleep(2)



if __name__ == '__main__':
    run_test()

import sys
import time
from traceback import print_exc

from Tribler.Core.API import *

DEBUG = False
FIRST_ITERATION = True
STOP_AFTER = False
QUIT = False
QUIT_NOW = False

def vod_event_callback(d,event,params):
    if event == VODEVENT_START:
    
        stream = params["stream"]
        length   = params["length"]
        mimetype = params["mimetype"]
        
        global FIRST_ITERATION
        global QUIT, QUIT_NOW
        
        epoch_server = None
        epoch_local = time.time()
        bitrate = None
        estduration = None
        currentSize = 0
        partialSize = length

        if startTime and FIRST_ITERATION:
            
            if DEBUG:
                print >>sys.stderr, "main: Seeking", startTime, estduration
            
            file = None
            blocksize = d.get_def().get_piece_length()
            if d.get_def().is_multifile_torrent():
                file = d.get_selected_files()[0]
            bitrate = d.get_def().get_bitrate(file)
            if bitrate is not None:
                estduration = float(length) / float(bitrate)
            
            if DEBUG:
                print >> sys.stderr, "main: Seeking: bitrate: ", bitrate, "duration: ", estduration

            if int(startTime) < int(estduration):
                seekbyte = float(bitrate * int(startTime))
                if mimetype == 'video/mp2t':
                    # Ric if it is a ts stream we can round the start
                    # byte to the beginning of a ts packet (ts pkt = 188 bytes)
                    seekbyte = seekbyte - seekbyte%188
                    
                stream.seek(int(seekbyte))      
                if DEBUG:  
                    print >>sys.stderr, "main: Seeking: seekbyte: ", seekbyte, "start time: ", startTime
                FIRST_ITERATION = False
            else:
                print >>sys.stderr, "main: Starting time exceeds video duration!!"

            if endTime:
                # Determine the final size of the stream depending on the end Time
                endbyte = float(bitrate * int(endTime))
                partialSize = endbyte - seekbyte

              
        else:
            print >>sys.stderr, "Seeking to the the beginning" 
            stream.seek(0)               
        
        
        f = open("video_part.mpegts","wb")
        prev_data = None    
        while not FIRST_ITERATION and (currentSize < partialSize):
            data = stream.read()
            if DEBUG:
                print >>sys.stderr,"main: VOD ready callback: reading",type(data)
                print >>sys.stderr,"main: VOD ready callback: reading",len(data)
            if len(data) == 0 or data == prev_data:
                if DEBUG:
                    print >>sys.stderr, "main: Same data replicated: we reached the end of the stream"
                break
            f.write(data)
            currentSize += len(data)
            prev_data = data
        
        
        # Stop the download
        if STOP_AFTER:
            d.stop()
            
        if QUIT:
            QUIT_NOW = True

        f.close()
    
        stream.close()
        
        print >> sys.stderr, "main: Seeking: END!!"
        

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



scfg = SessionStartupConfig()
scfg.set_megacache( False )
scfg.set_overlay( False )

s = Session( scfg )

params = [""]
startTime = None
endTime = None
    
if len(sys.argv) > 1:
    params = sys.argv[1:]
    torrentfilename = params[0]
else:
    print >>sys.stderr, "please provide at least a .torrent file"

if '-t' in params:
    idx = params.index('-t') 

    if len(params)>2 and params[idx+1].isdigit():
        startTime = params[idx+1]
    else:
        print >>sys.stderr, "please specify at least the start time!", len(params)

    if len(params)>3 and params[idx+2].isdigit():
        endTime = params[idx+2]
        print >>sys.stderr, "main: Starting download from sec.", startTime, "to sec.", endTime
    else:
        print >>sys.stderr, "main: Starting download from sec.", startTime

else:
    print >>sys.stderr, "No time specified. The entyre file will be downloaded"

if 'stopAfter' in params:
    STOP_AFTER = True
            
if 'quit' in params:
    STOP_AFTER = True
    QUIT = True
    
if 'debug' in params:
    DEBUG = True

#tdef = TorrentDef.load("test.torrent")
tdef = TorrentDef.load(torrentfilename)
dscfg = DownloadStartupConfig()
dscfg.set_video_event_callback( vod_event_callback )
#dscfg.set_max_uploads(16)

d = s.start_download( tdef, dscfg )

d.set_state_callback(state_callback,getpeerlist=False)

while True and not QUIT_NOW:
  time.sleep(30)


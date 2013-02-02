# Written by Riccardo Petrocco
# see LICENSE.txt for license information

import sys
import time
from traceback import print_exc

from Tribler.Core.API import *
from Tribler.Core.TorrentDef import *
from Tribler.Core.DownloadConfig import get_default_dest_dir

import Tribler.Core.Utilities.parseargs as parseargs

FIRST_ITERATION = True
QUIT_NOW = False
SESSION = None

argsdef = [('torr', '', 'original torrent file, mandatory argument!'), 
           ('start', '0', 'start time in seconds'), 
           ('end', '', 'end time in seconds, if not specified the program will download the original video file until the end'),
           ('videoOut', 'video_part.mpeg', 'name for the segment of downloaded video'),
           ('torrName', 'videoOut', 'name for the torrent created from the downloaded segment of video'),
           ('destdir', 'default download dir','dir to save torrent (and stream)'),
           ('continueDownload', 'False', 'set to true to continue downloading and seeding the original torrent'),
           ('createNewTorr', 'True', 'create a torrent with the newly downloaded section of video'),
           ('quitAfter', 'Flase', 'quit the program after the segmented video has been downloaded'),
           ('seedAfter', 'True', 'share the newly created torrent'),
           ('debug', 'False', 'set to true for additional information about the process')]

def get_usage(defs):
    return parseargs.formatDefinitions(defs,80)


def vod_event_callback(d,event,params):
  if event == VODEVENT_START:
    
    stream = params["stream"]
    length   = params["length"]
    mimetype = params["mimetype"]

    global FIRST_ITERATION, QUIT_NOW, SESSION
    epoch_server = None
    epoch_local = time.time()
    bitrate = None
    estduration = None
    currentSize = 0
    partialSize = length
    start = int(config['start'])
    end = int(config['end'])

    if FIRST_ITERATION:
            
      if config['debug']:
        print >>sys.stderr, "main: Seeking to second: ", config['start'], "estimated duration: ", estduration
            
      file = None
      blocksize = d.get_def().get_piece_length()
    
      if d.get_def().is_multifile_torrent():
        file = d.get_selected_files()[0]
      bitrate = d.get_def().get_bitrate(file)
      if bitrate is not None:
        estduration = float(length) / float(bitrate)

      if config['debug']:
        print >> sys.stderr, "main: Seeking: bitrate: ", bitrate, "duration: ", estduration
    
      if start < int(estduration):
        seekbyte = float(bitrate * start)

        # Works only with TS container
        if mimetype == 'video/mp2t':
          # Ric if it is a ts stream we can round the start
          # byte to the beginning of a ts packet (ts pkt = 188 bytes)
          seekbyte = seekbyte - seekbyte%188
                    
          stream.seek(int(seekbyte))      
          
          if config['debug']:  
            print >>sys.stderr, "main: Seeking: seekbyte: ", seekbyte, "start time: ", config['start']

        FIRST_ITERATION = False

      else:
        print >>sys.stderr, "main: Starting time exceeds video duration!!"

    if end != '':
      # Determine the final size of the stream depending on the end Time
      endbyte = float( bitrate * int(config['end']) )
      partialSize = endbyte - seekbyte

              
    else:
      print >>sys.stderr, "Seeking to the the beginning" 
      stream.seek(0)               
        
    basename = config['videoOut'] + '.mpeg'

    if config['destdir'] == 'default download dir':
        config['destdir'] = get_default_dest_dir()
        
    filename = os.path.join(config['destdir'], basename)

    if config['debug']:
      print >>sys.stderr, "main: Saving the file in the following location: ", filename

    f = open(filename,"wb")
    prev_data = None    

    while not FIRST_ITERATION and (currentSize < partialSize):
      data = stream.read()
      if config['debug']:
        print >>sys.stderr,"main: VOD ready callback: reading",type(data)
        print >>sys.stderr,"main: VOD ready callback: reading",len(data)
      if len(data) == 0 or data == prev_data:
        if config['debug']:
          print >>sys.stderr, "main: Same data replicated: we reached the end of the stream"
        break
      f.write(data)
      currentSize += len(data)
      prev_data = data
        
        
    # Stop the download
    if not config['continueDownload']:
      #SESSION.remove_
      d.stop()
    
    #seek(0)
            
    if config['quitAfter']:
      QUIT_NOW = True

    f.close()    
    stream.close()
       
    print >> sys.stderr, "main: Seeking: END!!"

    if config['createNewTorr']:
        createTorr(filename)      

def createTorr(filename):

  #get the time in a convinient format
  seconds = int(config['end']) - int(config['start'])
  m, s = divmod(seconds, 60)
  h, m = divmod(m, 60)

  humantime = "%02d:%02d:%02d" % (h, m, s)

  if config['debug']:
    print >>sys.stderr, "duration for the newly created torrent: ", humantime

  dcfg = DownloadStartupConfig()
#  dcfg.set_dest_dir(basename)
  tdef = TorrentDef()
  tdef.add_content( filename, playtime=humantime)
  tdef.set_tracker(SESSION.get_internal_tracker_url())
  print >>sys.stderr, tdef.get_tracker()
  tdef.finalize()
  
  if config['torrName'] == '':
    torrentbasename = config['videoOut']+'.torrent'
  else:
    torrentbasename = config['torrName']+'.torrent'
    
  torrentfilename = os.path.join(config['destdir'],torrentbasename)
  tdef.save(torrentfilename)
    
  if config['seedAfter']:
    if config['debug']:
      print >>sys.stderr, "Seeding the newly created torrent"
    d = SESSION.start_download(tdef,dcfg)
    d.set_state_callback(state_callback,getpeerlist=False)
        

def state_callback(ds):
  try:
    d = ds.get_download()
    p = "%.0f %%" % (100.0*ds.get_progress())
    dl = "dl %.0f" % (ds.get_current_speed(DOWNLOAD))
    ul = "ul %.0f" % (ds.get_current_speed(UPLOAD))
    print >>sys.stderr,dlstatus_strings[ds.get_status() ],p,dl,ul,"=====", d.get_def().get_name()
  except:
    print_exc()

  return (1.0,False)

if __name__ == "__main__":

  config, fileargs = parseargs.Utilities.parseargs(sys.argv, argsdef, presets = {})
  print >>sys.stderr,"config is",config
  print "fileargs is",fileargs
    
  if config['torr'] == '' or config['start'] == '':
    print "Usage:  ",get_usage(argsdef)
    sys.exit(0)


  scfg = SessionStartupConfig()
  scfg.set_megacache( False )
  scfg.set_overlay( False )
  s = Session( scfg )
  
  SESSION = s

  tdef = TorrentDef.load( config['torr'] )
  dscfg = DownloadStartupConfig()
  dscfg.set_video_event_callback( vod_event_callback )

  d = s.start_download( tdef, dscfg )

  d.set_state_callback(state_callback,getpeerlist=False)

  while not QUIT_NOW:
    time.sleep(10)


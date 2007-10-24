# Written by Arno Bakker 
# see LICENSE.txt for license information

from triblerAPI import *
from Tribler.API.RateManager import UserDefinedMaxAlwaysOtherwiseEquallyDividedRateManager

    
sscfg = SessionStartupConfig()
if sys.platform == 'win32':
    s = Session()
else:
    sscfg.set_state_dir('statedir')
    s = Session(sscfg)
    
r = UserDefinedMaxAlwaysOtherwiseEquallyDividedRateManager()
r.set_global_max_speed(DOWNLOAD,100)
t = 0
count = 0


def states_callback(dslist):
    global s
    global r
    global t
    global count
    
    adjustspeeds = False
    #if count % 4 == 0:
    #    adjustspeeds = True
    count += 1
    
    for ds in dslist:
        d = ds.get_download()
        print >>sys.stderr,"main: Stats",`d.get_def().get_name()`,dlstatus_strings[ds.get_status()],ds.get_progress(),"%",ds.get_error(),"up",ds.get_current_speed(UPLOAD),"down",ds.get_current_speed(DOWNLOAD),currentThread().getName()
        
        complete = ds.get_pieces_complete()
        print >>sys.stderr,"main: Pieces completed",`d.get_def().get_name()`,"len",len(complete)
        print >>sys.stderr,"main: Pieces completed",`d.get_def().get_name()`,complete[:60]
        
        """
        if ds.get_status() == DLSTATUS_SEEDING:
            print >>sys.stderr,"main: Syncing download because complete"
            d.checkpoint()
        """
        
        if adjustspeeds:
            r.add_downloadstate(ds)
        
    if adjustspeeds:
        r.adjust_speeds()
    return (1.0,False)



def state_callback(ds):
    d = ds.get_download()
    print >>sys.stderr,"main: SingleStats",`d.get_def().get_name()`,dlstatus_strings[ds.get_status()],ds.get_progress(),"%",ds.get_error(),"up",ds.get_current_speed(UPLOAD),"down",ds.get_current_speed(DOWNLOAD),currentThread().getName()
    return (1.0,False)


def vod_ready_callback(mimetype,stream):
    print >>sys.stderr,"main: VOD ready callback called",currentThread().getName(),"###########################################################",mimetype


if __name__ == "__main__":
    
    s.set_download_states_callback(states_callback,getpeerlist=False)
    # Torrent 1
    if sys.platform == 'win32':
        tdef = TorrentDef.load('bla.torrent')
    else:
        #tdef = TorrentDef.load('/tmp/bla3multi.torrent')
        tdef = TorrentDef.load('/arno/tmp/scandir/bla.torrent')
        
    dcfg = DownloadStartupConfig()
    #dcfg.set_dest_dir('/arno/tmp/scandir')
    """
    dcfg.set_video_on_demand(vod_ready_callback)
    #dcfg.set_selected_files('star-wreck-in-the-pirkinning.txt') # play this video
    dcfg.set_selected_files('star_wreck_in_the_pirkinning_subtitled_xvid.avi') # play this video
    """
    d = s.start_download(tdef,dcfg)
    
    # Torrent 2
    """
    if sys.platform == 'win32':
        tdef = TorrentDef.load('bla2.torrent')
    else:
        tdef = TorrentDef.load('/tmp/bla2.torrent')
    d2 = s.start_download(tdef)
    d2.set_state_callback(state_callback)
    """

    time.sleep(20)
    
    #s.shutdown()
    s.remove_download(d,removecontent=True)
    
    time.sleep(2500) # TODO: make sure we don't quit before shutdown checkpoint complete
    

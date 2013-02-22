# Based on SwiftDownloadImpl.py by Arno Bakker, modified by Egbert Bouman for the use with libtorrent

import sys
import copy
import libtorrent as lt

from traceback import print_exc

from Tribler.Core import NoDispersyRLock
from Tribler.Core.simpledefs import *
from Tribler.Core.DownloadState import DownloadState
from Tribler.Core.APIImplementation.DownloadRuntimeConfig import DownloadRuntimeConfig
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.APIImplementation import maketorrent
from Tribler.Core.osutils import fix_filebasename
from Tribler.Core.Libtorrent.LibtorrentMgr import LibtorrentMgr
from Tribler.Core.APIImplementation.maketorrent import torrentfilerec2savefilename, savefilenames2finaldest
from Tribler.Core.TorrentDef import TorrentDefNoMetainfo, TorrentDef
from Tribler.Core.exceptions import VODNoFileSelectedInMultifileTorrentException
            
DEBUG = True


class VODFile(object):
    __slots__ = ['_file', '_download'] 

    def __init__(self, f, d): 
        object.__setattr__(self, '_file', f)
        object.__setattr__(self, '_download', d)

    def __getattr__(self, name):
        return getattr(self._file, name) 

    def __setattr__(self, name, value): 
        setattr(self._file, name, value) 

    def read(self, *args):
        result = self._file.read(*args)
        self._download.vod_readpos += len(result)
        return result

    def seek(self, *args):
        self._file.seek(*args)
        self._download.vod_readpos += args[0]
        

class LibtorrentDownloadImpl(DownloadRuntimeConfig): 
    """ Download subclass that represents a libtorrent download."""
    
    def __init__(self, session, tdef):
        self.dllock = NoDispersyRLock()
        self.session = session
        self.tdef = tdef
        self.handle = None

        # Just enough so error saving and get_state() works
        self.error = None
        # To be able to return the progress of a stopped torrent, how far it got.
        self.progressbeforestop = 0.0
        self.filepieceranges = []

        # Libtorrent session manager performing the actual download.
        self.ltmgr = LibtorrentMgr.getInstance()

        # Libtorrent status
        self.dlstates = [DLSTATUS_WAITING4HASHCHECK, DLSTATUS_HASHCHECKING, DLSTATUS_METADATA, DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING, DLSTATUS_SEEDING, DLSTATUS_ALLOCATING_DISKSPACE, DLSTATUS_HASHCHECKING]
        self.dlstate = DLSTATUS_WAITING4HASHCHECK
        self.length = 0L
        self.progress = 0.0
        self.bufferprogress = 0.0
        self.curspeeds = {DOWNLOAD:0.0,UPLOAD:0.0} # bytes/s
        self.done = False
        self.pause_after_next_hashcheck = False
        self.prebuffsize = 5*1024*1024
        self.queue_position = -1

        self.vod_readpos = 0
        self.vod_pausepos = 0
        self.vod_status = ""

        self.lm_network_vod_event_callback = None
        self.pstate_for_restart = None
        
        self.cew_scheduled = False

    def get_def(self):
        return self.tdef

    def setup(self, dcfg = None, pstate = None, initialdlstatus = None, lm_network_engine_wrapper_created_callback = None, lm_network_vod_event_callback = None, wrapperDelay = 0):
        """
        Create a Download object. Used internally by Session.
        @param dcfg DownloadStartupConfig or None (in which case 
        a new DownloadConfig() is created and the result 
        becomes the runtime config of this Download.
        """
        # Called by any thread, assume sessionlock is held
        try:
            with self.dllock:
                # Copy dlconfig, from default if not specified
                if dcfg is None:
                    cdcfg = DownloadStartupConfig()
                else:
                    cdcfg = dcfg
                self.dlconfig = copy.copy(cdcfg.dlconfig)
                
                # Things that only exist at runtime
                self.dlruntimeconfig= {}
                self.dlruntimeconfig['max_desired_upload_rate'] = 0
                self.dlruntimeconfig['max_desired_download_rate'] = 0    
                    
                # H4xor this so the 'name' field is safe
                self.correctedinfoname = fix_filebasename(self.tdef.get_name_as_unicode())                

                if not isinstance(self.tdef, TorrentDefNoMetainfo):
                    self.set_files()
        
                if DEBUG:
                    print >> sys.stderr, "LibtorrentDownloadImpl: setup: initialdlstatus", self.tdef.get_infohash(), initialdlstatus
                    
                if initialdlstatus == DLSTATUS_STOPPED:
                    self.pause_after_next_hashcheck = True
                    
                self.create_engine_wrapper(lm_network_engine_wrapper_created_callback, pstate, lm_network_vod_event_callback, initialdlstatus = initialdlstatus, wrapperDelay = wrapperDelay)
                
            self.pstate_for_restart = pstate

        except Exception, e:
            with self.dllock:
                self.error = e
                print_exc()

    def create_engine_wrapper(self, lm_network_engine_wrapper_created_callback, pstate, lm_network_vod_event_callback, initialdlstatus = None, wrapperDelay = 0):
        with self.dllock:
            if not self.cew_scheduled:
                network_create_engine_wrapper_lambda = lambda:self.network_create_engine_wrapper(lm_network_engine_wrapper_created_callback, pstate, lm_network_vod_event_callback, initialdlstatus)
                self.session.lm.rawserver.add_task(network_create_engine_wrapper_lambda, wrapperDelay)
                self.cew_scheduled = True
                    
    def network_create_engine_wrapper(self, lm_network_engine_wrapper_created_callback, pstate, lm_network_vod_event_callback, initialdlstatus = None):
        # Called by any thread, assume dllock already acquired
        if DEBUG:
            print >>sys.stderr,"LibtorrentDownloadImpl: create_engine_wrapper()"

        atp = {}
        atp["save_path"] = str(self.dlconfig['saveas'])
        atp["storage_mode"] = lt.storage_mode_t.storage_mode_sparse
        atp["paused"] = True
        atp["auto_managed"] = False
        atp["duplicate_is_error"] = True
        
        if not isinstance(self.tdef, TorrentDefNoMetainfo):
            metainfo = self.tdef.get_metainfo()
            torrentinfo = lt.torrent_info(metainfo)
            
            torrent_files = torrentinfo.files()
            swarmname = os.path.commonprefix([file_entry.path for file_entry in torrent_files]) if self.tdef.is_multifile_torrent() else ''

            if self.tdef.is_multifile_torrent() and swarmname != self.correctedinfoname:
                for i, file_entry in enumerate(torrent_files):
                    filename = file_entry.path[len(swarmname):]
                    torrentinfo.rename_file(i, str(os.path.join(self.correctedinfoname, filename)))
        
            atp["ti"] = torrentinfo
            if pstate and pstate.get('engineresumedata', None):
                atp["resume_data"] = lt.bencode(pstate['engineresumedata'])
        else:
            atp["info_hash"] = lt.big_number(self.tdef.get_infohash())
            atp["name"] = self.tdef.get_name_as_unicode()

        self.handle = self.ltmgr.add_torrent(self, atp)
        self.lm_network_vod_event_callback = lm_network_vod_event_callback

        if self.handle:
            self.set_selected_files()
            if self.get_mode() == DLMODE_VOD:
                self.set_vod_mode()
            self.handle.resume()
            
        with self.dllock:
            self.cew_scheduled = False
            
        if lm_network_engine_wrapper_created_callback is not None:
            lm_network_engine_wrapper_created_callback(self,pstate)
            
    def set_vod_mode(self):
        self.vod_status = ""
        
        # Define which file to DL in VOD mode
        self.videoinfo = {'live' : self.get_def().get_live()}
        
        if self.tdef.is_multifile_torrent():
            if len(self.dlconfig['selected_files']) == 0:
                raise VODNoFileSelectedInMultifileTorrentException() 
            filename = self.dlconfig['selected_files'][0]
            self.videoinfo['index'] = self.get_def().get_index_of_file_in_files(filename)
            self.videoinfo['inpath'] = filename
            self.videoinfo['bitrate'] = self.get_def().get_bitrate(filename) 
                           
        else:                
            filename = self.get_def().get_name()
            self.videoinfo['index'] = 0
            self.videoinfo['inpath'] = filename
            self.videoinfo['bitrate'] = self.get_def().get_bitrate()

        self.videoinfo['outpath'] = self.files[self.videoinfo['index']]
        self.videoinfo['mimetype'] = self.get_mimetype(filename)
        self.videoinfo['usercallback'] = lambda event, params : self.session.uch.perform_vod_usercallback(self, self.dlconfig['vod_usercallback'], event, params)
        self.videoinfo['userevents'] = self.dlconfig['vod_userevents'][:]
                
        self.handle.set_sequential_download(True)
        
        self.prebuffsize = max(int(self.videoinfo['outpath'][1] * 0.05), 5*1024*1024)

        if self.handle.status().progress == 1.0:
            if DEBUG:
                print >> sys.stderr, "LibtorrentDownloadImpl: VOD requested, but file complete on disk", self.videoinfo
            self.start_vod(complete = True)
        else:
            if DEBUG:
                print >> sys.stderr, "LibtorrentDownloadImpl: going into VOD mode", self.videoinfo
            self.set_state_callback(self.monitor_vod, delay = 5.0)
               
    def monitor_vod(self, ds):
        status = self.handle.status()
        pieces = status.pieces if status else []

        startofbuffer = 0
        if not self.vod_status and self.tdef.is_multifile_torrent():
            selected_files = self.get_selected_files()
            startofbuffer = [t for t, _, f in self.filepieceranges if not selected_files or f == selected_files[0]][0]
        else:
            startofbuffer = int(self.vod_readpos / self.handle.get_torrent_info().piece_length())
        endofbuffer = startofbuffer + int(self.prebuffsize / self.handle.get_torrent_info().piece_length() + 1)
        buffer = pieces[startofbuffer:endofbuffer]
        self.bufferprogress = float(buffer.count(True))/len(buffer) if len(buffer) > 0 else 1

        if DEBUG:        
            print >> sys.stderr, 'LibtorrentDownloadImpl: bufferprogress = %.2f' % self.bufferprogress
        
        if self.bufferprogress >= 1:
            if not self.vod_status:
                self.vod_pausepos = startofbuffer * self.handle.get_torrent_info().piece_length()
                self.start_vod(complete = False)
            else:
                self.resume_vod()

        elif self.bufferprogress <= 0.1 and self.vod_status:
            self.pause_vod()

        delay = 1.0 if self.handle and not self.handle.is_paused() else 0.0            
        return (delay, False)
    
    def start_vod(self, complete = False):
        if not self.vod_status:
            self.vod_status = "started"
            self.lm_network_vod_event_callback(self.videoinfo, VODEVENT_START,
                                                   {"complete":  complete,
                                                    "filename":  self.videoinfo["outpath"][0] if complete else None,
                                                    "mimetype":  self.videoinfo["mimetype"],
                                                    "stream":    None if complete else VODFile(open(self.videoinfo['outpath'][0], 'rb'), self),
                                                    "length":    self.videoinfo['outpath'][1],
                                                    "bitrate":   self.videoinfo["bitrate"]})
    
            if DEBUG:
                print >> sys.stderr, "LibtorrentDownloadImpl: VOD started", self.videoinfo['outpath'][0]
    
    def resume_vod(self):
        if self.vod_status == "paused":
            self.vod_status = "resumed"
            self.videoinfo["usercallback"](VODEVENT_RESUME, {})

            if DEBUG:
                print >> sys.stderr, "LibtorrentDownloadImpl: VOD resumed"

    def pause_vod(self):
        if self.vod_status != "paused":
            self.vod_status = "paused"
            self.vod_pausepos = self.vod_readpos
            self.videoinfo["usercallback"](VODEVENT_PAUSE, {})

            if DEBUG:
                print >> sys.stderr, "LibtorrentDownloadImpl: VOD paused"

    def process_alert(self, alert, alert_type):
        if DEBUG:
            print >> sys.stderr, "LibtorrentDownloadImpl: alert %s with message %s" % (alert_type, alert)

        if self.handle and self.handle.is_valid():
            
            status = self.handle.status()

            with self.dllock:

                if alert_type == 'metadata_received_alert':
                    self.metadata = {'info': lt.bdecode(self.handle.get_torrent_info().metadata())}
                    self.tdef = TorrentDef.load_from_dict(self.metadata)
                    self.set_files()
                    
                    if self.session.lm.rtorrent_handler:
                        self.session.lm.rtorrent_handler.save_torrent(self.tdef)
                    elif self.session.lm.torrent_db:
                        self.session.lm.torrent_db.addExternalTorrent(self.tdef, source = '', extra_info = {'status':'good'}, commit = True)
                        
                    # Checkpoint
                    (infohash, pstate) = self.network_checkpoint()
                    checkpoint = lambda : self.session.lm.save_download_pstate(infohash, pstate)
                    self.session.lm.rawserver.add_task(checkpoint, 0)

                if alert_type == 'torrent_checked_alert' and self.pause_after_next_hashcheck:
                    self.handle.pause()
                    self.pause_after_next_hashcheck = False
                    self.dlstate = DLSTATUS_STOPPED
                else:
                    if alert_type == 'torrent_paused_alert':
                        self.dlstate = DLSTATUS_STOPPED_ON_ERROR if status.error else DLSTATUS_STOPPED
                    else:
                        self.dlstate = self.dlstates[status.state]
    
                    self.length = float(status.total_wanted)
                    self.progress = status.progress
                    self.curspeeds[DOWNLOAD] = float(status.download_payload_rate)
                    self.curspeeds[UPLOAD] = float(status.upload_payload_rate)
                    self.error = unicode(status.error) if status.error else None
                    
    def set_files(self):
        metainfo = self.tdef.get_metainfo()
        self.set_filepieceranges(metainfo)

        # Allow correctinfoname to be overwritten for multifile torrents only
        if 'files' in metainfo['info'] and self.dlconfig['correctedfilename'] and self.dlconfig['correctedfilename'] != '':
            self.correctedinfoname = self.dlconfig['correctedfilename']

        self.files = []
        if 'files' in metainfo['info']:
            for x in metainfo['info']['files']:
                savepath = torrentfilerec2savefilename(x)
                full = savefilenames2finaldest(self.get_content_dest(), savepath)
                # Arno: TODO: this sometimes gives too long filenames for 
                # Windows. When fixing this take into account that 
                # Download.get_dest_files() should still produce the same
                # filenames as your modifications here.
                self.files.append((full, x['length']))
        else:
            self.files.append((self.get_content_dest(), metainfo['info']['length']))
            
    def set_selected_files(self, selected_files = None):
        with self.dllock:
            
            if self.handle is not None and not isinstance(self.tdef, TorrentDefNoMetainfo):
    
                if selected_files is None:
                    selected_files = self.dlconfig['selected_files']
                else:
                    self.dlconfig['selected_files'] = selected_files
                
                torrent_files = self.handle.get_torrent_info().files()
                swarmname = os.path.commonprefix([file_entry.path for file_entry in torrent_files]) if self.tdef.is_multifile_torrent() else ''
                
                filepriorities = []
                for file_entry in torrent_files:
                    filename = file_entry.path[len(swarmname):]
        
                    if filename in selected_files or not selected_files:
                        filepriorities.append(1)
                    else:
                        filepriorities.append(0)
        
                self.handle.prioritize_files(filepriorities)
                
    def move_storage(self, new_dir):
        with self.dllock:
            if self.handle is not None and not isinstance(self.tdef, TorrentDefNoMetainfo):
                self.handle.move_storage(new_dir)
                self.dlconfig['saveas'] = new_dir
                return True
        return False
                
    def get_status(self):
        """ Returns the status of the download.
        @return DLSTATUS_*
        """
        with self.dllock:
            return self.dltate
    
    def get_length(self):
        """ Returns the size of the torrent content.
        @return float
        """ 
        with self.dllock:
            return self.length

    def get_progress(self):
        """ Return fraction of content downloaded.
        @return float 0..1
        """
        with self.dllock:
            return self.progress

    def get_current_speed(self, dir):
        """ Return last reported speed in KB/s 
        @return float
        """
        with self.dllock:
            return self.curspeeds[dir]/1024.0

    def network_get_stats(self, getpeerlist):
        """
        @return (status, stats, logmsgs, coopdl_helpers, coopdl_coordinator)
        """
        # Called by any thread, assume dllock already acquired

        stats = {}
        stats['down'] = self.curspeeds[DOWNLOAD]
        stats['up'] = self.curspeeds[UPLOAD]
        stats['frac'] = self.progress
        stats['wanted'] = self.length
        
        if DEBUG:
            print >> sys.stderr, "Torrent", self.handle.name(), "PROGRESS", self.progress, "QUEUEPOS", self.queue_position, "DLSTATE", self.dlstate, "SEEDTIME", self.handle.status().seeding_time
            
        stats['stats'] = self.network_create_statistics_reponse()
        stats['time'] = self.network_calc_eta()
        stats['vod_prebuf_frac'] = self.network_calc_prebuf_frac()
        stats['vod'] = True
        stats['vod_playable'] = self.progress == 1.0 or (stats['vod_prebuf_frac'] == 1.0 and self.curspeeds[DOWNLOAD] > 0.0)
        stats['vod_playable_after'] = self.network_calc_prebuf_eta()
        stats['vod_stats'] = self.network_get_vod_stats()
        stats['spew'] = self.network_create_spew_from_peerlist() if getpeerlist else []            
        
        logmsgs = []
        coopdl_helpers = None
        coopdl_coordinator = None
        return (self.dlstate, stats, logmsgs, coopdl_helpers, coopdl_coordinator)

    def network_create_statistics_reponse(self):
        status = self.handle.status() if self.handle else None
        numTotSeeds = status.num_complete
        numTotPeers = status.num_incomplete
        numleech = status.list_peers
        numseeds = status.list_seeds
        pieces = status.pieces if status else None
        upTotal = status.total_upload
        downTotal = status.total_download
        return LibtorrentStatisticsResponse(numTotSeeds, numTotPeers, numseeds, numleech, pieces, upTotal, downTotal)
    
    def network_calc_eta(self):
        bytestogof = (1.0 - self.progress) * float(self.length)
        dlspeed = max(0.000001, self.curspeeds[DOWNLOAD])
        return bytestogof / dlspeed

    def network_calc_prebuf_frac(self):
        if self.progress * self.length >= self.prebuffsize:
            return 1.0
        return self.bufferprogress

    def network_calc_prebuf_eta(self):
        bytestogof = (1.0 - self.network_calc_prebuf_frac()) * float(self.prebuffsize)
        dlspeed = max(0.000001, self.curspeeds[DOWNLOAD])
        return bytestogof/dlspeed

    def network_get_vod_stats(self):
        d = {}
        d['played'] = None
        d['late'] = None 
        d['dropped'] = None 
        d['stall'] = None 
        d['pos'] = None
        d['prebuf'] = None
        d['firstpiece'] = 0 
        d['npieces'] = ((self.length + 1023) / 1024)
        return d
    
    def network_create_spew_from_peerlist(self):
        plist = []
        with self.dllock:
            peer_infos = self.handle.get_peer_info()
        for peer_info in peer_infos:
            peer_dict = {}
            peer_dict['id'] = peer_info.pid
            peer_dict['extended_version'] = peer_info.client
            peer_dict['ip'] = peer_info.ip[0]
            peer_dict['port'] = peer_info.ip[1]
            peer_dict['optimistic'] = bool(peer_info.flags & 2048) # optimistic_unchoke = 0x800 seems unavailable in python bindings
            peer_dict['direction'] = 'L' if bool(peer_info.flags & peer_info.local_connection) else 'R'
            peer_dict['uprate'] = peer_info.up_speed
            peer_dict['uinterested'] = bool(peer_info.flags & peer_info.interesting)
            peer_dict['uchoked'] = bool(peer_info.flags & peer_info.choked)
            peer_dict['uhasqueries'] = peer_info.upload_queue_length > 0
            peer_dict['uflushed'] = peer_info.used_send_buffer > 0
            peer_dict['downrate'] = peer_info.down_speed
            peer_dict['dinterested'] = bool(peer_info.flags & peer_info.remote_interested)
            peer_dict['dchoked'] = bool(peer_info.flags & peer_info.remote_choked)
            peer_dict['snubbed'] = bool(peer_info.flags & 4096) # snubbed = 0x1000 seems unavailable in python bindings
            peer_dict['utotal'] = peer_info.total_download
            peer_dict['dtotal'] = peer_info.total_upload
            peer_dict['completed'] = peer_info.progress
            peer_dict['have'] = peer_info.pieces
            peer_dict['speed'] = peer_info.remote_dl_rate
            plist.append(peer_dict)
            
        return plist
        
    def set_state_callback(self, usercallback, getpeerlist = False, delay = 0.0):
        """ Called by any thread """
        with self.dllock:
            network_get_state_lambda = lambda:self.network_get_state(usercallback, getpeerlist)
            self.session.lm.rawserver.add_task(network_get_state_lambda, delay)

    def network_get_state(self,usercallback, getpeerlist, sessioncalling = False):
        """ Called by network thread """
        with self.dllock:
            if self.handle is None:
                if DEBUG:
                    print >> sys.stderr, "LibtorrentDownloadImpl: network_get_state: Download not running"
                ds = DownloadState(self, DLSTATUS_STOPPED, self.error, self.progressbeforestop)
            else:
                (status, stats, logmsgs, proxyservice_proxy_list, proxyservice_doe_list) = self.network_get_stats(getpeerlist)
                ds = DownloadState(self, status, self.error, self.get_progress(), stats = stats, filepieceranges = self.filepieceranges, logmsgs = logmsgs, proxyservice_proxy_list = proxyservice_proxy_list, proxyservice_doe_list = proxyservice_doe_list)
                self.progressbeforestop = ds.get_progress()
                        
            if sessioncalling:
                return ds

            # Invoke the usercallback function via a new thread.
            # After the callback is invoked, the return values will be passed to the returncallback for post-callback processing.
            if not self.done:
                self.session.uch.perform_getstate_usercallback(usercallback, ds, self.sesscb_get_state_returncallback)

    def sesscb_get_state_returncallback(self, usercallback, when, newgetpeerlist):
        """ Called by SessionCallbackThread """
        with self.dllock:
            if when > 0.0:
                # Schedule next invocation, either on general or DL specific
                network_get_state_lambda = lambda:self.network_get_state(usercallback,newgetpeerlist)
                self.session.lm.rawserver.add_task(network_get_state_lambda,when)

    def stop(self):
        """ Called by any thread """
        self.stop_remove(removestate = False, removecontent = False)

    def stop_remove(self, removestate = False, removecontent = False):
        """ Called by any thread. Called on Session.remove_download() """
        self.done = removestate
        self.network_stop(removestate = removestate, removecontent = removecontent)

    def network_stop(self, removestate, removecontent):
        """ Called by network thread, but safe for any """
        with self.dllock:
            if DEBUG:
                print >>sys.stderr,"LibtorrentDownloadImpl: network_stop", self.tdef.get_name()

            pstate = self.network_get_persistent_state()
            if self.handle is not None:
                if DEBUG:
                    print >> sys.stderr, "LibtorrentDownloadImpl: network_stop: engineresumedata from torrent handle"
                if removestate:
                    self.ltmgr.remove_torrent(self, removecontent)
                    self.handle = None
                else:
                    self.handle.pause()
                    pstate['engineresumedata'] = self.handle.write_resume_data() if self.handle.status().has_metadata else None
                    self.dlstate = DLSTATUS_STOPPED
                self.pstate_for_restart = pstate
            else:
                # This method is also called at Session shutdown, where one may
                # choose to checkpoint its Download. If the Download was 
                # stopped before, pstate_for_restart contains its resumedata.
                # and that should be written into the checkpoint.
                #
                if self.pstate_for_restart is not None:
                    if DEBUG:
                        print >>sys.stderr,"LibtorrentDownloadImpl: network_stop: Reusing previously saved engineresume data for checkpoint"
                    # Don't copy full pstate_for_restart, as the torrent
                    # may have gone from e.g. HASHCHECK at startup to STOPPED
                    # now, at shutdown. In other words, it was never active
                    # in this session and the pstate_for_restart still says 
                    # HASHCHECK.
                    pstate['engineresumedata'] = self.pstate_for_restart['engineresumedata']
                elif DEBUG:
                    print >> sys.stderr, "LibtorrentDownloadImpl: network_stop: Could not reuse engineresumedata as pstart_for_restart is None"
                    
            # Offload the removal of the dlcheckpoint to another thread
            if removestate:
                self.session.uch.perform_removestate_callback(self.tdef.get_infohash(), None, False)
                
            return (self.tdef.get_infohash(), pstate)

    def get_content_dest(self):
        """ Returns the file to which the downloaded content is saved. """
        return os.path.join(self.get_dest_dir(), self.correctedinfoname)
    
    def set_filepieceranges(self, metainfo):
        """ Determine which file maps to which piece ranges for progress info """
        if DEBUG:
            print >> sys.stderr,"LibtorrentDownloadImpl: set_filepieceranges:", self.dlconfig['selected_files']

        self.filepieceranges = maketorrent.get_length_filepieceranges_from_metainfo(metainfo, [])[1]

        # dlconfig['priority'] will propagate the selected files to Storage
        # self.dlconfig["priority"] = maketorrent.get_length_priority_from_metainfo(metainfo, self.dlconfig['selected_files'])[1]
        
    def restart(self, initialdlstatus = None):
        """ Restart the Download """
        # Called by any thread 
        if DEBUG:
            print >>sys.stderr,"LibtorrentDownloadImpl: restart:", self.tdef.get_name()
        with self.dllock:
            if self.handle is None:
                self.error = None
                self.create_engine_wrapper(self.session.lm.network_engine_wrapper_created_callback, self.pstate_for_restart, self.session.lm.network_vod_event_callback, initialdlstatus = initialdlstatus)
            else:
                self.handle.resume()   
                if self.get_mode() == DLMODE_VOD:
                    self.set_vod_mode()

    def set_max_desired_speed(self, direct, speed):
        if DEBUG:
            print >> sys.stderr,"LibtorrentDownloadImpl: set_max_desired_speed", direct, speed
        
        with self.dllock:
            if direct == UPLOAD:
                self.dlruntimeconfig['max_desired_upload_rate'] = speed
            else:
                self.dlruntimeconfig['max_desired_download_rate'] = speed

    def get_max_desired_speed(self, direct):
        with self.dllock:
            if direct == UPLOAD:
                return self.dlruntimeconfig['max_desired_upload_rate']
            else:
                return self.dlruntimeconfig['max_desired_download_rate']

    def get_dest_files(self, exts = None):
        """
        You can give a list of extensions to return. If None: return all dest_files
        @return list of (torrent,disk) filename tuples.
        """

        def get_ext(filename):
            _, ext = os.path.splitext(filename)
            if ext != '' and ext[0] == '.':
                ext = ext[1:]
            return ext
        
        with self.dllock:
            f2dlist = []
            metainfo = self.tdef.get_metainfo() 
            if metainfo:
                if 'files' not in metainfo['info']:
                    # single-file torrent
                    diskfn = self.get_content_dest()
                    _, filename = os.path.split(diskfn)
                    f2dtuple = (filename, diskfn)
                    ext = get_ext(diskfn)
                    if exts is None or ext in exts:
                        f2dlist.append(f2dtuple)
                else:
                    # multi-file torrent
                    if len(self.dlconfig['selected_files']) > 0:
                        fnlist = self.dlconfig['selected_files']
                    else:
                        fnlist = self.tdef.get_files(exts=exts)
                        
                    for filename in fnlist:
                        filerec = maketorrent.get_torrentfilerec_from_metainfo(filename,metainfo)
                        savepath = maketorrent.torrentfilerec2savefilename(filerec)
                        diskfn = maketorrent.savefilenames2finaldest(self.get_content_dest(),savepath)
                        ext = get_ext(diskfn)
                        if exts is None or ext in exts:
                            f2dtuple = (filename,diskfn)
                            f2dlist.append(f2dtuple)
            return f2dlist

    def checkpoint(self):
        """ Called by any thread """
        self.network_checkpoint()
    
    def network_checkpoint(self):
        """ Called by network thread """
        with self.dllock:
            pstate = self.network_get_persistent_state() 
            if self.handle is not None:
                if self.pstate_for_restart is not None:
                    resdata = self.pstate_for_restart['engineresumedata']
                else:
                    resdata = None
            else:
                resdata = self.handle.write_resume_data()
            pstate['engineresumedata'] = resdata
            return (self.tdef.get_infohash(), pstate)

    def network_get_persistent_state(self):
        # Assume sessionlock is held
        pstate = {}
        pstate['version'] = PERSISTENTSTATE_CURRENTVERSION
        if isinstance(self.tdef, TorrentDefNoMetainfo):
            pstate['metainfo'] = {'infohash': self.tdef.get_infohash(), 'name': self.tdef.get_name_as_unicode()}
        else:
            pstate['metainfo'] = self.tdef.get_metainfo()
            
        dlconfig = copy.copy(self.dlconfig)
        # Reset unpicklable params
        dlconfig['vod_usercallback'] = None
        dlconfig['mode'] = DLMODE_NORMAL
        pstate['dlconfig'] = dlconfig

        pstate['dlstate'] = {}
        ds = self.network_get_state(None, False, sessioncalling = True)
        pstate['dlstate']['status'] = ds.get_status()
        pstate['dlstate']['progress'] = ds.get_progress()
        pstate['dlstate']['swarmcache'] = None
        
        if DEBUG:
            print >> sys.stderr, "LibtorrentDownloadImpl: network_get_persistent_state: status", dlstatus_strings[ds.get_status()], "progress", ds.get_progress()

        pstate['engineresumedata'] = None
        return pstate

    def get_coopdl_role_object(self,role):
        """ Called by network thread """
        return None

    def recontact_tracker(self):
        """ Called by any thread """
        pass

    # ARNOCOMMENT: better if we removed this from Core, user knows which
    # file he selected to play, let him figure out MIME type
    def get_mimetype(self, file):
        (prefix, ext) = os.path.splitext(file)
        ext = ext.lower()
        mimetype = None
        if sys.platform == 'win32':
            # TODO: Use Python's mailcap facility on Linux to find player
            try:
                from Tribler.Video.utils import win32_retrieve_video_play_command

                [mimetype, playcmd] = win32_retrieve_video_play_command(ext, file)
                if DEBUG:
                    print >>sys.stderr, "LibtorrentDownloadImpl: Win32 reg said MIME type is", mimetype
            except:
                if DEBUG:
                    print_exc()
                pass
        else:
            try:
                import mimetypes
                # homedir = os.path.expandvars('${HOME}')
                from Tribler.Core.osutils import get_home_dir
                homedir = get_home_dir()
                homemapfile = os.path.join(homedir, '.mimetypes')
                mapfiles = [homemapfile] + mimetypes.knownfiles
                mimetypes.init(mapfiles)
                (mimetype, encoding) = mimetypes.guess_type(file)
                
                if DEBUG:
                    print >> sys.stderr, "LibtorrentDownloadImpl: /etc/mimetypes+ said MIME type is", mimetype, file
            except:
                print_exc()

        # if auto detect fails
        if mimetype is None:
            if ext == '.avi':
                # Arno, 2010-01-08: Hmmm... video/avi is not official registered at IANA
                mimetype = 'video/avi'
            elif ext == '.mpegts' or ext == '.ts':
                mimetype = 'video/mp2t'
            elif ext == '.mkv':
                mimetype = 'video/x-matroska'
            elif ext in ('.ogg', '.ogv'):
                mimetype = 'video/ogg'
            elif ext in ('.oga'):
                mimetype = 'audio/ogg'
            elif ext == '.webm':
                mimetype = 'video/webm'
            else:
                mimetype = 'video/mpeg'
        return mimetype
        
        
class LibtorrentStatisticsResponse:
    
    def __init__(self, numTotSeeds, numTotPeers, numseeds, numleech, have, upTotal, downTotal):
        self.numTotSeeds = numTotSeeds
        self.numTotPeers = numTotPeers        
        self.numSeeds = numseeds
        self.numPeers = numleech
        self.have = have
        self.upTotal = upTotal
        self.downTotal = downTotal
        self.numConCandidates = 0
        self.numConInitiated = 0
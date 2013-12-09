# Written by Arno Bakker
# see LICENSE.txt for license information
#
# TODO:
# - set rate limits
#     * Check if current policy of limiting hint_out_size is sane.
#         - test case: start unlimited, wait 10 s, then set to 512 K. In one
#           test speed dropped to few bytes/s then rose again to 512 K.
#     * upload rate limit
#     * test if you get 512K for each swarm when you download two in parallel
#       in one swift proc.
#
# - HASHCHECKING
#     * get progress from swift

#     * Current cmdgw impl will open and thus hashcheck on main thread, halting
#       all network traffic, etc. in all other swarms. BitTornado interleaves
#       on netw thread.
#           - Run cmdgw on separate thread(s)?
#
# - STATS
#     *  store 2 consecutive more info dicts and calc speeds, and convert
#        those to DownloadState.get_peerlist() format.
#
# - BUGS
#     * Try to recv ICMP port unreach on Mac such that we can clean up Channel
#       (Linux done)
#

import sys
import copy

from traceback import print_exc, print_stack
from threading import RLock, currentThread
from Tribler.Core import NoDispersyRLock

from Tribler.Core.simpledefs import *
from Tribler.Core.DownloadState import *
from Tribler.Core.DownloadConfig import get_default_dest_dir
from Tribler.Core.APIImplementation.DownloadRuntimeConfig import DownloadRuntimeConfig
import shutil
from Tribler.Main.globals import DownloadStartupConfig

# ARNOSMPTODO: MODIFY WITH cmdgw.cpp::CMDGW_PREBUFFER_BYTES_AS_LAYER
# Send PLAY after receiving 2^layer * 1024 bytes
CMDGW_PREBUFFER_BYTES = (2 ** 8) * 1024
SWIFT_ALIVE_CHECK_INTERVAL = 60.0


DEBUG = False


class SwiftDownloadImpl(DownloadRuntimeConfig):

    """ Download subclass that represents a swift download.
    The actual swift download takes places in a SwiftProcess.
    """

    def __init__(self, session, sdef):
        self.dllock = NoDispersyRLock()
        self.session = session
        self.sdef = sdef
        self.old_metadir = self.session.get_swift_meta_dir()

        # just enough so error saving and get_state() works
        self.error = None
        # To be able to return the progress of a stopped torrent, how far it got.
        self.progressbeforestop = 0.0

        # SwiftProcess performing the actual download.
        self.sp = None

        # spstatus
        self.dlstatus = DLSTATUS_WAITING4HASHCHECK
        self.dynasize = 0
        self.progress = 0.0
        self.curspeeds = {DOWNLOAD: 0.0, UPLOAD: 0.0}  # bytes/s
        self.numleech = 0
        self.numseeds = 0
        self.contentbytes = {DOWNLOAD: 0, UPLOAD: 0}  # bytes

        self.done = False  # when set it means this download is being removed
        self.midict = {}
        self.time_seeding = [0, None]
        self.total_up = 0
        self.total_down = 0

        self.lm_network_vod_event_callback = None
        self.askmoreinfo = False

    #
    # Download Interface
    #
    def get_def(self):
        return self.sdef

    #
    # DownloadImpl
    #

    #
    # Creating a Download
    #
    def setup(self, dcfg=None, pstate=None, initialdlstatus=None, lm_network_engine_wrapper_created_callback=None, lm_network_vod_event_callback=None):
        """
        Create a Download object. Used internally by Session.
        @param dcfg DownloadStartupConfig or None (in which case
        a new DownloadConfig() is created and the result
        becomes the runtime config of this Download.
        """
        # Called by any thread, assume sessionlock is held
        try:
            self.dllock.acquire()  # not really needed, no other threads know of this object

            # Copy dlconfig, from default if not specified
            if dcfg is None:
                cdcfg = DownloadStartupConfig()
            else:
                cdcfg = dcfg
            self.dlconfig = cdcfg.dlconfig.copy()

            # Things that only exist at runtime
            self.dlruntimeconfig = {}
            self.dlruntimeconfig['max_desired_upload_rate'] = 0
            self.dlruntimeconfig['max_desired_download_rate'] = 0

            if pstate and pstate.has_option('state', 'dlstate'):
                dlstate = pstate.get('state', 'dlstate')
                if 'time_seeding' in dlstate:
                    self.time_seeding = [dlstate['time_seeding'], None]
                if 'total_up' in dlstate:
                    self.total_up = dlstate['total_up']
                if 'total_down' in dlstate:
                    self.total_down = dlstate['total_down']

            if DEBUG:
                print >> sys.stderr, "SwiftDownloadImpl: setup: initialdlstatus", repr(self.sdef.get_roothash_as_hex()), initialdlstatus

            # Note: initialdlstatus now only works for STOPPED
            if initialdlstatus != DLSTATUS_STOPPED:
                self.create_engine_wrapper(lm_network_engine_wrapper_created_callback, pstate, lm_network_vod_event_callback)

            self.dllock.release()
        except Exception as e:
            print_exc()
            self.set_error(e)
            self.dllock.release()

    def create_engine_wrapper(self, lm_network_engine_wrapper_created_callback, pstate, lm_network_vod_event_callback, initialdlstatus=None):
        network_create_engine_wrapper_lambda = lambda: self.network_create_engine_wrapper(lm_network_engine_wrapper_created_callback, pstate, lm_network_vod_event_callback, initialdlstatus)
        self.session.lm.rawserver.add_task(network_create_engine_wrapper_lambda)

    def network_create_engine_wrapper(self, lm_network_engine_wrapper_created_callback, pstate, lm_network_vod_event_callback, initialdlstatus=None):
        """ Called by any thread, assume dllock already acquired """
        if DEBUG:
            print >> sys.stderr, "SwiftDownloadImpl: create_engine_wrapper()"

        self.set_config_callback(self.dlconfig_changed_callback)

        if self.get_mode() == DLMODE_VOD:
            self.lm_network_vod_event_callback = lm_network_vod_event_callback

        move_files = (not self.dlconfig.has_option('downloadconfig', 'swiftmetadir')) and not os.path.isdir(self.get_dest_dir())

        metadir = self.get_swift_meta_dir()
        if not metadir:
            metadir = self.session.get_swift_meta_dir()
            self.set_swift_meta_dir(metadir)

        if not os.path.exists(metadir):
            os.makedirs(metadir)

        if move_files:
            # We must be dealing with a checkpoint from a previous release (<6.1.0). Move the swift metadata to the right directory.
            is_multifile = self.get_dest_dir().endswith("." + self.get_def().get_roothash_as_hex())
            path_old = self.get_dest_dir()
            path_new = os.path.join(metadir, self.get_def().get_roothash_as_hex() if is_multifile else os.path.split(self.get_dest_dir())[1])
            try:
                if is_multifile:
                    shutil.move(path_old, path_new + '.mfspec')
                    self.set_dest_dir(os.path.split(self.get_dest_dir())[0])
                shutil.move(path_old + '.mhash', path_new + '.mhash')
                shutil.move(path_old + '.mbinmap', path_new + '.mbinmap')
            except:
                print_exc()

        # Synchronous: starts process if needed
        self.sp = self.session.lm.spm.get_or_create_sp(self.session.get_swift_working_dir(), self.session.get_torrent_collecting_dir(), self.get_swift_listen_port(), self.get_swift_httpgw_listen_port(), self.get_swift_cmdgw_listen_port())
        if self.sp:
            self.sp.start_download(self)

            self.session.lm.rawserver.add_task(self.network_check_swift_alive, SWIFT_ALIVE_CHECK_INTERVAL)

        # Arno: if used, make sure to switch to network thread first!
        # if lm_network_engine_wrapper_created_callback is not None:
        #    sp = self.sp
        #    exc = self.error
        #    lm_network_engine_wrapper_created_callback(self,sp,exc,pstate)

    #
    # SwiftProcess callbacks
    #
    def i2ithread_info_callback(self, dlstatus, progress, dynasize, dlspeed, ulspeed, numleech, numseeds, contentdl, contentul):
        self.dllock.acquire()
        try:
            if dlstatus == DLSTATUS_SEEDING and self.dlstatus != dlstatus:
                # started seeding
                self.time_seeding[0] = self.get_seeding_time()
                self.time_seeding[1] = time.time()
            elif dlstatus != DLSTATUS_SEEDING and self.dlstatus != dlstatus:
                # stopped seeding
                self.time_seeding[0] = self.get_seeding_time()
                self.time_seeding[1] = None

            self.dlstatus = dlstatus
            self.dynasize = dynasize
            # TODO: Temporary fix for very high progress even though nothing has been downloaded yet.
            self.progress = progress if progress <= 1.0 else 0.0
            self.curspeeds[DOWNLOAD] = dlspeed
            self.curspeeds[UPLOAD] = ulspeed
            self.numleech = numleech
            self.numseeds = numseeds
            self.contentbytes = {DOWNLOAD: contentdl, UPLOAD: contentul}
        finally:
            self.dllock.release()

    def i2ithread_vod_event_callback(self, event, httpurl):
        if DEBUG:
            print >> sys.stderr, "SwiftDownloadImpl: i2ithread_vod_event_callback: ENTER", event, httpurl, "mode", self.get_mode()

        self.dllock.acquire()
        try:
            if event == VODEVENT_START:

                if self.get_mode() != DLMODE_VOD:
                    return

                # Fix firefox idiosyncrasies
                duration = self.sdef.get_duration()
                if duration is not None:
                    httpurl += '@' + duration

                vod_usercallback_wrapper = lambda event, params: self.session.uch.perform_vod_usercallback(self, self.get_video_event_callback(), event, params)
                videoinfo = {}
                videoinfo['usercallback'] = vod_usercallback_wrapper

                # ARNOSMPTODO: if complete, return file directly

                # Allow direct connection of video renderer with swift HTTP server
                # via new "url" param.
                #

                if DEBUG:
                    print >> sys.stderr, "SwiftDownloadImpl: i2ithread_vod_event_callback", event, httpurl

                # Arno: No threading violation, lm_network_* is safe at the moment
                self.lm_network_vod_event_callback(videoinfo, VODEVENT_START, {
                    "complete": False,
                    "filename": None,
                    "mimetype": 'application/octet-stream', # ARNOSMPTODO
                    "stream": None,
                    "length": self.get_dynasize(),
                    "bitrate": None, # ARNOSMPTODO
                    "url": httpurl,
                })
        finally:
            self.dllock.release()

    def i2ithread_moreinfo_callback(self, midict):
        self.dllock.acquire()
        try:
            # print >>sys.stderr,"SwiftDownloadImpl: Got moreinfo",midict.keys()
            self.midict = midict
        finally:
            self.dllock.release()

    #
    # Retrieving DownloadState
    #
    def get_status(self):
        """ Returns the status of the download.
        @return DLSTATUS_* """
        self.dllock.acquire()
        try:
            return self.dlstatus
        finally:
            self.dllock.release()

    def get_dynasize(self):
        """ Returns the size of the swift content. Note this may vary
        (generally ~1KiB because of dynamic size determination by the
        swift protocol
        @return long
        """
        self.dllock.acquire()
        try:
            return self.dynasize
        finally:
            self.dllock.release()

    def get_progress(self):
        """ Return fraction of content downloaded.
        @return float 0..1
        """
        self.dllock.acquire()
        try:
            return self.progress
        finally:
            self.dllock.release()

    def get_current_speed(self, dir):
        """ Return last reported speed in KB/s
        @return float
        """
        self.dllock.acquire()
        try:
            return self.curspeeds[dir] / 1024.0
        finally:
            self.dllock.release()

    def get_moreinfo_stats(self, dir):
        """ Return last reported more info dict
        @return dict
        """
        self.dllock.acquire()
        try:
            return self.midict
        finally:
            self.dllock.release()

    def get_seeding_time(self):
        return self.time_seeding[0] + (time.time() - self.time_seeding[1] if self.time_seeding[1] != None else 0)

    def get_total_up(self):
        return self.total_up + self.contentbytes[UPLOAD]

    def get_total_down(self):
        return self.total_down + self.contentbytes[DOWNLOAD]

    def get_seeding_statistics(self):
        seeding_stats = {}
        seeding_stats['total_up'] = self.get_total_up()
        seeding_stats['total_down'] = self.get_total_down()
        seeding_stats['time_seeding'] = self.get_seeding_time()
        return seeding_stats

    def network_get_stats(self, getpeerlist):
        """
        @return (status,stats,logmsgs,coopdl_helpers,coopdl_coordinator)
        """
        # dllock held
        # ARNOSMPTODO: Have a status for when swift is hashchecking the file on disk

        if self.sp is None:
            status = DLSTATUS_STOPPED
        else:
            status = self.dlstatus

        stats = {}
        stats['down'] = self.curspeeds[DOWNLOAD]
        stats['up'] = self.curspeeds[UPLOAD]
        stats['frac'] = self.progress
        stats['stats'] = self.network_create_statistics_reponse()
        stats['time'] = self.network_calc_eta()
        stats['vod_prebuf_frac'] = self.network_calc_prebuf_frac()
        stats['vod'] = True
        # ARNOSMPTODO: no hard check for suff bandwidth, unlike BT1Download
        stats['vod_playable'] = self.progress == 1.0 or (self.network_calc_prebuf_frac() == 1.0 and self.curspeeds[DOWNLOAD] > 0.0)
        stats['vod_playable_after'] = self.network_calc_prebuf_eta()
        stats['vod_stats'] = self.network_get_vod_stats()
        stats['spew'] = self.network_create_spew_from_peerlist()

        seeding_stats = self.get_seeding_statistics()

        logmsgs = []
        return (status, stats, seeding_stats, logmsgs)

    def network_create_statistics_reponse(self):
        return SwiftStatisticsResponse(self.numleech, self.numseeds, self.midict)

    def network_calc_eta(self):
        bytestogof = (1.0 - self.progress) * float(self.dynasize)
        dlspeed = max(0.000001, self.curspeeds[DOWNLOAD])
        return bytestogof / dlspeed

    def network_calc_prebuf_frac(self):
        gotbytesf = self.progress * float(self.dynasize)
        prebuff = float(CMDGW_PREBUFFER_BYTES)
        return min(1.0, gotbytesf / prebuff)

    def network_calc_prebuf_eta(self):
        bytestogof = (1.0 - self.network_calc_prebuf_frac()) * float(CMDGW_PREBUFFER_BYTES)
        dlspeed = max(0.000001, self.curspeeds[DOWNLOAD])
        return bytestogof / dlspeed

    def network_get_vod_stats(self):
        # More would have to be sent from swift process to set these correctly
        d = {}
        d['played'] = None
        d['late'] = None
        d['dropped'] = None
        d['stall'] = None
        d['pos'] = None
        d['prebuf'] = None
        d['firstpiece'] = 0
        d['npieces'] = ((self.dynasize + 1023) / 1024)
        return d

    def network_create_spew_from_peerlist(self):
        if not 'channels' in self.midict:
            return []

        plist = []
        channels = self.midict['channels']
        for channel in channels:
            d = {}
            d['ip'] = channel['ip']
            d['port'] = channel['port']
            d['utotal'] = channel['bytes_up'] / 1024.0
            d['dtotal'] = channel['bytes_down'] / 1024.0
            plist.append(d)

        return plist

    #
    # Retrieving DownloadState
    #
    def set_state_callback(self, usercallback, getpeerlist=False, delay=0.0):
        """ Called by any thread """
        self.dllock.acquire()
        try:
            network_get_state_lambda = lambda: self.network_get_state(usercallback, getpeerlist)
            # First time on general rawserver
            self.session.lm.rawserver.add_task(network_get_state_lambda, delay)
        finally:
            self.dllock.release()

    def network_get_state(self, usercallback, getpeerlist, sessioncalling=False):
        """ Called by network thread """
        self.dllock.acquire()
        try:
            if self.sp is None:
                if DEBUG:
                    print >> sys.stderr, "SwiftDownloadImpl: network_get_state: Download not running"
                ds = DownloadState(self, DLSTATUS_STOPPED, self.error, self.progressbeforestop, seeding_stats=self.get_seeding_statistics())
            else:
                (status, stats, seeding_stats, logmsgs) = self.network_get_stats(getpeerlist)
                ds = DownloadState(self, status, self.error, self.get_progress(), stats=stats, seeding_stats=seeding_stats, logmsgs=logmsgs)
                self.progressbeforestop = ds.get_progress()

            if sessioncalling:
                return ds

            # Invoke the usercallback function via a new thread.
            # After the callback is invoked, the return values will be passed to
            # the returncallback for post-callback processing.
            if not self.done:
                self.session.uch.perform_getstate_usercallback(usercallback, ds, self.sesscb_get_state_returncallback)
        finally:
            self.dllock.release()

    def sesscb_get_state_returncallback(self, usercallback, when, newgetpeerlist):
        """ Called by SessionCallbackThread """
        self.dllock.acquire()
        try:
            if when > 0.0 and not self.done:
                # Schedule next invocation, either on general or DL specific
                # Note this continues when dl is stopped.
                network_get_state_lambda = lambda: self.network_get_state(usercallback, newgetpeerlist)
                self.session.lm.rawserver.add_task(network_get_state_lambda, when)
        finally:
            self.dllock.release()

    #
    # Download stop/resume
    #
    def stop(self):
        """ Called by any thread """
        self.stop_remove(False, removestate=False, removecontent=False)

    def stop_remove(self, removedl, removestate=False, removecontent=False):
        """ Called by any thread. Called on Session.remove_download() """
        # Arno, 2013-01-29: This download is being removed, not just stopped.
        self.done = removedl
        self.network_stop(removestate=removestate, removecontent=removecontent)

    def network_stop(self, removestate, removecontent):
        """ Called by network thread, but safe for any """
        self.dllock.acquire()
        try:
            if DEBUG:
                print >> sys.stderr, "SwiftDownloadImpl: network_stop", repr(self.sdef.get_name())

            pstate = self.network_get_persistent_state()
            if self.sp is not None:
                self.sp.remove_download(self, removestate, removecontent)
                self.session.lm.spm.release_sp(self.sp)
                self.sp = None

            self.time_seeding = [self.get_seeding_time(), None]

            # Offload the removal of the dlcheckpoint to another thread
            if removestate:
                # To remove:
                # 1. Core checkpoint (if any)
                # 2. .mhash file
                # 3. content (if so desired)

                # content and .mhash file is removed by swift engine if requested
                roothash = self.sdef.get_roothash()
                self.session.uch.perform_removestate_callback(roothash, None, False)

            return (self.sdef.get_roothash(), pstate)
        finally:
            self.dllock.release()

    def get_content_dest(self):
        """ Returns the file to which the downloaded content is saved. """
        return os.path.join(self.get_dest_dir(), self.sdef.get_roothash_as_hex())

    def restart(self, initialdlstatus=None):
        """ Restart the Download """
        # Called by any thread
        if DEBUG:
            print >> sys.stderr, "SwiftDownloadImpl: restart:", repr(self.sdef.get_name())
        self.dllock.acquire()
        try:
            if self.sp is None:
                self.error = None  # assume fatal error is reproducible
                self.create_engine_wrapper(self.session.lm.network_engine_wrapper_created_callback, None, self.session.lm.network_vod_event_callback, initialdlstatus=initialdlstatus)

            # No exception if already started, for convenience
        finally:
            self.dllock.release()

    #
    # Config parameters that only exists at runtime
    #
    def set_max_desired_speed(self, direct, speed):
        if DEBUG:
            print >> sys.stderr, "Download: set_max_desired_speed", direct, speed
        # if speed < 10:
        #    print_stack()

        self.dllock.acquire()
        if direct == UPLOAD:
            self.dlruntimeconfig['max_desired_upload_rate'] = speed
        else:
            self.dlruntimeconfig['max_desired_download_rate'] = speed
        self.dllock.release()

    def get_max_desired_speed(self, direct):
        self.dllock.acquire()
        try:
            if direct == UPLOAD:
                return self.dlruntimeconfig['max_desired_upload_rate']
            else:
                return self.dlruntimeconfig['max_desired_download_rate']
        finally:
            self.dllock.release()

    def get_dest_files(self, exts=None):
        """
        Returns (None,destfilename)
        """
        if exts is not None:
            raise OperationNotEnabledByConfigurationException()

        f2dlist = []
        diskfn = self.get_content_dest()
        f2dtuple = (None, diskfn)
        f2dlist.append(f2dtuple)
        return f2dlist

    #
    # Persistence
    #
    def checkpoint(self):
        """ Called by any thread """
        # Arno, 2012-05-15. Currently this is safe to call from any thread.
        # Need this for torrent collecting via swift.
        self.network_checkpoint()

    def network_checkpoint(self):
        """ Called by network thread """
        self.dllock.acquire()
        try:
            pstate = self.network_get_persistent_state()
            if self.sp is not None:
                self.sp.checkpoint_download(self)
            return (self.sdef.get_roothash(), pstate)
        finally:
            self.dllock.release()

    def network_get_persistent_state(self):
        """ Assume dllock already held """

        pstate = self.dlconfig.copy()

        pstate.set('downloadconfig', 'name', self.sdef.get_name())

        # Reset unpicklable params
        pstate.set('downloadconfig', 'vod_usercallback', None)
        pstate.set('downloadconfig', 'mode', DLMODE_NORMAL)

        # Reset default metadatadir
        if self.get_swift_meta_dir() == self.old_metadir:
            pstate.set('downloadconfig', 'swiftmetadir', None)

        # Add state stuff
        if not pstate.has_section('state'):
            pstate.add_section('state')
        pstate.set('state', 'version', PERSISTENTSTATE_CURRENTVERSION)
        pstate.set('state', 'metainfo', self.sdef.get_url_with_meta())  # assumed immutable

        ds = self.network_get_state(None, False, sessioncalling=True)
        dlstate = {'status': ds.get_status(), 'progress': ds.get_progress(), 'swarmcache': None}
        dlstate.update(ds.get_seeding_statistics())
        pstate.set('state', 'dlstate', dlstate)

        if DEBUG:
            print >> sys.stderr, "SwiftDownloadImpl: netw_get_pers_state: status", dlstatus_strings[ds.get_status()], "progress", ds.get_progress()

        # Swift stores own state in .mhash and .mbinmap file
        pstate.set('state', 'engineresumedata', None)
        return pstate

    #
    # Coop download
    #
    def get_coopdl_role_object(self, role):
        """ Called by network thread """
        return None

    def recontact_tracker(self):
        """ Called by any thread """
        pass

    #
    # MOREINFO
    #
    def set_moreinfo_stats(self, enable):
        """ Called by any thread """

        # Arno, 2012-07-31: slight risk if process killed in between
        if self.askmoreinfo == enable:
            return
        self.askmoreinfo = enable

        if self.sp is not None:
            self.sp.set_moreinfo_stats(self, enable)

    #
    # External addresses
    #
    def add_peer(self, addr):
        """ Add a peer address from 3rd source (not tracker, not DHT) to this
        Download.
        @param (hostname_ip,port) tuple
        """
        if self.sp is not None:
            self.sp.add_peer(self, addr)

    #
    # Internal methods
    #
    def set_error(self, e):
        self.dllock.acquire()
        self.error = e
        self.dllock.release()

    #
    # Auto restart after swift crash
    #
    def network_check_swift_alive(self):
        self.dllock.acquire()
        try:
            if self.sp is not None and not self.done:
                if not self.sp.is_alive():
                    print >> sys.stderr, "SwiftDownloadImpl: network_check_swift_alive: Restarting", repr(self.sdef.get_name())
                    self.sp = None
                    self.restart()
        except:
            print_exc()
        finally:
            self.dllock.release()

        if not self.done:
            self.session.lm.rawserver.add_task(self.network_check_swift_alive, SWIFT_ALIVE_CHECK_INTERVAL)

    def dlconfig_changed_callback(self, section, name, new_value, old_value):
        if section == 'downloadconfig' and name in ['max_upload_rate', 'max_download_rate']:
            if self.sp is not None:
                direct = UPLOAD if name == 'max_upload_rate' else DOWNLOAD
                if self.get_max_speed(direct) != new_value:
                    self.sp.set_max_speed(self, direct, new_value)
        elif section == 'downloadconfig' and name in ['selected_files', 'mode', 'correctedfilename', 'saveas', 'vod_usercallback', 'super_seeder']:
            return False
        return True


class SwiftStatisticsResponse:

    def __init__(self, numleech, numseeds, midict):
        # More would have to be sent from swift process to set these correctly
        self.numConCandidates = 0
        self.numConInitiated = 0
        self.have = None
        self.numSeeds = numseeds
        self.numPeers = numleech

        # Arno, 2012-05-23: At Niels' request
        self.upTotal = 0
        self.downTotal = 0
        try:
            self.upTotal = midict['bytes_up']
            self.downTotal = midict['bytes_down']
        except:
            pass

        try:
            self.rawUpTotal = midict['raw_bytes_up']
            self.rawDownTotal = midict['raw_bytes_down']
        except KeyError:
            self.rawUpTotal = 0
            self.rawDownTotal = 0

# coding: utf-8
# Written by Wendo Sabée
# Manages local downloads

import threading
import binascii
import os

# Setup logger
import logging
_logger = logging.getLogger(__name__)

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import DOWNLOAD, UPLOAD
from Tribler.Main.globals import DefaultDownloadStartupConfig

# Tribler defs
from Tribler.Core.simpledefs import NTFY_TORRENTS, NTFY_MYPREFERENCES, \
    NTFY_VOTECAST, NTFY_CHANNELCAST, NTFY_METADATA, \
    DLSTATUS_METADATA, DLSTATUS_WAITING4HASHCHECK, dlstatus_strings

# DB Tuples
from Tribler.Main.Utility.GuiDBTuples import Torrent, ChannelTorrent, RemoteChannelTorrent, RemoteTorrent
from Tribler.Core.TorrentDef import TorrentDefNoMetainfo


# TODO: not hardcoded please
DOWNLOAD_UPDATE_DELAY = 2.0
DOWNLOAD_CHECKPOINT_INTERVAL = 300.0
DOWNLOAD_UPDATE_CACHE = 300.0
RATELIMIT_UPDATE_DELAY = 15.0

from BaseManager import BaseManager

class DownloadManager(BaseManager):
    _dllock = threading.Lock()
    _dispersy = None
    _remote_lock = None

    _torrent_db = None
    _channelcast_db = None
    _votecast_db = None

    _downloads = {}

    def init(self):
        """
        Load database handles and Dispersy.
        :return: Nothing.
        """
        if not self._connected:
            self._connected = True
            self._remote_lock = threading.Lock()

            self._torrent_db = self._session.open_dbhandler(NTFY_TORRENTS)
            self._channelcast_db = self._session.open_dbhandler(NTFY_CHANNELCAST)
            self._votecast_db = self._session.open_dbhandler(NTFY_VOTECAST)

            self._dispersy = self._session.lm.dispersy

            # Schedule load checkpoints
            threading.Timer(1.0, self._load_checkpoints, ()).start()

            # Schedule download checkpoints
            threading.Timer(DOWNLOAD_CHECKPOINT_INTERVAL, self._run_session_checkpoint, ()).start()

        else:
            raise RuntimeError('DownloadManager already connected')

    def _run_session_checkpoint(self):
        """
        Periodically run function that checkpoints the current downloads. This is done so that after a crash, no full
        hash recheck is needed.
        :return: Nothing.
        """
        _logger.info("Running session checkpoint..")
        self._session.checkpoint()

        # Schedule next checkpoint
        threading.Timer(DOWNLOAD_CHECKPOINT_INTERVAL, self._run_session_checkpoint, ()).start()

    def set_max_download(self, maxspeed):
        """
        Set the global maximum download speed.
        :param maxspeed: Maximum download speed in KiB/s, 0 for unlimited
        :return: Boolean indicating success.
        """
        self._session.set_max_download_speed(maxspeed)

    def set_max_upload(self, maxspeed):
        """
        Set the global maximum upload speed.
        :param maxspeed: Maximum upload speed in KiB/s, 0 for unlimited
        :return: Boolean indicating success.
        """
        self._session.set_max_upload_speed(maxspeed)

    def add_torrent(self, infohash, name):
        """
        Add a download to the download list by its infohash.
        :param infohash: The infohash of the torrent.
        :param name: The name of the torrent.
        :return: Boolean indicating success.
        """

        def add_torrent_callback():
            try:
                bin_infohash = binascii.unhexlify(infohash)

                tdef = TorrentDefNoMetainfo(bin_infohash, name)
                _logger.info("[%s] Adding torrent by magnet link" % infohash)

                defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
                dscfg = defaultDLConfig.copy()

                dl = self._session.start_download(tdef, dscfg)
                dl.set_state_callback(self._update_dl_state, delay=1)

                self._session.checkpoint()

            except Exception, e:
                _logger.error("Error adding torrent (infohash=%s,name=%s) (%s)" % (infohash, name, e.args))
                return False

            return True

        self._session.lm.rawserver.add_task(add_torrent_callback, delay=1)
        return True

    def _update_dl_state(self, ds):
        """
        DownloadState callback that updates the associated download dict.
        :param ds: DownloadState object.
        :return: Nothing.
        """

        self._dllock.acquire()
        try:
            _logger.info("Got download status callback (%s: %s; %s)" % (type(ds).__name__, ds.get_status(), ds.get_progress()))

            dldict = self._getDownloadState(ds, progress=True, vod=True)
            if dldict:
                if dldict['infohash'] in self._downloads.keys():
                    self._downloads[dldict['infohash']].update(dldict)
                    # TODO: Not supported in Tribler anymore but might be needed
                    #self._ratelimiter.add_downloadstate(ds)
                else:
                    self._downloads[dldict['infohash']] = dldict
                    # TODO: Not supported in Tribler anymore but might be needed
                    #self._ratelimiter.add_downloadstate(ds)
            else:
                _logger.warn("Error updating download state")

        finally:
            self._dllock.release()
            return DOWNLOAD_UPDATE_DELAY, False

    def remove_torrent(self, infohash, removecontent):
        """
        Remove a download from the download list by its infohash.
        :param infohash: The infohash of the torrent.
        :return: Boolean indicating success.
        """
        def remove_torrent_callback():
            try:
                _logger.info("Removing torrent with infohash %s" % infohash)
                dl = self._session.get_download(binascii.unhexlify(infohash))
                self._session.remove_download(dl, removecontent)

                if infohash in self._downloads.keys():
                    self._downloads.pop(infohash, None)

                self._session.checkpoint()

                return True

            except Exception, e:
                _logger.error("Couldn't remove torrent with infohash %s (%s)" % (infohash, e.args))
                return False

        self._session.lm.rawserver.add_task(remove_torrent_callback, delay=1)
        return True

    def get_progress(self, infohash):
        """
        Get the progress of a single torrent, by infohash.
        :param infohash: Infohash of the torrent.
        :return: Progress of a torrent or False on failure.
        """
        with self._dllock:
            if infohash in self._downloads.keys():
                return self._downloads[infohash]
            else:
                return False

    def get_progress_all(self):
        """
        Get the progress of all current torrents.
        :return: List of progress torrents.
        """
        with self._dllock:
            return self._downloads.values()

    def _download_update_cache(self):
        """
        Periodically called function that checks if there are any downloads that are not yet tracked by the
        DownloadManager.
        :return: Nothing.
        """
        _logger.info("Downloads cache check hit..")

        with self._dllock:
            for dl in self._session.get_downloads():
                try:
                    infohash = binascii.hexlify(dl.get_def().get_infohash())
                    if not infohash in self._downloads.keys():
                        _logger.info("Added %s to download cache" % infohash)
                        dl.set_state_callback(self._update_dl_state, delay=1)
                    else:
                        _logger.info("Already in download cache: " % infohash)
                except Exception, e:
                    _logger.info("Error checking download: " % e.args)
                    pass

        threading.Timer(DOWNLOAD_UPDATE_CACHE, self._download_update_cache, ()).start()

    def _load_checkpoints(self):
        """
        Load the checkpoint for any downloads that can be resumed.
        :return: Nothing.
        """
        _logger.info("Loading download checkpoints..")

        # Niels: first remove all "swift" torrent collect checkpoints
        dir = self._session.get_downloads_pstate_dir()
        coldir = os.path.basename(os.path.abspath(self._session.get_torrent_collecting_dir()))

        filelist = os.listdir(dir)
        filelist = [os.path.join(dir, filename) for filename in filelist if filename.endswith('.state')]

        for file in filelist:
            try:
                pstate = self._session.lm.load_download_pstate(file)

                saveas = pstate.get('downloadconfig', 'saveas')
                if saveas:
                    destdir = os.path.basename(saveas)
                    if destdir == coldir or destdir == os.path.join(self._session.get_state_dir(), "anon_test"):
                        _logger.info("Removing swift checkpoint %s" % file)
                        os.remove(file)
            except:
                pass

        #from Tribler.Main.vwxGUI.UserDownloadChoice import UserDownloadChoice
        #user_download_choice = UserDownloadChoice.get_singleton()
        #initialdlstatus_dict = {}
        #for id, state in user_download_choice.get_download_states().iteritems():
        #    if state == 'stop':
        #        initialdlstatus_dict[id] = DLSTATUS_STOPPED
        try:
            self._session.load_checkpoint()
        except:
            pass

        threading.Timer(1.0, self._download_update_cache, ()).start()

    def get_full(self, infohash):
        """
        Get the full info of a single torrent, by infohash.
        :param infohash: Infohash of the torrent.
        :return: Full info of a torrent or False on failure.
        """
        return self._get_download_info(infohash, {'progress': True, 'files': True, 'network': True})

    def get_vod(self, infohash):
        """
        Get the vod status of a single torrent, by infohash.
        :param infohash: Infohash of the torrent.
        :return: Vod status of a torrent or False on failure.
        """
        return self._get_download_info(infohash, {'vod': True})

    def _get_download_info(self, infohash, args):
        """
        Get the info of a download by its infohash.
        :param infohash: The infohash of the torrent.
        :param args: Dictionary with arguments indicating which info to include.
        :return: Dictionary with information about the download.
        """
        try:
            download = self._session.get_download(binascii.unhexlify(infohash))
            return self._getDownload(download, **args)
        except:
            return False

    def start_vod(self, infohash):
        """
        Set a download to vod mode.
        :param infohash: Infohash of the torrent.
        :return: Vod uri on success, False otherwise.
        """
        try:
            download = self._session.get_download(binascii.unhexlify(infohash))

            from Tribler.Core.Video.utils import videoextdefaults

            files = download.get_def().get_files_with_length()
            files.sort(key=lambda fl: fl[1], reverse=True)

            selected_file = None
            findex = 0
            for f in files:
                try:
                    _, ext = os.path.splitext(f[0])
                    print ext
                    if ext[1:] in videoextdefaults:
                        selected_file = f[0]
                        break
                except:
                    pass
                findex += 1

            _logger.info("Selecting %s for VOD" % selected_file)

            if selected_file is None:
                #selected_file = files[0][0]
                return False

            download.set_selected_files(selected_file)

            download.set_vod_mode(True)
        except Exception, e:
            print "Start_vod error: %s" % e.args
            return False

        voduri = self.get_vod_uri(infohash, fileindex=findex)
        _logger.info("Returning VOD uri: %s" % voduri)

        return voduri

    def stop_vod(self, infohash):
        """
        Set a download to normal download mode.
        :param infohash: Infohash of the torrent.
        :return: Boolean indicating success.
        """
        try:
            download = self._session.get_download(binascii.unhexlify(infohash))
            download.set_vod_mode(False)
        except:
            return False

        return True

    def get_vod_uri(self, infohash, fileindex=0):
        """
        Returns the VOD uri for this torrent.
        :param infohash: Infohash of the torrent.
        :return: Uri that can be used to stream the torrent.
        """
        return "http://127.0.0.1:%s/%s/%s" % (self._session.get_videoplayer_port(), infohash, fileindex)

    def set_state(self, infohash):
        pass

    def _get_torrent_from_infohash(self, infohash):
        dict = self._torrent_db.getTorrent(infohash, keys=['C.torrent_id', 'infohash', 'name', 'length', 'category', 'status', 'num_seeders', 'num_leechers'])
        if dict:
            t = Torrent(dict['C.torrent_id'], dict['infohash'], dict['name'], dict['length'], dict['category'], dict['status'], dict['num_seeders'], dict['num_leechers'], None)
            t.torrent_db = self._torrent_db
            t.channelcast_db = self._channelcast_db
            # TODO: ENABLE metadata_db WHEN METADATA COMMUNITY IS ENABLED
            t.metadata_db = None  #self._metadata_db

            # prefetching channel, metadata
            _ = t.channel
            _ = t.metadata
            return t

    def _getDownload(self, torrentimpl, vod=False, progress=False, files=False, network=False):
        """
        Convert a LibTorrentDownloadImpl object to a dictionary.
        :param torrentimpl: A LibTorrentDownloadImpl object.
        :param vod: Include info about vod.
        :param progress: Include info about download progress.
        :param files: Include info about files.
        :param network: Include info about network.
        :return: Dictionary with information about the download.
        """
        #progress = infoh, name, speed, eta, progress, size, seeders/leechers
        #vod = vod_eta, vod_stats
        #full = progress + {files, metadata (description, thumbnail), dest}, speed_max

        try:
            dlinfo = {'infohash': binascii.hexlify(torrentimpl.get_def().get_infohash())}

            if progress:
                dlinfo.update({'name': torrentimpl.tdef.get_name(),
                               'progress': torrentimpl.get_progress(),
                               'length': torrentimpl.get_length(),
                               'speed_up': torrentimpl.get_current_speed(UPLOAD),
                               'speed_down': torrentimpl.get_current_speed(DOWNLOAD),
                               'eta': torrentimpl.network_calc_eta(),
                               'status': torrentimpl.get_status(),
                               'status_string': dlstatus_strings[torrentimpl.get_status()],
                               # TODO: return state
                               })

            if vod:
                vod_stats = torrentimpl.network_get_vod_stats()
                dlinfo.update({'vod_eta': torrentimpl.network_calc_prebuf_eta(),
                               'vod_pieces': vod_stats['npieces'],
                               'vod_played': vod_stats['playes'],
                               'vod_firstpiece': vod_stats['firstpiece'],
                               'vod_pos': vod_stats['pos'],
                               'vod_late': vod_stats['late'],
                               'vod_stall': vod_stats['stall'],
                               'vod_dropped': vod_stats['dropped'],
                               'vod_prebuf': vod_stats['prebuf'],
                               })

            if files:
                dlinfo.update({'destination': torrentimpl.get_content_dest(),
                               'speed_up_max': torrentimpl.get_max_desired_speed(UPLOAD),
                               'speed_down_max': torrentimpl.get_max_desired_speed(DOWNLOAD),
                               'files': torrentimpl.get_dest_files(),
                               'magnet_uri': torrentimpl.get_magnet_link(),
                               })

            if network:
                dlinfo.update({'network': torrentimpl.network_create_statistics_reponse()})

            return dlinfo
        except Exception, e:
            print "Error getting TorrentDownloadImpl: %s" % e.args
            return {}

    def _getDownloadState(self, dstate, vod=False, progress=False, files=False, network=False):
        """
        Convert a DownloadState object to a dictionary.
        :param dstate: A DownloadState object.
        :param vod: Include info about vod.
        :param progress: Include info about download progress.
        :param files: Include info about files.
        :param network: Include info about network.
        :return: Dictionary with information about the download.
        """
        #progress = infoh, name, speed, eta, progress, size, seeders/leechers
        #vod = vod_eta, vod_stats
        #full = progress + {files, metadata (description, thumbnail), dest}, speed_max

        try:
            dlinfo = {'infohash': binascii.hexlify(dstate.get_download().get_def().get_infohash())}

            if progress:
                dlinfo.update({'name': dstate.get_download().get_def().get_name(),
                               'progress': dstate.get_progress(),
                               'length': dstate.get_length(),
                               'speed_up': dstate.get_current_speed(UPLOAD),
                               'speed_down': dstate.get_current_speed(DOWNLOAD),
                               'availability': dstate.get_availability(),
                               'eta': dstate.get_eta(),
                               'status': dstate.get_status(),
                               'status_string': dlstatus_strings[dstate.get_status()],
                               })
            if vod:
                dlinfo.update({'vod_eta': float(2 ** 31) if dstate.stats is None else dstate.stats['vod_playable_after'], #dstate.get_vod_playable_after()
                               'vod_prebuffer_progress': dstate.get_vod_prebuffering_progress(),
                               'vod_consec_prebuffer_progress': dstate.get_vod_prebuffering_progress_consec(),
                               'vod': dstate.is_vod(),
                               'vod_playable': False if dstate.stats is None else dstate.stats['vod_playable'], #dstate.get_vod_playable()
                               })

            return dlinfo
        except Exception, e:
            print "Error getting downloadstate: %s" % e.args
            return {}

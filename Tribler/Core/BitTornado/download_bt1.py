# Written by Bram Cohen and Pawel Garbacki, George Milescu
# see LICENSE.txt for license information

import sys
import os
import time
from zurllib import urlopen
from urlparse import urlparse
from BT1.btformats import check_message
from BT1.Choker import Choker
from BT1.Storage import Storage
from BT1.StorageWrapper import StorageWrapper
from BT1.FileSelector import FileSelector
from BT1.Uploader import Upload
from BT1.Downloader import Downloader
from BT1.GetRightHTTPDownloader import GetRightHTTPDownloader
from BT1.HoffmanHTTPDownloader import HoffmanHTTPDownloader
from BT1.Connecter import Connecter
from RateLimiter import RateLimiter
from BT1.Encrypter import Encoder
from RawServer import RawServer, autodetect_socket_style
from BT1.Rerequester import Rerequester
from BT1.DownloaderFeedback import DownloaderFeedback
from RateMeasure import RateMeasure
from CurrentRateMeasure import Measure
from BT1.PiecePicker import PiecePicker
from BT1.Statistics import Statistics
from bencode import bencode, bdecode
from Tribler.Core.Utilities.Crypto import sha
from os import path, makedirs, listdir
from parseargs import parseargs, formatDefinitions, defaultargs
from socket import error as socketerror
from random import seed
from threading import Event
from clock import clock
import re
from traceback import print_exc,print_stack

from Tribler.Core.simpledefs import *
from Tribler.Core.Merkle.merkle import create_fake_hashes
from Tribler.Core.Utilities.unicode import bin2unicode, dunno2unicode
from Tribler.Core.Video.PiecePickerStreaming import PiecePickerVOD
# Ric: added svc
from Tribler.Core.Video.PiecePickerSVC import PiecePickerSVC
from Tribler.Core.Video.SVCTransporter import SVCTransporter
from Tribler.Core.Video.VideoOnDemand import MovieOnDemandTransporter
from Tribler.Core.APIImplementation.maketorrent import torrentfilerec2savefilename,savefilenames2finaldest

#ProxyService_
#
from Tribler.Core.ProxyService.Coordinator import Coordinator
from Tribler.Core.ProxyService.Helper import Helper
from Tribler.Core.ProxyService.RatePredictor import ExpSmoothRatePredictor
import sys
from traceback import print_exc,print_stack
#
#_ProxyService

try:
    True
except:
    True = 1
    False = 0

DEBUG = False

class BT1Download:    
    def __init__(self, statusfunc, finfunc, errorfunc, excfunc, logerrorfunc, doneflag, 
                 config, response, infohash, id, rawserver, get_extip_func, port,
                 videoanalyserpath):
        self.statusfunc = statusfunc
        self.finfunc = finfunc
        self.errorfunc = errorfunc
        self.excfunc = excfunc
        self.logerrorfunc = logerrorfunc
        self.doneflag = doneflag
        self.config = config
        self.response = response
        self.infohash = infohash
        self.myid = id
        self.rawserver = rawserver
        self.get_extip_func = get_extip_func
        self.port = port
        self.info = self.response['info']
        
        # Merkle: Create list of fake hashes. This will be filled if we're an
        # initial seeder
        if self.info.has_key('root hash') or self.info.has_key('live'):
            self.pieces = create_fake_hashes(self.info)
        else:
            self.pieces = [self.info['pieces'][x:x+20]
                           for x in xrange(0, len(self.info['pieces']), 20)]
        self.len_pieces = len(self.pieces)
        self.piecesize = self.info['piece length']
        self.unpauseflag = Event()
        self.unpauseflag.set()
        self.downloader = None
        self.storagewrapper = None
        self.fileselector = None
        self.super_seeding_active = False
        self.filedatflag = Event()
        self.spewflag = Event()
        self.superseedflag = Event()
        self.whenpaused = None
        self.finflag = Event()
        self.rerequest = None
        self.tcp_ack_fudge = config['tcp_ack_fudge']
        # Ric added SVC case
        self.svc_video = (config['mode'] == DLMODE_SVC)
        self.play_video = (config['mode'] == DLMODE_VOD)
        self.am_video_source = bool(config['video_source'])
        # i.e. if VOD then G2G, if live then BT 
        self.use_g2g = self.play_video and not ('live' in response['info'])
        self.videoinfo = None
        self.videoanalyserpath = videoanalyserpath
        self.voddownload = None
        

        self.selector_enabled = config['selector_enabled']

        self.excflag = self.rawserver.get_exception_flag()
        self.failed = False
        self.checking = False
        self.started = False

        # ProxyService_
        #
        self.helper = None
        self.coordinator = None
        self.rate_predictor = None
        #
        # _ProxyService

        # 2fastbt_
        try:
            
            # 03/01/11 boudewijn: when self.coordinator or self.helper
            # is set, a lot of data is logged.  Unfortunately either
            # is set for -any- download, not only the 2010 test
            # torrent.  This resulted in huge amounts of log, memory
            # usage, and even crashes.
            #
            # if self.config['download_help']:
            #     if DEBUG:
            #         print >>sys.stderr,"BT1Download: coopdl_role is",self.config['coopdl_role'],`self.config['coopdl_coordinator_permid']`
                
            #     if self.config['coopdl_role'] == COOPDL_ROLE_COORDINATOR:
            #         from Tribler.Core.ProxyService.Coordinator import Coordinator
                    
            #         self.coordinator = Coordinator(self.infohash, self.len_pieces)
            #     #if self.config['coopdl_role'] == COOPDL_ROLE_COORDINATOR or self.config['coopdl_role'] == COOPDL_ROLE_HELPER:
            #     # Arno, 2008-05-20: removed Helper when coordinator, shouldn't need it.
            #     # Reason to remove it is because it messes up PiecePicking: when a 
            #     # helper, it calls _next() again after it returned None, probably
            #     # to provoke a RESERVE_PIECE request to the coordinator.
            #     # This change passes test_dlhelp.py
            #     #
            #     if self.config['coopdl_role'] == COOPDL_ROLE_HELPER:
            #         from Tribler.Core.ProxyService.Helper import Helper
                    
            #         self.helper = Helper(self.infohash, self.len_pieces, self.config['coopdl_coordinator_permid'], coordinator = self.coordinator)
            #         self.config['coopdl_role'] = ''
            #         self.config['coopdl_coordinator_permid'] = ''


            if self.am_video_source:
                from Tribler.Core.Video.VideoSource import PiecePickerSource

                self.picker = PiecePickerSource(self.len_pieces, config['rarest_first_cutoff'], 
                             config['rarest_first_priority_cutoff'], helper = self.helper, coordinator = self.coordinator)
            elif self.play_video:
                # Jan-David: Start video-on-demand service
                self.picker = PiecePickerVOD(self.len_pieces, config['rarest_first_cutoff'], 
                             config['rarest_first_priority_cutoff'], helper = self.helper, coordinator = self.coordinator, piecesize=self.piecesize)
            elif self.svc_video:
                # Ric: Start SVC VoD service TODO
                self.picker = PiecePickerSVC(self.len_pieces, config['rarest_first_cutoff'], 
                             config['rarest_first_priority_cutoff'], helper = self.helper, coordinator = self.coordinator, piecesize=self.piecesize)
            else:
                self.picker = PiecePicker(self.len_pieces, config['rarest_first_cutoff'], 
                             config['rarest_first_priority_cutoff'], helper = self.helper, coordinator = self.coordinator)
            
        except:
            print_exc()
            print >> sys.stderr,"BT1Download: EXCEPTION in __init__ :'" + str(sys.exc_info()) + "' '"
# _2fastbt

        self.choker = Choker(config, rawserver.add_task, 
                             self.picker, self.finflag.isSet)

        #print >>sys.stderr,"download_bt1.BT1Download: play_video is",self.play_video

    def set_videoinfo(self,videoinfo,videostatus):
        self.videoinfo = videoinfo
        self.videostatus = videostatus

        # Ric: added svc case
        if self.play_video or self.svc_video:
            self.picker.set_videostatus( self.videostatus )

    def checkSaveLocation(self, loc):
        if self.info.has_key('length'):
            return path.exists(loc)
        for x in self.info['files']:
            if path.exists(path.join(loc, x['path'][0])):
                return True
        return False
                

    def saveAs(self, filefunc, pathfunc = None):
        """ Now throws Exceptions """
        def make(f, forcedir = False):
            if not forcedir:
                f = path.split(f)[0]
            if f != '' and not path.exists(f):
                makedirs(f)

        if self.info.has_key('length'):
            file_length = self.info['length']
            file = filefunc(self.info['name'], file_length, 
                            self.config['saveas'], False)
            # filefunc throws exc if filename gives IOError

            make(file)
            files = [(file, file_length)]
        else:
            file_length = 0L
            for x in self.info['files']:
                file_length += x['length']
            file = filefunc(self.info['name'], file_length, 
                            self.config['saveas'], True)
            # filefunc throws exc if filename gives IOError

            # if this path exists, and no files from the info dict exist, we assume it's a new download and 
            # the user wants to create a new directory with the default name
            existing = 0
            if path.exists(file):
                if not path.isdir(file):
                    raise IOError(file + 'is not a dir')
                if listdir(file):  # if it's not empty
                    for x in self.info['files']:
                        savepath1 = torrentfilerec2savefilename(x,1)
                        if path.exists(path.join(file, savepath1)):
                            existing = 1
                    if not existing:
                        try:
                            file = path.join(file, self.info['name'])
                        except UnicodeDecodeError:
                            file = path.join(file, dunno2unicode(self.info['name']))
                        if path.exists(file) and not path.isdir(file):
                            if file.endswith('.torrent') or file.endswith(TRIBLER_TORRENT_EXT):
                                (prefix,ext) = os.path.splitext(file)
                                file = prefix
                            if path.exists(file) and not path.isdir(file):
                                raise IOError("Can't create dir - " + self.info['name'])
            make(file, True)

            # alert the UI to any possible change in path
            if pathfunc != None:
                pathfunc(file)

            files = []
            for x in self.info['files']:
                savepath = torrentfilerec2savefilename(x)
                full = savefilenames2finaldest(file,savepath)
                # Arno: TODO: this sometimes gives too long filenames for 
                # Windows. When fixing this take into account that 
                # Download.get_dest_files() should still produce the same
                # filenames as your modifications here.
                files.append((full, x['length']))
                make(full)

        self.filename = file
        self.files = files
        self.datalength = file_length
        
        if DEBUG:
            print >>sys.stderr,"BT1Download: saveas returning ",`file`,"self.files is",`self.files`
                
        return file

    def getFilename(self):
        return self.filename

    def get_dest(self,index):
        return self.files[index][0]

    def get_datalength(self):
        return self.datalength 

    def _finished(self):
        self.finflag.set()
        try:
            self.storage.set_readonly()
        except (IOError, OSError), e:
            self.errorfunc('trouble setting readonly at end - ' + str(e))
        if self.superseedflag.isSet():
            self._set_super_seed()
        self.choker.set_round_robin_period(
            max( self.config['round_robin_period'],
                 self.config['round_robin_period'] *
                                     self.info['piece length'] / 200000 ) )
        self.rerequest_complete()
        self.finfunc()

    def _data_flunked(self, amount, index):
        self.ratemeasure_datarejected(amount)
        if not self.doneflag.isSet():
            self.logerrorfunc('piece %d failed hash check, re-downloading it' % index)

    def _piece_from_live_source(self,index,data):
        if self.videostatus.live_streaming and self.voddownload is not None:
            return self.voddownload.piece_from_live_source(index,data)
        else:
            return True

    def _failed(self, reason):
        self.failed = True
        self.doneflag.set()
        if reason is not None:
            self.errorfunc(reason)
        

    def initFiles(self, old_style = False, statusfunc = None, resumedata = None):
        """ Now throws exceptions """
        if self.doneflag.isSet():
            return None
        if not statusfunc:
            statusfunc = self.statusfunc

        disabled_files = None
        if self.selector_enabled:
            self.priority = self.config['priority']
            if self.priority:
                try:
                    self.priority = self.priority.split(',')
                    assert len(self.priority) == len(self.files)
                    self.priority = [int(p) for p in self.priority]
                    for p in self.priority:
                        assert p >= -1
                        assert p <= 2
                except:
                    raise ValueError('bad priority list given, ignored')
                    self.priority = None
            try:
                disabled_files = [x == -1 for x in self.priority]
            except:
                pass

        self.storage = Storage(self.files, self.info['piece length'], 
                               self.doneflag, self.config, disabled_files)

        # Merkle: Are we dealing with a Merkle torrent y/n?
        if self.info.has_key('root hash'):
            root_hash = self.info['root hash']
        else:
            root_hash = None
        self.storagewrapper = StorageWrapper(self.videoinfo, self.storage, self.config['download_slice_size'],
            self.pieces, self.info['piece length'], root_hash, 
            self._finished, self._failed,
            statusfunc, self.doneflag, self.config['check_hashes'],
            self._data_flunked, self._piece_from_live_source, self.rawserver.add_task,
            self.config, self.unpauseflag)
            
        if self.selector_enabled:
            self.fileselector = FileSelector(self.files, self.info['piece length'], 
                                             None, 
                                             self.storage, self.storagewrapper, 
                                             self.rawserver.add_task, 
                                             self._failed)

            if resumedata:
                self.fileselector.unpickle(resumedata)
                
        self.checking = True
        if old_style:
            return self.storagewrapper.old_style_init()
        return self.storagewrapper.initialize


    def _make_upload(self, connection, ratelimiter, totalup):
        return Upload(connection, ratelimiter, totalup, 
                      self.choker, self.storagewrapper, self.picker, 
                      self.config)

    def _kick_peer(self, connection):
        def k(connection = connection):
            connection.close()
        self.rawserver.add_task(k, 0)

    def _ban_peer(self, ip):
        self.encoder_ban(ip)

    def _received_raw_data(self, x):
        if self.tcp_ack_fudge:
            x = int(x*self.tcp_ack_fudge)
            self.ratelimiter.adjust_sent(x)
#            self.upmeasure.update_rate(x)

    def _received_data(self, x):
        self.downmeasure.update_rate(x)
        self.ratemeasure.data_came_in(x)

    def _received_http_data(self, x):
        self.downmeasure.update_rate(x)
        self.ratemeasure.data_came_in(x)
        self.downloader.external_data_received(x)

    def _cancelfunc(self, pieces):
        self.downloader.cancel_piece_download(pieces)
        self.ghttpdownloader.cancel_piece_download(pieces)
        self.hhttpdownloader.cancel_piece_download(pieces)
    def _reqmorefunc(self, pieces):
        self.downloader.requeue_piece_download(pieces)

    def startEngine(self, ratelimiter = None, vodeventfunc = None):
        
        if DEBUG:
            print >>sys.stderr,"BT1Download: startEngine",`self.info['name']`
        
        if self.doneflag.isSet():
            return
        
        self.checking = False

        # Arno, 2010-08-11: STBSPEED: if at all, loop only over pieces I have, 
        # not piece range.
        completeondisk = (self.storagewrapper.get_amount_left() == 0)
        if DEBUG:
            print >>sys.stderr,"BT1Download: startEngine: complete on disk?",completeondisk,"found",len(self.storagewrapper.get_pieces_on_disk_at_startup())
        self.picker.fast_initialize(completeondisk)
        if not completeondisk:
            for i in self.storagewrapper.get_pieces_on_disk_at_startup(): # empty when completeondisk
                self.picker.complete(i)
            
        self.upmeasure = Measure(self.config['max_rate_period'], 
                            self.config['upload_rate_fudge'])
        self.downmeasure = Measure(self.config['max_rate_period'])

        if ratelimiter:
            self.ratelimiter = ratelimiter
        else:
            self.ratelimiter = RateLimiter(self.rawserver.add_task, 
                                           self.config['upload_unit_size'], 
                                           self.setConns)
            self.ratelimiter.set_upload_rate(self.config['max_upload_rate'])
        
        self.ratemeasure = RateMeasure()
        self.ratemeasure_datarejected = self.ratemeasure.data_rejected

        self.downloader = Downloader(self.infohash, self.storagewrapper, self.picker, 
            self.config['request_backlog'], self.config['max_rate_period'], 
            self.len_pieces, self.config['download_slice_size'], 
            self._received_data, self.config['snub_time'], self.config['auto_kick'], 
            self._kick_peer, self._ban_peer, scheduler = self.rawserver.add_task)
        self.downloader.set_download_rate(self.config['max_download_rate'])

        self.picker.set_downloader(self.downloader)
# 2fastbt_
        if self.coordinator is not None:
            self.coordinator.set_downloader(self.downloader)

        self.connecter = Connecter(self.response, self._make_upload, self.downloader, self.choker, 
                            self.len_pieces, self.piecesize, self.upmeasure, self.config, 
                            self.ratelimiter, self.info.has_key('root hash'),
                            self.rawserver.add_task, self.coordinator, self.helper, self.get_extip_func, self.port, self.use_g2g,self.infohash,self.response.get('announce',None),self.info.has_key('live'))
# _2fastbt
        self.encoder = Encoder(self.connecter, self.rawserver, 
            self.myid, self.config['max_message_length'], self.rawserver.add_task, 
            self.config['keepalive_interval'], self.infohash, 
            self._received_raw_data, self.config)
        self.encoder_ban = self.encoder.ban
        if "initial peers" in self.response:
            if DEBUG:
                print >> sys.stderr, "BT1Download: startEngine: Using initial peers", self.response["initial peers"]
            self.encoder.start_connections([(address, 0) for address in self.response["initial peers"]])
#--- 2fastbt_
        if DEBUG:
            print str(self.config['exclude_ips'])
        for ip in self.config['exclude_ips']:
            if DEBUG:
                print >>sys.stderr,"BT1Download: startEngine: Banning ip: " + str(ip)
            self.encoder_ban(ip)

        if self.helper is not None:
            from Tribler.Core.ProxyService.RatePredictor import ExpSmoothRatePredictor

            self.helper.set_encoder(self.encoder)
            self.encoder.set_helper(self.helper)
            self.rate_predictor = ExpSmoothRatePredictor(self.rawserver, 
                self.downmeasure, self.config['max_download_rate'])
            self.picker.set_rate_predictor(self.rate_predictor)
            self.rate_predictor.update()
        if self.coordinator is not None:
            self.coordinator.set_encoder(self.encoder)
# _2fastbt

        self.ghttpdownloader = GetRightHTTPDownloader(self.storagewrapper, self.picker, 
            self.rawserver, self.finflag, self.logerrorfunc, self.downloader, 
            self.config['max_rate_period'], self.infohash, self._received_http_data, 
            self.connecter.got_piece)
        if self.response.has_key('url-list') and not self.finflag.isSet():
            for u in self.response['url-list']:
                self.ghttpdownloader.make_download(u)

        self.hhttpdownloader = HoffmanHTTPDownloader(self.storagewrapper, self.picker, 
            self.rawserver, self.finflag, self.logerrorfunc, self.downloader, 
            self.config['max_rate_period'], self.infohash, self._received_http_data, 
            self.connecter.got_piece)
        if self.response.has_key('httpseeds') and not self.finflag.isSet():
            for u in self.response['httpseeds']:
                self.hhttpdownloader.make_download(u)

        if self.selector_enabled:
            self.fileselector.tie_in(self.picker, self._cancelfunc, self._reqmorefunc)
            if self.priority:
                self.fileselector.set_priorities_now(self.priority)
                                # erase old data once you've started modifying it

        # Ric: added svc case TODO check with play_video
        if self.svc_video:
            if self.picker.am_I_complete():
                # TODO do something
                pass
            self.voddownload = SVCTransporter(self,self.videostatus,self.videoinfo,self.videoanalyserpath,vodeventfunc)
        
        elif self.play_video:
            if self.picker.am_I_complete():
                if DEBUG:
                    print >>sys.stderr,"BT1Download: startEngine: VOD requested, but file complete on disk",self.videoinfo
                # Added bitrate parameter for html5 playback
                vodeventfunc( self.videoinfo, VODEVENT_START, {
                    "complete":  True,
                    "filename":  self.videoinfo["outpath"],
                    "mimetype":  self.videoinfo["mimetype"],
                    "stream":    None,
                    "length":    self.videostatus.selected_movie["size"],
                    "bitrate":   self.videoinfo["bitrate"]
                } )
            else:
                if DEBUG:
                    print >>sys.stderr,"BT1Download: startEngine: Going into VOD mode",self.videoinfo

                self.voddownload = MovieOnDemandTransporter(self,self.videostatus,self.videoinfo,self.videoanalyserpath,vodeventfunc,self.ghttpdownloader)
        elif DEBUG:
            print >>sys.stderr,"BT1Download: startEngine: Going into standard mode"

        if self.am_video_source:
            from Tribler.Core.Video.VideoSource import VideoSourceTransporter,RateLimitedVideoSourceTransporter

            if DEBUG:
                print >>sys.stderr,"BT1Download: startEngine: Acting as VideoSource"
            if self.config['video_ratelimit']:
                self.videosourcetransporter = RateLimitedVideoSourceTransporter(self.config['video_ratelimit'],self.config['video_source'],self,self.config['video_source_authconfig'],self.config['video_source_restartstatefilename'])
            else:
                self.videosourcetransporter = VideoSourceTransporter(self.config['video_source'],self,self.config['video_source_authconfig'],self.config['video_source_restartstatefilename'])
            self.videosourcetransporter.start()
        elif DEBUG:
            print >>sys.stderr,"BT1Download: startEngine: Not a VideoSource"
            
        if not self.doneflag.isSet():
            self.started = True

    def rerequest_complete(self):
        if self.rerequest:
            self.rerequest.announce(1)

    def rerequest_stopped(self):
        if self.rerequest:
            self.rerequest.announce(2)

    def rerequest_lastfailed(self):
        if self.rerequest:
            return self.rerequest.last_failed
        return False
    
    def startRerequester(self, paused=False):
        # RePEX:
        # Moved the creation of the Rerequester to a separate method,
        # allowing us to only create the Rerequester without starting
        # it from SingleDownload.
        if self.rerequest is None:
            self.rerequest = self.createRerequester()
            self.encoder.set_rerequester(self.rerequest)
        
        if not paused:
            self.rerequest.start()
            
        
    def createRerequester(self, callback=None):
        if self.response.has_key ('announce-list'):
            trackerlist = self.response['announce-list']
            for tier in range(len(trackerlist)):
                for t in range(len(trackerlist[tier])):
                    trackerlist[tier][t] = bin2unicode(trackerlist[tier][t])
        else:
            tracker = bin2unicode(self.response.get('announce', ''))
            if tracker:
                trackerlist = [[tracker]]
            else:
                trackerlist = [[]]

        if callback is None:
            callback = self.encoder.start_connections

        rerequest = Rerequester(trackerlist, self.config['rerequest_interval'], 
            self.rawserver.add_task,self.connecter.how_many_connections, 
            self.config['min_peers'], callback, 
            self.rawserver.add_task, self.storagewrapper.get_amount_left, 
            self.upmeasure.get_total, self.downmeasure.get_total, self.port, self.config['ip'], 
            self.myid, self.infohash, self.config['http_timeout'], 
            self.logerrorfunc, self.excfunc, self.config['max_initiate'], 
            self.doneflag, self.upmeasure.get_rate, self.downmeasure.get_rate, 
            self.unpauseflag,self.config)

        if self.play_video and self.voddownload is not None:
            rerequest.add_notifier( lambda x: self.voddownload.peers_from_tracker_report( len( x ) ) )

        return rerequest


    def _init_stats(self):
        self.statistics = Statistics(self.upmeasure, self.downmeasure, 
                    self.connecter, self.ghttpdownloader, self.hhttpdownloader, self.ratelimiter, 
                    self.rerequest_lastfailed, self.filedatflag, self.encoder)
        if self.info.has_key('files'):
            self.statistics.set_dirstats(self.files, self.info['piece length'])

    def autoStats(self, displayfunc = None):
        if not displayfunc:
            displayfunc = self.statusfunc

        self._init_stats()
        DownloaderFeedback(self.choker, self.ghttpdownloader, self.hhttpdownloader, self.rawserver.add_task, 
            self.upmeasure.get_rate, self.downmeasure.get_rate, 
            self.ratemeasure, self.storagewrapper.get_stats, 
            self.datalength, self.finflag, self.spewflag, self.statistics, 
            displayfunc, self.config['display_interval'], 
            infohash = self.infohash,voddownload=self.voddownload)

    def startStats(self):
        self._init_stats()
        self.spewflag.set()    # start collecting peer cache
        d = DownloaderFeedback(self.choker, self.ghttpdownloader, self.hhttpdownloader, self.rawserver.add_task, 
            self.upmeasure.get_rate, self.downmeasure.get_rate, 
            self.ratemeasure, self.storagewrapper.get_stats, 
            self.datalength, self.finflag, self.spewflag, self.statistics, 
            infohash = self.infohash,voddownload=self.voddownload)
        return d.gather


    def getPortHandler(self):
        return self.encoder


    def checkpoint(self): # Added by Arno
        """ Called by network thread """
        if self.fileselector and self.started:
            # self.fileselector.finish() does nothing at the moment, so as
            # long as the network thread calls this, it should be OK.
            return self.fileselector.pickle()
        else:
            return None

    def shutdown(self):
        if self.checking or self.started:
            self.storagewrapper.sync()
            self.storage.close()
            self.rerequest_stopped()
        resumedata = None
        if self.fileselector and self.started:
            if not self.failed:
                self.fileselector.finish()
                resumedata = self.fileselector.pickle()
        if self.voddownload is not None:
            self.voddownload.stop()
        return resumedata


    def setUploadRate(self, rate, networkcalling=False):
        try:
            def s(self = self, rate = rate):
                if DEBUG:
                    print >>sys.stderr,"BT1Download: set max upload to",rate
                self.config['max_upload_rate'] = rate
                self.ratelimiter.set_upload_rate(rate)
            if networkcalling:
                s()
            else:
                self.rawserver.add_task(s)
        except AttributeError:
            pass

    def setConns(self, conns, conns2 = None,networkcalling=False):
        if not conns2:
            conns2 = conns
        try:
            def s(self = self, conns = conns, conns2 = conns2):
                self.config['min_uploads'] = conns
                self.config['max_uploads'] = conns2
                if (conns > 30):
                    self.config['max_initiate'] = conns + 10
            if networkcalling:
                s()
            else:
                self.rawserver.add_task(s)
        except AttributeError:
            pass
        
    def setDownloadRate(self, rate,networkcalling=False):
        try:
            def s(self = self, rate = rate):
                self.config['max_download_rate'] = rate
                self.downloader.set_download_rate(rate)
            if networkcalling:
                s()
            else:
                self.rawserver.add_task(s)
        except AttributeError:
            pass

    def startConnection(self, ip, port, id):
        self.encoder._start_connection((ip, port), id)
      
    def _startConnection(self, ipandport, id):
        self.encoder._start_connection(ipandport, id)
        
    def setInitiate(self, initiate,networkcalling=False):
        try:
            def s(self = self, initiate = initiate):
                self.config['max_initiate'] = initiate
            if networkcalling:
                s()
            else:
                self.rawserver.add_task(s)
        except AttributeError:
            pass

    def setMaxConns(self,nconns,networkcalling=False):
        try:
            def s(self = self, nconns = nconns):
                self.config['max_connections'] = nconns
            if networkcalling:
                s()
            else:
                self.rawserver.add_task(s)
        except AttributeError:
            pass


    def getConfig(self):
        return self.config

    def reannounce(self, special = None):
        try:
            def r(self = self, special = special):
                if special is None:
                    self.rerequest.announce()
                else:
                    self.rerequest.announce(specialurl = special)
            self.rawserver.add_task(r)
        except AttributeError:
            pass

    def getResponse(self):
        try:
            return self.response
        except:
            return None

#    def Pause(self):
#        try:
#            if self.storagewrapper:
#                self.rawserver.add_task(self._pausemaker, 0)
#        except:
#            return False
#        self.unpauseflag.clear()
#        return True
#
#    def _pausemaker(self):
#        self.whenpaused = clock()
#        self.unpauseflag.wait()   # sticks a monkey wrench in the main thread
#
#    def Unpause(self):
#        self.unpauseflag.set()
#        if self.whenpaused and clock()-self.whenpaused > 60:
#            def r(self = self):
#                self.rerequest.announce(3)      # rerequest automatically if paused for >60 seconds
#            self.rawserver.add_task(r)

    def Pause(self):
        if not self.storagewrapper:
            return False
        self.unpauseflag.clear()
        self.rawserver.add_task(self.onPause)
        return True

    def onPause(self):
        self.whenpaused = clock()
        if not self.downloader:
            return
        self.downloader.pause(True)
        self.encoder.pause(True)
        self.choker.pause(True)

    def Unpause(self):
        self.unpauseflag.set()
        self.rawserver.add_task(self.onUnpause)

    def onUnpause(self):
        if not self.downloader:
            return
        self.downloader.pause(False)
        self.encoder.pause(False)
        self.choker.pause(False)
        if self.rerequest and self.whenpaused and clock()-self.whenpaused > 60:
            self.rerequest.announce(3)      # rerequest automatically if paused for >60 seconds

    def set_super_seed(self,networkcalling=False):
        self.superseedflag.set()
        if networkcalling:
            self._set_super_seed()
        else:
            self.rawserver.add_task(self._set_super_seed)

    def _set_super_seed(self):
        if not self.super_seeding_active and self.finflag.isSet():
            self.super_seeding_active = True
            self.logerrorfunc('        ** SUPER-SEED OPERATION ACTIVE **\n' +
                           '  please set Max uploads so each peer gets 6-8 kB/s')
            def s(self = self):
                self.downloader.set_super_seed()
                self.choker.set_super_seed()
            self.rawserver.add_task(s)
            if self.finflag.isSet():        # mode started when already finished
                def r(self = self):
                    self.rerequest.announce(3)  # so after kicking everyone off, reannounce
                self.rawserver.add_task(r)

    def am_I_finished(self):
        return self.finflag.isSet()

    def get_transfer_stats(self):
        return self.upmeasure.get_total(), self.downmeasure.get_total()

    def get_moviestreamtransport(self):
        return self.voddownload

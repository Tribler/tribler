# Written by Bram Cohen and Pawel Garbacki
# see LICENSE.txt for license information

import os
from zurllib import urlopen
from urlparse import urlparse
from BT1.btformats import check_message
from BT1.Choker import Choker
from BT1.Storage import Storage
from BT1.StorageWrapper import StorageWrapper
from BT1.FileSelector import FileSelector
from BT1.Uploader import Upload
from BT1.Downloader import Downloader
from BT1.HTTPDownloader import HTTPDownloader
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
from ConfigDir import ConfigDir
from bencode import bencode, bdecode
from sha import sha
from os import path, makedirs, listdir
from parseargs import parseargs, formatDefinitions, defaultargs
from socket import error as socketerror
from random import seed
from threading import Event
from clock import clock
import re
from __init__ import createPeerID

from Tribler.Core.simpledefs import TRIBLER_TORRENT_EXT
from Tribler.Core.Merkle.merkle import create_fake_hashes
from Tribler.Core.Utilities.unicode import bin2unicode
from Tribler.Core.Video.VideoOnDemand import MovieSelector,MovieOnDemandTransporter,PiecePickerVOD

# 2fastbt_
from Tribler.Core.CoopDownload.Coordinator import Coordinator
from Tribler.Core.CoopDownload.Helper import Helper
from Tribler.Core.CoopDownload.RatePredictor import ExpSmoothRatePredictor
import sys
from traceback import print_exc,print_stack
# _2fastbt

from Tribler.Core.simpledefs import *

try:
    True
except:
    True = 1
    False = 0

argslistheader = 'Arguments are:\n\n'

DEBUG = False

def _failfunc(x):
    print x

# old-style downloader
def download(params, filefunc, statusfunc, finfunc, errorfunc, doneflag, cols,
             pathFunc = None, presets = {}, exchandler = None,
             failed = _failfunc, paramfunc = None):

    try:
        config = parse_params(params, presets)
    except ValueError, e:
        failed('error: ' + str(e) + '\nrun with no args for parameter explanations')
        return
    if not config:
        errorfunc(get_usage())
        return
    
    myid = createPeerID()
    seed(myid)

    rawserver = RawServer(doneflag, config['timeout_check_interval'],
                          config['timeout'], ipv6_enable = config['ipv6_enabled'],
                          failfunc = failed, errorfunc = exchandler)

    # Arno: disabled, code never used
    try:
        listen_port = rawserver.find_and_bind(config['minport'], config['maxport'],
                        config['bind'], ipv6_socket_style = config['ipv6_binds_v4'],
                        randomizer = config['random_port'])
    except socketerror, e:
        failed("Couldn't listen - " + str(e))
        return

    response = get_response(config['responsefile'], config['url'], failed)
    if not response:
        return

    infohash = sha(bencode(response['info'])).digest()

    d = BT1Download(statusfunc, finfunc, errorfunc, exchandler, doneflag,
                    config, response, infohash, myid, rawserver, listen_port)

    if not d.saveAs(filefunc):
        return

    if pathFunc:
        pathFunc(d.getFilename())

    hashcheck = d.initFiles(old_style = True)
    if not hashcheck:
        return
    if not hashcheck():
        return
    if not d.startEngine():
        return
    d.startRerequester()
    d.autoStats()

    statusfunc(activity = 'connecting to peers')

    if paramfunc:
        paramfunc({ 'max_upload_rate' : d.setUploadRate,  # change_max_upload_rate(<int KiB/sec>)
                    'max_uploads': d.setConns, # change_max_uploads(<int max uploads>)
                    'listen_port' : listen_port, # int
                    'peer_id' : myid, # string
                    'info_hash' : infohash, # string
                    'start_connection' : d._startConnection, # start_connection((<string ip>, <int port>), <peer id>)
                    })
        
    rawserver.listen_forever(d.getPortHandler())
    
    d.shutdown()


def parse_params(params, presets = {}):
    if not params:
        return None
    config, args = parseargs(params, defaults, 0, 1, presets = presets)
    if args:
        if config['responsefile'] or config['url']:
            raise ValueError, 'must have responsefile or url as arg or parameter, not both'
        if path.isfile(args[0]):
            config['responsefile'] = args[0]
        else:
            try:
                urlparse(args[0])
            except:
                raise ValueError, 'bad filename or url'
            config['url'] = args[0]
    elif (not config['responsefile']) == (not config['url']):
        raise ValueError, 'need responsefile or url, must have one, cannot have both'
    return config


#def get_usage(defaults = defaults, cols = 100, presets = {}):
#    return (argslistheader + formatDefinitions(defaults, cols, presets))


def get_response(file, url, errorfunc):
    try:
        if file:
            h = open(file, 'rb')
            try:
                line = h.read(10)   # quick test to see if responsefile contains a dict
                front, garbage = line.split(':', 1)
                assert front[0] == 'd'
                int(front[1:])
            except:
                errorfunc(file+' is not a valid responsefile')
                return None
            try:
                h.seek(0)
            except:
                try:
                    h.close()
                except:
                    pass
                h = open(file, 'rb')
        else:
            try:
                h = urlopen(url)
            except:
                errorfunc(url+' bad url')
                return None
        response = h.read()
    
    except IOError, e:
        errorfunc('problem getting response info - ' + str(e))
        return None
    try:    
        h.close()
    except:
        pass
    try:
        try:
            response = bdecode(response)
        except:
            errorfunc("warning: bad data in responsefile")
            response = bdecode(response, sloppy=1)
        check_message(response)
    except ValueError, e:
        errorfunc("got bad file info - " + str(e))
        return None

    return response

class BT1Download:    
    def __init__(self, statusfunc, finfunc, errorfunc, excfunc, logerrorfunc, doneflag, 
                 config, response, infohash, id, rawserver, port,
                 videoanalyserpath, appdataobj = None):
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
        self.port = port
        
        self.info = self.response['info']  
        #self.infohash = sha(bencode(self.info)).digest()
        # Merkle: Create list of fake hashes. This will be filled if we're an
        # initial seeder
        if self.info.has_key('root hash'):
            self.pieces = create_fake_hashes(self.info)
        else:
            self.pieces = [self.info['pieces'][x:x+20]
                           for x in xrange(0, len(self.info['pieces']), 20)]
        self.len_pieces = len(self.pieces)
        self.piecesize = self.info['piece length']
        self.argslistheader = argslistheader
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
        
        self.play_video = (config['mode'] == DLMODE_VOD)
        self.videoinfo = None
        self.videoanalyserpath = videoanalyserpath
        self.voddownload = None

        self.selector_enabled = config['selector_enabled']
        if appdataobj:
            self.appdataobj = appdataobj
        elif self.selector_enabled:
            if config.has_key('config_path'):
                self.appdataobj = ConfigDir(dir_root = config['config_path'])
            else:
                self.appdataobj = ConfigDir()
            self.appdataobj.deleteOldCacheData( config['expire_cache_data'],
                                                [self.infohash] )

        self.excflag = self.rawserver.get_exception_flag()
        self.failed = False
        self.checking = False
        self.started = False

# 2fastbt_
        try:
            self.helper = None
            self.coordinator = None
            self.rate_predictor = None
            if self.config['role'] == 'coordinator':
                self.coordinator = Coordinator(self.infohash, self.len_pieces)
            if self.config['role'] == 'coordinator' or self.config['role'] == 'helper':
                self.helper = Helper(self.infohash, self.len_pieces, self.config['coordinator_permid'], coordinator = self.coordinator)
                self.config['role'] = ''
                self.config['coordinator_permid'] = ''

            if self.play_video:
                # Jan-David: Start video-on-demand service
                self.picker = PiecePickerVOD(self.len_pieces, config['rarest_first_cutoff'], 
                             config['rarest_first_priority_cutoff'], helper = self.helper, piecesize=self.piecesize)
            else:
                self.picker = PiecePicker(self.len_pieces, config['rarest_first_cutoff'], 
                             config['rarest_first_priority_cutoff'], helper = self.helper)
        except:
            print_exc()
            print >> sys.stderr,"download_bt1.BT1Download: EXCEPTION in __init__ :'" + str(sys.exc_info()) + "' '"
# _2fastbt

        self.choker = Choker(config, rawserver.add_task, 
                             self.picker, self.finflag.isSet)

        #print >>sys.stderr,"download_bt1.BT1Download: play_video is",self.play_video

    def set_videoinfo(self,videoinfo):
        self.videoinfo = videoinfo


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
                        if path.exists(path.join(file, x['path'][0])):
                            existing = 1
                    if not existing:
                        file = path.join(file, self.info['name'])
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
                n = file
                for i in x['path']:
                    n = path.join(n, i)
                files.append((n, x['length']))
                make(n)
        if DEBUG:
            print >>sys.stderr,"BT1Download: saveas 2"

        self.filename = file
        self.files = files
        self.datalength = file_length
        
        if DEBUG:
            print "BT1Download: saveas returning ", file
                
        return file


    def getFilename(self):
        return self.filename

    def get_dest(self,index):
        return self.files[index][0]

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
            self._data_flunked, self.rawserver.add_task,
            self.config, self.unpauseflag)
            
        if self.selector_enabled:
            self.fileselector = FileSelector(self.files, self.info['piece length'], 
                                             self.appdataobj.getPieceDir(self.infohash), 
                                             self.storage, self.storagewrapper, 
                                             self.rawserver.add_task, 
                                             self._failed)
            if resumedata:
                self.fileselector.unpickle(resumedata)
                
        self.checking = True
        if old_style:
            return self.storagewrapper.old_style_init()
        return self.storagewrapper.initialize


    def getCachedTorrentData(self):
        return self.appdataobj.getTorrentData(self.infohash)


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
        self.httpdownloader.cancel_piece_download(pieces)
    def _reqmorefunc(self, pieces):
        self.downloader.requeue_piece_download(pieces)

    def startEngine(self, ratelimiter = None, vodplayablefunc = None):
        
        if DEBUG:
            print >>sys.stderr,"BT1Download: startEngine"
        
        if self.doneflag.isSet():
            return
        
        self.checking = False

        for i in xrange(self.len_pieces):
            if self.storagewrapper.do_I_have(i):
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

        self.downloader = Downloader(self.storagewrapper, self.picker, 
            self.config['request_backlog'], self.config['max_rate_period'], 
            self.len_pieces, self.config['download_slice_size'], 
            self._received_data, self.config['snub_time'], self.config['auto_kick'], 
            self._kick_peer, self._ban_peer, scheduler = self.rawserver.add_task)
        self.downloader.set_download_rate(self.config['max_download_rate'])
# 2fastbt_
        self.connecter = Connecter(self._make_upload, self.downloader, self.choker, 
                            self.len_pieces, self.upmeasure, self.config, 
                            self.ratelimiter, self.info.has_key('root hash'),
                            self.rawserver.add_task, self.coordinator, self.helper, self.port, self.play_video,self.infohash)
# _2fastbt
        self.encoder = Encoder(self.connecter, self.rawserver, 
            self.myid, self.config['max_message_length'], self.rawserver.add_task, 
            self.config['keepalive_interval'], self.infohash, 
            self._received_raw_data, self.config)
        self.encoder_ban = self.encoder.ban
#--- 2fastbt_
        try:
            list_of_banned_ips = self.config['exclude_ips'].split(',')
            self.config['exclude_ips'] = list_of_banned_ips
        except:
            self.config['exclude_ips'] = []
        if DEBUG:
            print str(self.config['exclude_ips'])
        for ip in self.config['exclude_ips']:
            if DEBUG:
                print "Banning ip: " + str(ip)
            self.encoder_ban(ip)

        if self.helper is not None:
            self.helper.set_encoder(self.encoder)
            self.rate_predictor = ExpSmoothRatePredictor(self.rawserver, 
                self.downmeasure, self.config['max_download_rate'])
            self.picker.set_rate_predictor(self.rate_predictor)
            self.rate_predictor.update()
# _2fastbt

        self.httpdownloader = HTTPDownloader(self.storagewrapper, self.picker, 
            self.rawserver, self.finflag, self.logerrorfunc, self.downloader, 
            self.config['max_rate_period'], self.infohash, self._received_http_data, 
            self.connecter.got_piece)
        if self.response.has_key('httpseeds') and not self.finflag.isSet():
            for u in self.response['httpseeds']:
                self.httpdownloader.make_download(u)

        if self.selector_enabled:
            self.fileselector.tie_in(self.picker, self._cancelfunc, self._reqmorefunc)
            if self.priority:
                self.fileselector.set_priorities_now(self.priority)
            self.appdataobj.deleteTorrentData(self.infohash)
                                # erase old data once you've started modifying it

        if self.play_video:
            if self.picker.am_I_complete():
                if DEBUG:
                    print >>sys.stderr,"BT1Download: startEngine: VOD requested, but file complete on disk",self.videoinfo
                vodplayablefunc(self.videoinfo,True,None,None)
            else:
                if DEBUG:
                    print >>sys.stderr,"BT1Download: startEngine: Going into VOD mode",self.videoinfo
                self.picker.set_downloader(self.downloader)
                self.movieselector = MovieSelector(self.videoinfo,self.fileselector,self.storagewrapper,self.picker)
                self.voddownload = MovieOnDemandTransporter(self.movieselector,self.picker,self.info['piece length'], self.rawserver, self.videoanalyserpath,vodplayablefunc)
                
        elif DEBUG:
            print >>sys.stderr,"BT1Download: startEngine: Going into standard mode"
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

    def startRerequester(self):
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
            
        self.rerequest = Rerequester(trackerlist, self.config['rerequest_interval'], 
            self.rawserver.add_task,self.connecter.how_many_connections, 
            self.config['min_peers'], self.encoder.start_connections, 
            self.rawserver.add_task, self.storagewrapper.get_amount_left, 
            self.upmeasure.get_total, self.downmeasure.get_total, self.port, self.config['ip'], 
            self.myid, self.infohash, self.config['http_timeout'], 
            self.logerrorfunc, self.excfunc, self.config['max_initiate'], 
            self.doneflag, self.upmeasure.get_rate, self.downmeasure.get_rate, 
            self.unpauseflag,self.config)

        self.encoder.set_rerequester(self.rerequest)
        self.rerequest.start()


    def _init_stats(self):
        self.statistics = Statistics(self.upmeasure, self.downmeasure, 
                    self.connecter, self.httpdownloader, self.ratelimiter, 
                    self.rerequest_lastfailed, self.filedatflag)
        if self.info.has_key('files'):
            self.statistics.set_dirstats(self.files, self.info['piece length'])

    def autoStats(self, displayfunc = None):
        if not displayfunc:
            displayfunc = self.statusfunc

        self._init_stats()
        DownloaderFeedback(self.choker, self.httpdownloader, self.rawserver.add_task, 
            self.upmeasure.get_rate, self.downmeasure.get_rate, 
            self.ratemeasure, self.storagewrapper.get_stats, 
            self.datalength, self.finflag, self.spewflag, self.statistics, 
            displayfunc, self.config['display_interval'], 
            infohash = self.infohash,voddownload=self.voddownload)

    def startStats(self):
        self._init_stats()
        self.spewflag.set()    # start collecting peer cache
        d = DownloaderFeedback(self.choker, self.httpdownloader, self.rawserver.add_task, 
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
                
                #print >>sys.stderr,"BT1Download: set max upload to",rate # TEMP ARNO
                
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

    def getDefaults(self):
        return defaultargs(defaults)

    def getUsageText(self):
        return self.argslistheader

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

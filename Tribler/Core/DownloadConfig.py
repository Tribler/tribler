# Written by Arno Bakker 
# see LICENSE.txt for license information

import sys
import os
#import time
import copy
import sha
import pickle
import shutil
from traceback import print_exc,print_stack
from types import StringType,ListType,IntType

from Tribler.Core.simpledefs import *
from Tribler.Core.defaults import *
from Tribler.Core.exceptions import *
from Tribler.Core.Base import *
from Tribler.Core.APIImplementation.miscutils import *

from Tribler.Core.Utilities.unicode import metainfoname2unicode
from Tribler.Core.osutils import *


class DownloadConfigInterface:
    """
    (key,value) pair config of per-torrent runtime parameters,
    e.g. destdir, file-allocation policy, etc. Also options to advocate
    torrent, e.g. register in DHT, advertise via Buddycast.
    
    Use DownloadStartupConfig to manipulate download configs before download 
    startup time. This is just a parent class.
     
    cf. libtorrent torrent_handle
    """
    def __init__(self,dlconfig=None):
        
        if dlconfig is not None: # copy constructor
            self.dlconfig = dlconfig
            return
        
        self.dlconfig = {}
        
        # Define the built-in default here
        self.dlconfig.update(dldefaults)

        self.dlconfig['saveas'] = get_default_dest_dir()


    def set_dest_dir(self,path):
        """ Sets the directory where to save this Download """
        self.dlconfig['saveas'] = path

    def set_video_on_demand(self,usercallback):
        """ Download the torrent in Video-On-Demand mode. usercallback is a 
        function that accepts a file-like object as its first argument. 
        To fetch a specific file from a multi-file torrent, use the
        set_selected_files() method. """
        self.dlconfig['mode'] = DLMODE_VOD
        self.dlconfig['vod_usercallback'] = usercallback


    def get_mode(self):
        return self.dlconfig['mode']

    def get_vod_callback(self):
        return self.dlconfig['vod_usercallback']

    def set_selected_files(self,files):
        """ Select which files to download. "files" can be a single filename
        or a list of filenames (e.g. ['harry.avi','sjaak.avi']). The filenames
        must be in print format. TODO explain + add methods """
        # TODO: can't check if files exists, don't have tdef here.... bugger
        if type(files) == StringType: # convenience
            files = [files] 
            
        if self.dlconfig['mode'] == DLMODE_VOD and len(files) > 1:
            raise ValueError("In Video-On-Demand mode only 1 file can be selected for download")
        self.dlconfig['selected_files'] = files
        
        print >>sys.stderr,"DownloadStartupConfig: set_selected_files",files

    def get_selected_files(self):
        return self.dlconfig['selected_files']

    #
    # Common download performance parameters
    #
    def set_max_speed(self,direct,speed):
        """ Sets the maximum upload or download speed for this Download in KB/s """
        if direct == UPLOAD:
            self.dlconfig['max_upload_rate'] = speed
        else:
            self.dlconfig['max_download_rate'] = speed

    def get_max_speed(self,direct):
        if direct == UPLOAD:
            return self.dlconfig['max_upload_rate']
        else:
            return self.dlconfig['max_download_rate']

    def set_max_conns_to_initiate(self,nconns):
        """ Sets the maximum number of connections to initiate for this 
        Download """
        self.dlconfig['max_initiate'] = nconns

    def get_max_conns_to_initiate(self):
        return self.dlconfig['max_initiate']

    def set_max_conns(self,nconns):
        """ Sets the maximum number of connections to connections for this 
        Download """
        self.dlconfig['max_connections'] = nconns

    def get_max_conns(self):
        return self.dlconfig['max_connections']

    #
    # Advanced download parameters
    # 
    def set_max_uploads(self,value):
        """ the maximum number of uploads to allow at once. """
        self.dlconfig['max_uploads'] = value

    def get_max_uploads(self):
        return self.dlconfig['max_uploads']

    def set_keepalive_interval(self,value):
        """ number of seconds to pause between sending keepalives """
        self.dlconfig['keepalive_interval'] = value

    def get_keepalive_interval(self):
        return self.dlconfig['keepalive_interval']

    def set_download_slice_size(self,value):
        """ How many bytes to query for per request. """
        self.dlconfig['download_slice_size'] = value

    def get_download_slice_size(self):
        return self.dlconfig['download_slice_size']

    def set_upload_unit_size(self,value):
        """ when limiting upload rate, how many bytes to send at a time """
        self.dlconfig['upload_unit_size'] = value

    def get_upload_unit_size(self):
        return self.dlconfig['upload_unit_size']

    def set_request_backlog(self,value):
        """ maximum number of requests to keep in a single pipe at once. """
        self.dlconfig['request_backlog'] = value

    def get_request_backlog(self):
        return self.dlconfig['request_backlog']

    def set_max_message_length(self,value):
        """ maximum length prefix encoding you'll accept over the wire - larger values get the connection dropped. """
        self.dlconfig['max_message_length'] = value

    def get_max_message_length(self):
        return self.dlconfig['max_message_length']

    def set_max_slice_length(self,value):
        """ maximum length slice to send to peers, larger requests are ignored """
        self.dlconfig['max_slice_length'] = value

    def get_max_slice_length(self):
        return self.dlconfig['max_slice_length']

    def set_max_rate_period(self,value):
        """ maximum amount of time to guess the current rate estimate represents """
        self.dlconfig['max_rate_period'] = value

    def get_max_rate_period(self):
        return self.dlconfig['max_rate_period']

    def set_upload_rate_fudge(self,value):
        """ time equivalent of writing to kernel-level TCP buffer, for rate adjustment """
        self.dlconfig['upload_rate_fudge'] = value

    def get_upload_rate_fudge(self):
        return self.dlconfig['upload_rate_fudge']

    def set_tcp_ack_fudge(self,value):
        """ how much TCP ACK download overhead to add to upload rate calculations (0 = disabled) """
        self.dlconfig['tcp_ack_fudge'] = value

    def get_tcp_ack_fudge(self):
        return self.dlconfig['tcp_ack_fudge']

    def set_rerequest_interval(self,value):
        """ time to wait between requesting more peers """
        self.dlconfig['rerequest_interval'] = value

    def get_rerequest_interval(self):
        return self.dlconfig['rerequest_interval']

    def set_min_peers(self,value):
        """ minimum number of peers to not do rerequesting """
        self.dlconfig['min_peers'] = value

    def get_min_peers(self):
        return self.dlconfig['min_peers']

    def set_http_timeout(self,value):
        """ number of seconds to wait before assuming that an http connection has timed out """
        self.dlconfig['http_timeout'] = value

    def get_http_timeout(self):
        return self.dlconfig['http_timeout']

    def set_check_hashes(self,value):
        """ whether to check hashes on disk """
        self.dlconfig['check_hashes'] = value

    def get_check_hashes(self):
        return self.dlconfig['check_hashes']

    def set_alloc_type(self,value):
        """ allocation type (may be normal, background, pre-allocate or sparse) """
        self.dlconfig['alloc_type'] = value

    def get_alloc_type(self):
        return self.dlconfig['alloc_type']

    def set_alloc_rate(self,value):
        """ rate (in MiB/s) to allocate space at using background allocation """
        self.dlconfig['alloc_rate'] = value

    def get_alloc_rate(self):
        return self.dlconfig['alloc_rate']

    def set_buffer_reads(self,value):
        """ whether to buffer disk reads """
        self.dlconfig['buffer_reads'] = value

    def get_buffer_reads(self):
        return self.dlconfig['buffer_reads']

    def set_write_buffer_size(self,value):
        """ the maximum amount of space to use for buffering disk writes (in megabytes, 0 = disabled) """
        self.dlconfig['write_buffer_size'] = value

    def get_write_buffer_size(self):
        return self.dlconfig['write_buffer_size']

    def set_breakup_seed_bitfield(self,value):
        """ sends an incomplete bitfield and then fills with have messages, in order to get around stupid ISP manipulation """
        self.dlconfig['breakup_seed_bitfield'] = value

    def get_breakup_seed_bitfield(self):
        return self.dlconfig['breakup_seed_bitfield']

    def set_snub_time(self,value):
        """ seconds to wait for data to come in over a connection before assuming it's semi-permanently choked """
        self.dlconfig['snub_time'] = value

    def get_snub_time(self):
        return self.dlconfig['snub_time']

    def set_rarest_first_cutoff(self,value):
        """ number of downloads at which to switch from random to rarest first """
        self.dlconfig['rarest_first_cutoff'] = value

    def get_rarest_first_cutoff(self):
        return self.dlconfig['rarest_first_cutoff']

    def set_rarest_first_priority_cutoff(self,value):
        """ the number of peers which need to have a piece before other partials take priority over rarest first """
        self.dlconfig['rarest_first_priority_cutoff'] = value

    def get_rarest_first_priority_cutoff(self):
        return self.dlconfig['rarest_first_priority_cutoff']

    def set_min_uploads(self,value):
        """ the number of uploads to fill out to with extra optimistic unchokes """
        self.dlconfig['min_uploads'] = value

    def get_min_uploads(self):
        return self.dlconfig['min_uploads']

    def set_max_files_open(self,value):
        """ the maximum number of files to keep open at a time, 0 means no limit """
        self.dlconfig['max_files_open'] = value

    def get_max_files_open(self):
        return self.dlconfig['max_files_open']

    def set_round_robin_period(self,value):
        """ the number of seconds between the client's switching upload targets """
        self.dlconfig['round_robin_period'] = value

    def get_round_robin_period(self):
        return self.dlconfig['round_robin_period']

    def set_super_seeder(self,value):
        """ whether to use special upload-efficiency-maximizing routines (only for dedicated seeds) """
        self.dlconfig['super_seeder'] = value

    def get_super_seeder(self):
        return self.dlconfig['super_seeder']

    def set_security(self,value):
        """ whether to enable extra security features intended to prevent abuse """
        self.dlconfig['security'] = value

    def get_security(self):
        return self.dlconfig['security']

    def set_max_connections(self,value):
        """ the absolute maximum number of peers to connect with (0 = no limit) """
        self.dlconfig['max_connections'] = value

    def get_max_connections(self):
        return self.dlconfig['max_connections']

    def set_auto_kick(self,value):
        """ whether to allow the client to automatically kick/ban peers that send bad data """
        self.dlconfig['auto_kick'] = value

    def get_auto_kick(self):
        return self.dlconfig['auto_kick']

    def set_double_check(self,value):
        """ whether to double-check data being written to the disk for errors (may increase CPU load) """
        self.dlconfig['double_check'] = value

    def get_double_check(self):
        return self.dlconfig['double_check']

    def set_triple_check(self,value):
        """ whether to thoroughly check data being written to the disk (may slow disk access) """
        self.dlconfig['triple_check'] = value

    def get_triple_check(self):
        return self.dlconfig['triple_check']

    def set_lock_files(self,value):
        """ whether to lock files the client is working with """
        self.dlconfig['lock_files'] = value

    def get_lock_files(self):
        return self.dlconfig['lock_files']

    def set_lock_while_reading(self,value):
        """ whether to lock access to files being read """
        self.dlconfig['lock_while_reading'] = value

    def get_lock_while_reading(self):
        return self.dlconfig['lock_while_reading']

    def set_auto_flush(self,value):
        """ minutes between automatic flushes to disk (0 = disabled) """
        self.dlconfig['auto_flush'] = value

    def get_auto_flush(self):
        return self.dlconfig['auto_flush']

    def set_exclude_ips(self,value):
        """ list of IP addresse to be excluded; comma separated """
        self.dlconfig['exclude_ips'] = value

    def get_exclude_ips(self):
        return self.dlconfig['exclude_ips']

    def set_ut_pex_max_addrs_from_peer(self,value):
        """ maximum number of addresses to accept from peer (0 = disabled PEX) """
        self.dlconfig['ut_pex_max_addrs_from_peer'] = value

    def get_ut_pex_max_addrs_from_peer(self):
        return self.dlconfig['ut_pex_max_addrs_from_peer']


class DownloadStartupConfig(DownloadConfigInterface,Serializable,Copyable):
    """
    (key,value) pair config of per-torrent runtime parameters,
    e.g. destdir, file-allocation policy, etc. Also options to advocate
    torrent, e.g. register in DHT, advertise via Buddycast.
    
    cf. libtorrent torrent_handle
    """
    def __init__(self,dlconfig=None):
        """ Normal constructor for DownloadStartupConfig (copy constructor 
        used internally) """
        DownloadConfigInterface.__init__(self,dlconfig)

    #
    # Copyable interface
    # 
    def copy(self):
        config = copy.copy(self.dlconfig)
        return DownloadStartupConfig(config)


def get_default_dest_dir():
    if sys.platform == 'win32':
        profiledir = os.path.expandvars('${USERPROFILE}')
        tempdir = os.path.join(profiledir,'Desktop','TriblerDownloads')
        return tempdir 
    elif sys.platform == 'darwin':
        profiledir = os.path.expandvars('${HOME}')
        tempdir = os.path.join(profiledir,'Desktop','TriblerDownloads')
        return tempdir
    else:
        return '/tmp'
    

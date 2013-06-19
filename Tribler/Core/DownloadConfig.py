# Written by Arno Bakker
# Updated by George Milescu
# see LICENSE.txt for license information
""" Controls how a TorrentDef is downloaded (rate, where on disk, etc.) """

#
# WARNING: When extending this class:
#
# 1. Add a JavaDoc description for each method you add.
# 2. Also add the methods to APIImplementation/DownloadRuntimeConfig.py
# 3. Document your changes in API.py
#
#

import sys
import os
# import time
import copy
import pickle
from types import StringType

from Tribler.Core.simpledefs import *
from Tribler.Core.defaults import *
from Tribler.Core.exceptions import *
from Tribler.Core.Base import *
from Tribler.Core.APIImplementation.miscutils import *

from Tribler.Core.osutils import getfreespace, get_desktop_dir


class DownloadConfigInterface:

    """
    (key,value) pair config of per-torrent runtime parameters,
    e.g. destdir, file-allocation policy, etc. Also options to advocate
    torrent, e.g. register in DHT, advertise via Buddycast.

    Use DownloadStartupConfig to manipulate download configs before download
    startup time. This is just a parent class.

    cf. libtorrent torrent_handle
    """
    def __init__(self, dlconfig=None):

        if dlconfig is not None:  # copy constructor

            # modify/fix incorrectly saved dlconfigs
            if isinstance(dlconfig['saveas'], tuple):
                dlconfig['saveas'] = dlconfig['saveas'][-1]

            self.dlconfig = dlconfig
            return

        self.dlconfig = {}

        # Define the built-in default here
        self.dlconfig.update(dldefaults)

        if not self.get_dest_dir():
            self.set_dest_dir(get_default_dest_dir())

    def updateToCurrentVersion(self):
        """ Will update this DownloadConfig to the latest version
        @return list of added field if update was necessary
        @return None if version was current
        """

        oldver = self.dlconfig['version']
        if oldver != DLDEFAULTS_VERSION:
            updatedFields = []

            for key in dldefaults.keys():
                if key not in self.dlconfig:
                    self.dlconfig[key] = dldefaults[key]
                    updatedFields.append(key)
            self.dlconfig['version'] = DLDEFAULTS_VERSION

            return updatedFields
        return None

    def set_dest_dir(self, path):
        """ Sets the directory where to save this Download.
        @param path A path of a directory.
        """
        assert isinstance(path, basestring), path
        self.dlconfig['saveas'] = path

    def get_dest_dir(self):
        """ Gets the directory where to save this Download.
        """
        return self.dlconfig['saveas']

    # LAYERVIOLATION: Core has nothing to do with GUI dialogs
    def get_show_saveas(self):
        """ Gets the boolean indicating if we should show a dialog where to save a torrent
        """
        return self.dlconfig['showsaveas']

    def set_show_saveas(self, show):
        """ Sets the boolean indicating if we should show a dialog where to save a torrent
        @param show Boolean to show a dialog
        """
        self.dlconfig['showsaveas'] = show

    def get_corrected_filename(self):
        """ Gets the directory name where to save this torrent
        """
        return self.dlconfig['correctedfilename']

    def set_corrected_filename(self, correctedfilename):
        """ Sets the directory name where to save this torrent
        @param correctedfilename name for multifile directory
        """
        self.dlconfig['correctedfilename'] = correctedfilename

    def set_video_event_callback(self, usercallback):
        """ Download the torrent in Video-On-Demand mode or as live stream.
        When a playback event occurs, the usercallback function will be
        called, with the following list of arguments:
        <pre>
            Download,event,params
        </pre>
        In which event is a string, and params a dictionary. The following
        events are supported:
        <pre>
        VODEVENT_START:
            The params dictionary will contain the fields

                mimetype,stream,filename,length,bitrate,blocksize,url

            If the filename is set, the video can be read from there. If not,
            the video can be read from the stream, which is a file-like object
            supporting the read(),seek(), and close() operations. It also
            supports an available() method that returns the number of bytes
            that can be read from the stream without blocking.  If the stream
            is not set, the url key contains a URL for the video.

            The MIME type of the video is given by "mimetype", the length of
            the stream in bytes by "length" which may be None if the length is
            unknown (e.g. when live streaming). bitrate is either the bitrate
            as specified in the TorrentDef, or if that was lacking an dynamic
            estimate calculated using the videoanalyser (e.g. ffmpeg), see
            SessionConfig.set_video_analyser_path(). "blocksize" indicates
            the preferred amount of data to read from the stream at a time.

            To fetch a specific file from a multi-file torrent, use the
            set_selected_files() method. This method sets the mode to DLMODE_VOD

        VODEVENT_PAUSE:
            The download engine would like video playback to be paused as the
            data is not coming in fast enough / the data due is not available
            yet.

            The params dictionary contains the fields

                autoresume

            "autoresume" indicates whether or not the Core will generate
            a VODEVENT_RESUME when it is ready again, or that this is left
            to the core user.

        VODEVENT_RESUME:
            The download engine would like video playback to resume.
        </pre>
        The usercallback should ignore events it does not support.

        The usercallback will be called by a popup thread which can be used
        indefinitely (within reason) by the higher level code.

        @param usercallback  A function with the above signature.
        """
        self.dlconfig['vod_usercallback'] = usercallback

    def set_video_events(self, events=[]):
        """ Sets which events will be supported with the usercallback set
        by set_video_event_callback. Supporting the VODEVENT_START event is
        mandatory, and can therefore be omitted from the list.

        @param events        A list of supported VODEVENT_* events.
        """

        # create a copy to avoid loosing the info
        self.dlconfig['vod_userevents'] = events[:]

    def set_video_source(self, videosource, authconfig=None, restartstatefilename=None):
        """ Provides the live video source for this torrent from an external
        source.

        @param videosource  A file-like object providing the live video stream
        (i.e., supports read() and close())
        @param authconfig The key information for source authentication of
        packets. See LiveSourceAuthConfig and TorrentDef.create_live_torrent()
        @param restartstatefilename A filename to read/write state needed for a
        graceful restart of the source.
        """
        self.dlconfig['video_source'] = videosource
        if authconfig is None:
            from Tribler.Core.LiveSourceAuthConfig import LiveSourceAuthConfig

            authconfig = LiveSourceAuthConfig(LIVE_AUTHMETHOD_NONE)
        self.dlconfig['video_source_authconfig'] = authconfig
        self.dlconfig['video_source_restartstatefilename'] = restartstatefilename

    def set_video_ratelimit(self, ratelimit):
        """ Sets a limit on the speed at which the video stream is to be read.
        Useful when creating a live stream from file or any other faster-than-live
        data stream.

        @param ratelimit    The maximum speed at which to read from the stream (bps)
        """
        self.dlconfig['video_ratelimit'] = ratelimit

    def set_mode(self, mode):
        """ Sets the mode of this download.
        @param mode DLMODE_NORMAL/DLMODE_VOD """
        self.dlconfig['mode'] = mode

    def set_live_aux_seeders(self, seeders):
        """ Sets a number of live seeders, auxiliary servers that
        get high priority at the source server to distribute its content
        to others.
        @param seeders A list of [IP address,port] lists.
        """
        self.dlconfig['live_aux_seeders'] = seeders

    def get_mode(self):
        """ Returns the mode of this download.
        @return DLMODE_NORMAL/DLMODE_VOD """
        return self.dlconfig['mode']

    def get_video_event_callback(self):
        """ Returns the function that was passed to set_video_event_callback().
        @return A function.
        """
        return self.dlconfig['vod_usercallback']

    def get_video_events(self):
        """ Returns the function that was passed to set_video_events().
        @return A list of events.
        """
        return self.dlconfig['vod_userevents']

    def get_video_source(self):
        """ Returns the object that was passed to set_video_source().
        @return A file-like object.
        """
        return self.dlconfig['video_source']

    def get_video_ratelimit(self):
        """ Returns the speed at which the video stream is read (bps).
        @return An integer.
        """
        return self.dlconfig['video_ratelimit']

    def get_live_aux_seeders(self):
        """ Returns the aux. live seeders set.
        @return A list of [IP address,port] lists. """
        return self.dlconfig['live_aux_seeders']

    def set_selected_files(self, files):
        """ Select which files in the torrent to download. The filenames must
        be the names as they appear in the content def, including encoding.
        Trivially, when the torrent contains a file 'sjaak.avi' the files
        parameter must be 'sjaak.avi'. When the content def is a torrent def
        and contains multiple files and is named 'filecollection', the files
        parameter must be
            os.path.join('filecollection','sjaak.avi')
        For a swift def, the files must be following the multi-file spec encoding
        (i.e., UTF-8 and /).

        @param files Can be a single filename or a list of filenames (e.g.
        ['harry.avi','sjaak.avi']). Not Unicode strings!
        """
        # TODO: can't check if files exists, don't have tdef here.... bugger
        if isinstance(files, StringType):  # convenience
            files = [files]

        if self.dlconfig['mode'] == DLMODE_VOD and len(files) > 1:
            raise ValueError("In Video-On-Demand mode only 1 file can be selected for download")

        # Ric: added svc case
        elif self.dlconfig['mode'] == DLMODE_SVC and len(files) < 2:
            raise ValueError("In SVC Video-On-Demand mode at least 2 files have to be selected for download")

        self.dlconfig['selected_files'] = files

    def get_selected_files(self):
        """ Returns the list of files selected for download.
        @return A list of strings. """
        return self.dlconfig['selected_files']

    #
    # Common download performance parameters
    #
    def set_max_speed(self, direct, speed):
        """ Sets the maximum upload or download speed for this Download.
        @param direct The direction (UPLOAD/DOWNLOAD)
        @param speed The speed in KB/s.
        """
        if direct == UPLOAD:
            self.dlconfig['max_upload_rate'] = speed
        else:
            self.dlconfig['max_download_rate'] = speed

    def get_max_speed(self, direct):
        """ Returns the configured maximum speed.
        Returns the speed in KB/s. """
        if direct == UPLOAD:
            return self.dlconfig['max_upload_rate']
        else:
            return self.dlconfig['max_download_rate']

    def set_max_conns_to_initiate(self, nconns):
        """ Sets the maximum number of connections to initiate for this
        Download.
        @param nconns A number of connections.
        """
        self.dlconfig['max_initiate'] = nconns

    def get_max_conns_to_initiate(self):
        """ Returns the configured maximum number of connections to initiate.
        @return A number of connections.
        """
        return self.dlconfig['max_initiate']

    def set_max_conns(self, nconns):
        """ Sets the maximum number of connections to connections for this
        Download.
        @param nconns A number of connections.
        """
        self.dlconfig['max_connections'] = nconns

    def get_max_conns(self):
        """ Returns the configured maximum number of connections.
        @return A number of connections.
        """
        return self.dlconfig['max_connections']

    #
    # Advanced download parameters
    #
    def set_max_uploads(self, value):
        """ Set the maximum number of uploads to allow at once.
        @param value A number.
        """
        self.dlconfig['max_uploads'] = value

    def get_max_uploads(self):
        """ Returns the maximum number of uploads.
        @return A number. """
        return self.dlconfig['max_uploads']

    def set_keepalive_interval(self, value):
        """ Set the number of seconds to pause between sending keepalives.
        @param value An interval """
        self.dlconfig['keepalive_interval'] = value

    def get_keepalive_interval(self):
        """ Returns the keepalive interval.
        @return A number of seconds. """
        return self.dlconfig['keepalive_interval']

    def set_download_slice_size(self, value):
        """ Set how many bytes to query for per request.
        @param value A number of bytes.
        """
        self.dlconfig['download_slice_size'] = value

    def get_download_slice_size(self):
        """ Returns the number of bytes to query per request.
        @return A number of bytes. """
        return self.dlconfig['download_slice_size']

    def set_upload_unit_size(self, value):
        """ When limiting upload rate, how many bytes to send at a time.
        @param value A number of bytes. """
        self.dlconfig['upload_unit_size'] = value

    def get_upload_unit_size(self):
        """ Returns the set upload unit size.
        @returns A number of bytes.
        """
        return self.dlconfig['upload_unit_size']

    def set_request_backlog(self, value):
        """ Maximum number of requests to keep in a single pipe at once.
        @param value A number of requests.
        """
        self.dlconfig['request_backlog'] = value

    def get_request_backlog(self):
        """ Returns the request backlog.
        @return A number of requests.
        """
        return self.dlconfig['request_backlog']

    def set_max_message_length(self, value):
        """ Maximum message-length prefix to accept over the wire - larger
        values get the connection dropped.
        @param value A number of bytes.
        """
        self.dlconfig['max_message_length'] = value

    def get_max_message_length(self):
        """ Returns the maximum message length that is accepted.
        @return A number of bytes.
        """
        return self.dlconfig['max_message_length']

    def set_max_slice_length(self, value):
        """ Maximum length slice to send to peers, larger requests are ignored.
        @param value A number of bytes.
        """
        self.dlconfig['max_slice_length'] = value

    def get_max_slice_length(self):
        """ Returns the maximum slice length that is accepted.
        @return A number of bytes.
        """
        return self.dlconfig['max_slice_length']

    def set_max_rate_period(self, value):
        """ Maximum amount of time to guess the current rate estimate.
        @param value A number of seconds. """
        self.dlconfig['max_rate_period'] = value

    def get_max_rate_period(self):
        """ Returns the maximum rate period.
        @return A number of seconds.
        """
        return self.dlconfig['max_rate_period']

    def set_upload_rate_fudge(self, value):
        """ Time equivalent of writing to kernel-level TCP buffer, for rate
        adjustment.
        @param value A number of seconds.
        """
        self.dlconfig['upload_rate_fudge'] = value

    def get_upload_rate_fudge(self):
        """ Returns the upload rate fudge.
        @return A number of seconds.
        """
        return self.dlconfig['upload_rate_fudge']

    def set_tcp_ack_fudge(self, value):
        """ How much TCP ACK download overhead to add to upload rate
        calculations. I.e. when a message is received we add X percent
        of this message to our upload rate to account for TCP ACKs that
        were sent during the reception process. (0 = disabled)
        @param value A percentage
        """
        self.dlconfig['tcp_ack_fudge'] = value

    def get_tcp_ack_fudge(self):
        """ Returns the TCP ACK fudge.
        @return A percentage.
        """
        return self.dlconfig['tcp_ack_fudge']

    def set_rerequest_interval(self, value):
        """ Time to wait between requesting more peers from tracker.
        @param value An interval in seconds.
        """
        self.dlconfig['rerequest_interval'] = value

    def get_rerequest_interval(self):
        """ Returns the tracker re-request interval.
        @return A number of seconds.
        """
        return self.dlconfig['rerequest_interval']

    def set_min_peers(self, value):
        """ Minimum number of peers to not do rerequesting.
        @param value A number of peers.
         """
        self.dlconfig['min_peers'] = value

    def get_min_peers(self):
        """ Returns the minimum number of peers.
        @return A number of peers.
        """
        return self.dlconfig['min_peers']

    def set_http_timeout(self, value):
        """ Number of seconds to wait before assuming that a HTTP connection
        has timed out.
        @param value A number of seconds.
         """
        self.dlconfig['http_timeout'] = value

    def get_http_timeout(self):
        """ Returns the HTTP timeout.
        @return A number of seconds.
        """
        return self.dlconfig['http_timeout']

    def set_check_hashes(self, value):
        """ Whether to check the integrity of the data on disk using the
        hashes from the torrent definition.
        @param value Boolean
        """
        self.dlconfig['check_hashes'] = value

    def get_check_hashes(self):
        """ Returns whether to check hashes.
        @return Boolean. """
        return self.dlconfig['check_hashes']

    def set_alloc_type(self, value):
        """ Set disk-allocation type:
        <pre>
        * DISKALLOC_NORMAL:  Allocates space as data is received
        * DISKALLOC_BACKGROUND: Also adds space in the background
        * DISKALLOC_PREALLOCATE: Reserves space up front (slow)
        * DISKALLOC_SPARSE: Is only for filesystems that support it by default
          (UNIX)
        </pre>
        @param value A DISKALLOC_* policy.
        """
        self.dlconfig['alloc_type'] = value

    def get_alloc_type(self):
        """ Returns the disk-allocation policy.
        @return DISKALLOC_*
        """
        return self.dlconfig['alloc_type']

    def set_alloc_rate(self, value):
        """ Set the rate to allocate space at using background
        allocation (DISKALLOC_BACKGROUND).

        @param value A rate in MB/s.
        """
        self.dlconfig['alloc_rate'] = value

    def get_alloc_rate(self):
        """ Returns the background disk-allocation rate.
        @return A number of megabytes per second.
        """
        return self.dlconfig['alloc_rate']

    def set_buffer_reads(self, value):
        """ Whether to buffer disk reads.
        @param value Boolean
        """
        self.dlconfig['buffer_reads'] = value

    def get_buffer_reads(self):
        """ Returns whether to buffer reads.
        @return Boolean. """
        return self.dlconfig['buffer_reads']

    def set_write_buffer_size(self, value):
        """ The maximum amount of space to use for buffering disk writes
        (0 = disabled).
        @param value A buffer size in megabytes.
        """
        self.dlconfig['write_buffer_size'] = value

    def get_write_buffer_size(self):
        """ Returns the write buffer size.
        @return A number of megabytes.
        """
        return self.dlconfig['write_buffer_size']

    def set_breakup_seed_bitfield(self, value):
        """ Whether to send an incomplete BITFIELD and then fills with HAVE
        messages, in order to get around intellectually-challenged Internet
        Service Provider manipulation.
        @param value Boolean
        """
        self.dlconfig['breakup_seed_bitfield'] = value

    def get_breakup_seed_bitfield(self):
        """ Returns whether to send an incomplete BITFIELD message.
        @return Boolean. """
        return self.dlconfig['breakup_seed_bitfield']

    def set_snub_time(self, value):
        """ Seconds to wait for data to come in over a connection before
        assuming it's semi-permanently choked.
        @param value  A number of seconds.
        """
        self.dlconfig['snub_time'] = value

    def get_snub_time(self):
        """ Returns the snub time.
        @return A number of seconds.
        """
        return self.dlconfig['snub_time']

    def set_rarest_first_cutoff(self, value):
        """ Number of downloads at which to switch from random to rarest first.
        @param value A number of downloads.
        """
        self.dlconfig['rarest_first_cutoff'] = value

    def get_rarest_first_cutoff(self):
        """ Returns the rarest first cutoff.
        @return A number of downloads.
        """
        return self.dlconfig['rarest_first_cutoff']

    def set_rarest_first_priority_cutoff(self, value):
        """ The number of peers which need to have a piece before other
        partials take priority over rarest first policy.
        @param value A number of peers.
        """
        self.dlconfig['rarest_first_priority_cutoff'] = value

    def get_rarest_first_priority_cutoff(self):
        """ Returns the rarest-first priority cutoff.
        @return A number of peers. """
        return self.dlconfig['rarest_first_priority_cutoff']

    def set_min_uploads(self, value):
        """ The number of uploads to fill out to with extra optimistic unchokes.
        @param value A number of uploads.
        """
        self.dlconfig['min_uploads'] = value

    def get_min_uploads(self):
        """ Returns the minimum number of uploads.
        @return A number of uploads. """
        return self.dlconfig['min_uploads']

    def set_max_files_open(self, value):
        """ The maximum number of files to keep open at a time, 0 means no
        limit.
        @param value A number of files.
        """
        self.dlconfig['max_files_open'] = value

    def get_max_files_open(self):
        """ Returns the maximum number of open files.
        @return A number of files. """
        return self.dlconfig['max_files_open']

    def set_round_robin_period(self, value):
        """ The number of seconds between the client's switching upload targets.
        @param value A number of seconds.
        """
        self.dlconfig['round_robin_period'] = value

    def get_round_robin_period(self):
        """ Returns the round-robin period.
        @return A number of seconds. """
        return self.dlconfig['round_robin_period']

    def set_super_seeder(self, value):
        """ whether to use special upload-efficiency-maximizing routines (only
        for dedicated seeds).
        @param value Boolean
        """
        self.dlconfig['super_seeder'] = value

    def get_super_seeder(self):
        """ Returns hether super seeding is enabled.
        @return Boolean. """
        return self.dlconfig['super_seeder']

    def set_security(self, value):
        """ Whether to enable extra security features intended to prevent abuse,
        such as checking for multiple connections from the same IP address.
        @param value Boolean
        """
        self.dlconfig['security'] = value

    def get_security(self):
        """ Returns the security setting.
        @return Boolean. """
        return self.dlconfig['security']

    def set_auto_kick(self, value):
        """ Whether to automatically kick/ban peers that send bad data.
        @param value Boolean
        """
        self.dlconfig['auto_kick'] = value

    def get_auto_kick(self):
        """ Returns whether autokick is enabled.
        @return Boolean. """
        return self.dlconfig['auto_kick']

    def set_double_check_writes(self, value):
        """ Whether to double-check data being written to the disk for errors
        (may increase CPU load).
        @param value Boolean
        """
        self.dlconfig['double_check'] = value

    def get_double_check_writes(self):
        """ Returns whether double-checking on writes is enabled. """
        return self.dlconfig['double_check']

    def set_triple_check_writes(self, value):
        """ Whether to thoroughly check data being written to the disk (may
        slow disk access).
        @param value Boolean """
        self.dlconfig['triple_check'] = value

    def get_triple_check_writes(self):
        """ Returns whether triple-checking on writes is enabled. """
        return self.dlconfig['triple_check']

    def set_lock_files(self, value):
        """ Whether to lock files the Download is working with.
        @param value Boolean """
        self.dlconfig['lock_files'] = value

    def get_lock_files(self):
        """ Returns whether locking of files is enabled. """
        return self.dlconfig['lock_files']

    def set_lock_while_reading(self, value):
        """ Whether to lock access to files being read.
        @param value Boolean
        """
        self.dlconfig['lock_while_reading'] = value

    def get_lock_while_reading(self):
        """ Returns whether locking of files for reading is enabled.
        @return Boolean. """
        return self.dlconfig['lock_while_reading']

    def set_auto_flush(self, value):
        """ Minutes between automatic flushes to disk (0 = disabled).
        @param value A number of minutes.
        """
        self.dlconfig['auto_flush'] = value

    def get_auto_flush(self):
        """ Returns the auto flush interval.
        @return A number of minutes. """
        return self.dlconfig['auto_flush']

    def set_exclude_ips(self, value):
        """ Set a list of IP addresses to be excluded.
        @param value A list of IP addresses in dotted notation.
        """
        self.dlconfig['exclude_ips'] = value

    def get_exclude_ips(self):
        """ Returns the list of excluded IP addresses.
        @return A list of strings. """
        return self.dlconfig['exclude_ips']

    def set_ut_pex_max_addrs_from_peer(self, value):
        """ Maximum number of addresses to accept from peer via the uTorrent
        Peer Exchange extension (0 = disable PEX)
        @param value A number of IP addresses.
        """
        self.dlconfig['ut_pex_max_addrs_from_peer'] = value

    def get_ut_pex_max_addrs_from_peer(self):
        """ Returns the maximum number of IP addresses to accept from a peer
        via ut_pex.
        @return A number of addresses.
        """
        return self.dlconfig['ut_pex_max_addrs_from_peer']

    def set_same_nat_try_internal(self, value):
        """ Whether to try to detect if a peer is behind the same NAT as
        this Session and then establish a connection over the internal
        network
        @param value Boolean
        """
        self.dlconfig['same_nat_try_internal'] = value

    def get_same_nat_try_internal(self):
        """ Returns whether same NAT detection is enabled.
        @return Boolean """
        return self.dlconfig['same_nat_try_internal']

    def set_unchoke_bias_for_internal(self, value):
        """ Amount to add to unchoke score for peers on the internal network.
        @param value A number
        """
        self.dlconfig['unchoke_bias_for_internal'] = value

    def get_unchoke_bias_for_internal(self):
        """ Returns the bias for peers on the internal network.
        @return A number
        """
        return self.dlconfig['unchoke_bias_for_internal']

    # SWIFTPROC
    def set_swift_listen_port(self, port):
        """ Set the UDP port for the swift process
        (download-to-process mapping permitting).
        @param port A port number.
        """
        self.dlconfig['swiftlistenport'] = port

    def get_swift_listen_port(self):
        """ Returns the UDP port of the swift process.

        @return Port number. """
        return self.dlconfig['swiftlistenport']

    def set_swift_cmdgw_listen_port(self, port):
        """ Set the TCP listen port for the CMDGW of the swift process
        (download-to-process mapping permitting).
        @param port A port number.
        """
        self.dlconfig['swiftcmdgwlistenport'] = port

    def get_swift_cmdgw_listen_port(self):
        """ Returns the TCP listen port for the CMDGW of the swift process
        (download-to-process mapping permitting).

        @return Port number. """
        return self.dlconfig['swiftcmdgwlistenport']

    def set_swift_httpgw_listen_port(self, port):
        """ Set the TCP listen port for the CMDGW of the swift process
        (download-to-process mapping permitting).
        @param port A port number.
        """
        self.dlconfig['swifthttpgwlistenport'] = port

    def get_swift_httpgw_listen_port(self):
        """ Returns the TCP listen port for the CMDGW of the swift process.

        @return Port number. """
        return self.dlconfig['swifthttpgwlistenport']

    def set_swift_meta_dir(self, value):
        """ Set the metadir for storing .m* files of this Download.
        @param value An absolutepath.
        """
        self.dlconfig['swiftmetadir'] = value

    def get_swift_meta_dir(self):
        """ Return the metadir for storing .m* files of this Download.
        @return An absolutepath.
        """
        return self.dlconfig['swiftmetadir']


class DownloadStartupConfig(DownloadConfigInterface, Serializable, Copyable):

    """
    (key,value) pair config of per-torrent runtime parameters,
    e.g. destdir, file-allocation policy, etc. Also options to advocate
    torrent, e.g. register in DHT, advertise via Buddycast.

    cf. libtorrent torrent_handle
    """
    def __init__(self, dlconfig=None):
        """ Normal constructor for DownloadStartupConfig (copy constructor
        used internally) """
        DownloadConfigInterface.__init__(self, dlconfig)
    #
    # Class method
    #

    def load(filename):
        """
        Load a saved DownloadStartupConfig from disk.

        @param filename  An absolute Unicode filename
        @return DownloadStartupConfig object
        """
        # Class method, no locking required
        f = open(filename, "rb")
        dlconfig = pickle.load(f)
        dscfg = DownloadStartupConfig(dlconfig)
        f.close()
        return dscfg
    load = staticmethod(load)

    def save(self, filename):
        """ Save the DownloadStartupConfig to disk.
        @param filename  An absolute Unicode filename
        """
        # Called by any thread
        f = open(filename, "wb")
        pickle.dump(self.dlconfig, f)
        f.close()

    #
    # Copyable interface
    #
    def copy(self):
        config = copy.copy(self.dlconfig)
        return DownloadStartupConfig(config)


def get_default_dest_dir():
    """ Returns the default dir to save content to.
    <pre>
    * For Win32/MacOS: Desktop\TriblerDownloads
    * For UNIX:
        If Desktop exists: Desktop\TriblerDownloads
        else: Home\TriblerDownloads
    </pre>
    """
    downloaddir = 'TriblerDownloads'

    if os.path.isdir(downloaddir):
        return os.path.abspath(downloaddir)

    uhome = get_desktop_dir()
    return os.path.join(uhome, downloaddir)

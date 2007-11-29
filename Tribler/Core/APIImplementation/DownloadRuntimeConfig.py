# Written by Arno Bakker 
# see LICENSE.txt for license information

import sys
from traceback import print_exc

from Tribler.Core.DownloadConfig import DownloadConfigInterface


class DownloadRuntimeConfig(DownloadConfigInterface):
    """
    Implements the Tribler.Core.DownloadConfig.DownloadConfigInterface
    
    Use these to change the download config at runtime.
    
    DownloadConfigInterface: All methods called by any thread
    """
    def set_max_speed(self,direct,speed):
        print >>sys.stderr,"Download: set_max_speed",`self.get_def().get_metainfo()['info']['name']`,direct,speed
        #print_stack()
        
        self.dllock.acquire()
        try:
            # Don't need to throw an exception when stopped, we then just save the new value and
            # use it at (re)startup.
            if self.sd is not None:
                set_max_speed_lambda = lambda:self.sd.set_max_speed(direct,speed,None)
                self.session.lm.rawserver.add_task(set_max_speed_lambda,0)
                
            # At the moment we can't catch any errors in the engine that this 
            # causes, so just assume it always works.
            DownloadConfigInterface.set_max_speed(self,direct,speed)
        finally:
            self.dllock.release()

    def get_max_speed(self,direct):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_max_speed(self,direct)
        finally:
            self.dllock.release()

    def set_saveas(self,path):
        raise OperationNotPossibleAtRuntimeException()

    def set_video_start_callback(self,usercallback):
        raise NotYetImplementedException()

    def get_mode(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_mode(self)
        finally:
            self.dllock.release()

    def get_vod_usercallback(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_vod_usercallback(self)
        finally:
            self.dllock.release()

    def set_selected_files(self,files):
        raise OperationNotPossibleAtRuntimeException()

    def get_selected_files(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_selected_files(self)
        finally:
            self.dllock.release()

    def set_max_conns_to_initiate(self,nconns):
        self.dllock.acquire()
        try:
            if self.sd is not None:
                set_max_conns2init_lambda = lambda:self.sd.set_max_conns_to_initiate(nconns,None)
                self.session.lm.rawserver.add_task(set_max_conns2init_lambda,0.0)
            DownloadConfigInterface.set_max_conns_to_initiate(self,nconns)
        finally:
            self.dllock.release()

    def get_max_conns_to_initiate(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_max_conns_to_initiate(self)
        finally:
            self.dllock.release()

    def set_max_conns(self,nconns):
        self.dllock.acquire()
        try:
            if self.sd is not None:
                set_max_conns_lambda = lambda:self.sd.set_max_conns(nconns,None)
                self.session.lm.rawserver.add_task(set_max_conns_lambda,0.0)
            DownloadConfigInterface.set_max_conns(self,nconns)
        finally:
            self.dllock.release()
    
    def get_max_conns(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_max_conns(self)
        finally:
            self.dllock.release()

    #
    # Advanced download parameters
    #
    def set_max_uploads(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_max_uploads(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_max_uploads(self)
        finally:
            self.dllock.release()

    def set_keepalive_interval(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_keepalive_interval(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_keepalive_interval(self)
        finally:
            self.dllock.release()

    def set_download_slice_size(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_download_slice_size(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_download_slice_size(self)
        finally:
            self.dllock.release()

    def set_upload_unit_size(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_upload_unit_size(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_upload_unit_size(self)
        finally:
            self.dllock.release()

    def set_request_backlog(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_request_backlog(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_request_backlog(self)
        finally:
            self.dllock.release()

    def set_max_message_length(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_max_message_length(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_max_message_length(self)
        finally:
            self.dllock.release()

    def set_max_slice_length(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_max_slice_length(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_max_slice_length(self)
        finally:
            self.dllock.release()

    def set_max_rate_period(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_max_rate_period(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_max_rate_period(self)
        finally:
            self.dllock.release()

    def set_upload_rate_fudge(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_upload_rate_fudge(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_upload_rate_fudge(self)
        finally:
            self.dllock.release()

    def set_tcp_ack_fudge(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tcp_ack_fudge(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_tcp_ack_fudge(self)
        finally:
            self.dllock.release()

    def set_rerequest_interval(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_rerequest_interval(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_rerequest_interval(self)
        finally:
            self.dllock.release()

    def set_min_peers(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_min_peers(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_min_peers(self)
        finally:
            self.dllock.release()

    def set_http_timeout(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_http_timeout(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_http_timeout(self)
        finally:
            self.dllock.release()

    def set_check_hashes(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_check_hashes(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_check_hashes(self)
        finally:
            self.dllock.release()

    def set_alloc_type(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_alloc_type(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_alloc_type(self)
        finally:
            self.dllock.release()

    def set_alloc_rate(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_alloc_rate(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_alloc_rate(self)
        finally:
            self.dllock.release()

    def set_buffer_reads(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_buffer_reads(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_buffer_reads(self)
        finally:
            self.dllock.release()

    def set_write_buffer_size(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_write_buffer_size(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_write_buffer_size(self)
        finally:
            self.dllock.release()

    def set_breakup_seed_bitfield(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_breakup_seed_bitfield(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_breakup_seed_bitfield(self)
        finally:
            self.dllock.release()

    def set_snub_time(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_snub_time(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_snub_time(self)
        finally:
            self.dllock.release()

    def set_rarest_first_cutoff(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_rarest_first_cutoff(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_rarest_first_cutoff(self)
        finally:
            self.dllock.release()

    def set_rarest_first_priority_cutoff(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_rarest_first_priority_cutoff(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_rarest_first_priority_cutoff(self)
        finally:
            self.dllock.release()

    def set_min_uploads(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_min_uploads(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_min_uploads(self)
        finally:
            self.dllock.release()

    def set_max_files_open(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_max_files_open(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_max_files_open(self)
        finally:
            self.dllock.release()

    def set_round_robin_period(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_round_robin_period(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_round_robin_period(self)
        finally:
            self.dllock.release()

    def set_super_seeder(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_super_seeder(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_super_seeder(self)
        finally:
            self.dllock.release()

    def set_security(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_security(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_security(self)
        finally:
            self.dllock.release()

    def set_auto_kick(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_auto_kick(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_auto_kick(self)
        finally:
            self.dllock.release()

    def set_double_check_writes(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_double_check_writes(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_double_check(self)
        finally:
            self.dllock.release()

    def set_triple_check_writes(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_triple_check_writes(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_triple_check(self)
        finally:
            self.dllock.release()

    def set_lock_files(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_lock_files(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_lock_files(self)
        finally:
            self.dllock.release()

    def set_lock_while_reading(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_lock_while_reading(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_lock_while_reading(self)
        finally:
            self.dllock.release()

    def set_auto_flush(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_auto_flush(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_auto_flush(self)
        finally:
            self.dllock.release()

    def set_exclude_ips(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_exclude_ips(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_exclude_ips(self)
        finally:
            self.dllock.release()

    def set_ut_pex_max_addrs_from_peer(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_ut_pex_max_addrs_from_peer(self):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_ut_pex_max_addrs_from_peer(self)
        finally:
            self.dllock.release()


# Written by Arno Bakker
# Updated by George Milescu
# see LICENSE.txt for license information

from __future__ import with_statement
import sys
from traceback import print_exc

from Tribler.Core.exceptions import *
from Tribler.Core.SessionConfig import SessionConfigInterface

# 10/02/10 Boudewijn: pylint points out that member variables used in
# SessionRuntimeConfig do not exist.  This is because they are set in
# Tribler.Core.Session which is a subclass of SessionRuntimeConfig.
#
# We disable this error
# pylint: disable-msg=E1101

class SessionRuntimeConfig(SessionConfigInterface):
    """
    Implements the Tribler.Core.API.SessionConfigInterface

    Use these to change the session config at runtime.
    """
    def set_state_dir(self, statedir):
        raise OperationNotPossibleAtRuntimeException()

    def get_state_dir(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_state_dir(self)
        finally:
            self.sesslock.release()

    def set_install_dir(self, statedir):
        raise OperationNotPossibleAtRuntimeException()

    def get_install_dir(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_install_dir(self)
        finally:
            self.sesslock.release()

    def set_permid_keypair_filename(self, keypair):
        raise OperationNotPossibleAtRuntimeException()

    def get_permid_keypair_filename(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_permid_keypair_filename(self)
        finally:
            self.sesslock.release()

    def set_listen_port(self, port):
        raise OperationNotPossibleAtRuntimeException()

    def get_listen_port(self):
        # To protect self.sessconfig
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_listen_port(self)
        finally:
            self.sesslock.release()

    def get_video_analyser_path(self):
        # To protect self.sessconfig
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_video_analyser_path(self)
        finally:
            self.sesslock.release()

    def set_tracker_ip(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_ip(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_ip(self)
        finally:
            self.sesslock.release()

    def set_bind_to_addresses(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_bind_to_addresses(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_bind_to_addresses(self)
        finally:
            self.sesslock.release()

    def set_autoclose_timeout(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_autoclose_timeout(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_autoclose_timeout(self)
        finally:
            self.sesslock.release()

    def set_autoclose_check_interval(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_autoclose_check_interval(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_autoclose_check_interval(self)
        finally:
            self.sesslock.release()

    def set_megacache(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_megacache(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_megacache(self)
        finally:
            self.sesslock.release()

    def set_overlay(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_overlay(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_overlay(self)
        finally:
            self.sesslock.release()

    def set_buddycast(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_buddycast(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_buddycast(self)
        finally:
            self.sesslock.release()

    def set_start_recommender(self, value):
        self.sesslock.acquire()
        try:
            from Tribler.Core.Overlay.OverlayThreadingBridge import OverlayThreadingBridge

            SessionConfigInterface.set_start_recommender(self, value)
            olbridge = OverlayThreadingBridge.getInstance()
            task = lambda:self.olthread_set_start_recommender(value)
            olbridge.add_task(task, 0)
        finally:
            self.sesslock.release()

    def olthread_set_start_recommender(self, value):
        from Tribler.Core.BuddyCast.buddycast import BuddyCastFactory
        bcfac = BuddyCastFactory.getInstance()
        if value:
            bcfac.restartBuddyCast()
        else:
            bcfac.pauseBuddyCast()

    def get_start_recommender(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_start_recommender(self)
        finally:
            self.sesslock.release()

    # ProxyService_
    #
    def set_proxyservice_status(self, value):
        """ Set the status of the proxyservice (on or off).

        ProxyService off means the current node could not be used as a proxy. ProxyService on means other nodes will be able to use it as a proxy.

        @param value: one of the possible two values: PROXYSERVICE_OFF, PROXYSERVICE_ON
        """
        self.sesslock.acquire()
        try:
            SessionConfigInterface.set_proxyservice_status(self, value)
        finally:
            self.sesslock.release()

    def get_proxyservice_status(self):
        """ Returns the status of the proxyservice (on or off).
        @return: one of the possible two values: PROXYSERVICE_OFF, PROXYSERVICE_ON
        """
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_proxyservice_status(self)
        finally:
            self.sesslock.release()

    def set_proxyservice_dir(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_proxyservice_dir(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_proxyservice_dir(self)
        finally:
            self.sesslock.release()
    #
    # _ProxyService



    def set_torrent_collecting(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_torrent_collecting(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_torrent_collecting(self)
        finally:
            self.sesslock.release()


    def set_torrent_collecting_dir(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_torrent_collecting_dir(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_torrent_collecting_dir(self)
        finally:
            self.sesslock.release()

    def set_overlay_log(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_overlay_log(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_overlay_log(self)
        finally:
            self.sesslock.release()

    def set_buddycast_interval(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_buddycast_interval(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_buddycast_interval(self)
        finally:
            self.sesslock.release()

    def set_torrent_collecting_max_torrents(self, value):
        self.sesslock.acquire()
        try:
            from Tribler.Core.Overlay.OverlayThreadingBridge import OverlayThreadingBridge

            SessionConfigInterface.set_torrent_collecting_max_torrents(self, value)
            olbridge = OverlayThreadingBridge.getInstance()
            task = lambda:self.olthread_set_torrent_collecting_max_torrents(value)
            olbridge.add_task(task, 0)
        finally:
            self.sesslock.release()

    def olthread_set_torrent_collecting_max_torrents(self, value):
        from Tribler.Core.Overlay.MetadataHandler import MetadataHandler
        mh = MetadataHandler.getInstance()
        mh.set_overflow(value)
        mh.delayed_check_overflow(2)


    def get_torrent_collecting_max_torrents(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_torrent_collecting_max_torrents(self)
        finally:
            self.sesslock.release()

    def set_buddycast_max_peers(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_buddycast_max_peers(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_buddycast_max_peers(self)
        finally:
            self.sesslock.release()

    def set_torrent_collecting_rate(self, value):
        self.sesslock.acquire()
        try:
            from Tribler.Core.Overlay.OverlayThreadingBridge import OverlayThreadingBridge

            SessionConfigInterface.set_torrent_collecting_rate(self, value)
            olbridge = OverlayThreadingBridge.getInstance()
            task = lambda:self.olthread_set_torrent_collecting_rate(value)
            olbridge.add_task(task, 0)
        finally:
            self.sesslock.release()

    def olthread_set_torrent_collecting_rate(self, value):
        from Tribler.Core.Overlay.MetadataHandler import MetadataHandler
        mh = MetadataHandler.getInstance()
        mh.set_rate(value)

    def get_torrent_collecting_rate(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_torrent_collecting_rate(self)
        finally:
            self.sesslock.release()

    def set_torrent_checking(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_torrent_checking(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_torrent_checking(self)
        finally:
            self.sesslock.release()

    def set_torrent_checking_period(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_torrent_checking_period(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_torrent_checking_period(self)
        finally:
            self.sesslock.release()

    def set_dialback(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_dialback(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_dialback(self)
        finally:
            self.sesslock.release()

    def set_stop_collecting_threshold(self, value):
        self.sesslock.acquire()
        try:
            from Tribler.Core.Overlay.OverlayThreadingBridge import OverlayThreadingBridge

            SessionConfigInterface.set_stop_collecting_threshold(self, value)
            olbridge = OverlayThreadingBridge.getInstance()
            task = lambda:self.olthread_set_stop_collecting_threshold(value)
            olbridge.add_task(task, 0)
        finally:
            self.sesslock.release()

    def olthread_set_stop_collecting_threshold(self, value):
        from Tribler.Core.Overlay.MetadataHandler import MetadataHandler
        mh = MetadataHandler.getInstance()
        mh.set_min_free_space(value)
        mh.delayed_check_free_space(2)

    def get_stop_collecting_threshold(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_stop_collecting_threshold(self)
        finally:
            self.sesslock.release()

    def set_internal_tracker(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_internal_tracker(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_internal_tracker(self)
        finally:
            self.sesslock.release()

    def set_internal_tracker_url(self, value):
        raise OperationNotPossibleAtRuntimeException()

    # def get_internal_tracker_url(self):
        """ Implemented in Session.py """

    def set_mainline_dht(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_mainline_dht(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_mainline_dht(self)
        finally:
            self.sesslock.release()

    def set_nickname(self, value):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.set_nickname(self, value)
        finally:
            self.sesslock.release()

    def get_nickname(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_nickname(self)
        finally:
            self.sesslock.release()

    def set_mugshot(self, value, mime='image/jpeg'):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.set_mugshot(self, value, mime)
        finally:
            self.sesslock.release()

    def get_mugshot(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_mugshot(self)
        finally:
            self.sesslock.release()


    def set_tracker_dfile(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_dfile(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_dfile(self)
        finally:
            self.sesslock.release()

    def set_tracker_dfile_format(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_dfile_format(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_dfile_format(self)
        finally:
            self.sesslock.release()

    def set_tracker_socket_timeout(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_socket_timeout(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_socket_timeout(self)
        finally:
            self.sesslock.release()

    def set_tracker_save_dfile_interval(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_save_dfile_interval(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_save_dfile_interval(self)
        finally:
            self.sesslock.release()

    def set_tracker_timeout_downloaders_interval(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_timeout_downloaders_interval(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_timeout_downloaders_interval(self)
        finally:
            self.sesslock.release()

    def set_tracker_reannounce_interval(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_reannounce_interval(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_reannounce_interval(self)
        finally:
            self.sesslock.release()

    def set_tracker_response_size(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_response_size(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_response_size(self)
        finally:
            self.sesslock.release()

    def set_tracker_timeout_check_interval(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_timeout_check_interval(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_timeout_check_interval(self)
        finally:
            self.sesslock.release()

    def set_tracker_nat_check(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_nat_check(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_nat_check(self)
        finally:
            self.sesslock.release()

    def set_tracker_log_nat_checks(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_log_nat_checks(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_log_nat_checks(self)
        finally:
            self.sesslock.release()

    def set_tracker_min_time_between_log_flushes(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_min_time_between_log_flushes(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_min_time_between_log_flushes(self)
        finally:
            self.sesslock.release()

    def set_tracker_min_time_between_cache_refreshes(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_min_time_between_cache_refreshes(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_min_time_between_cache_refreshes(self)
        finally:
            self.sesslock.release()

    def set_tracker_allowed_dir(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_allowed_dir(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_allowed_dir(self)
        finally:
            self.sesslock.release()

    def set_tracker_allowed_list(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_allowed_list(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_allowed_list(self)
        finally:
            self.sesslock.release()

    def set_tracker_allowed_controls(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_allowed_controls(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_allowed_controls(self)
        finally:
            self.sesslock.release()

    def set_tracker_multitracker_enabled(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_multitracker_enabled(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_multitracker_enabled(self)
        finally:
            self.sesslock.release()

    def set_tracker_multitracker_allowed(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_multitracker_allowed(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_multitracker_allowed(self)
        finally:
            self.sesslock.release()

    def set_tracker_multitracker_reannounce_interval(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_multitracker_reannounce_interval(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_multitracker_reannounce_interval(self)
        finally:
            self.sesslock.release()

    def set_tracker_multitracker_maxpeers(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_multitracker_maxpeers(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_multitracker_maxpeers(self)
        finally:
            self.sesslock.release()

    def set_tracker_aggregate_forward(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_aggregate_forward(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_aggregate_forward(self)
        finally:
            self.sesslock.release()

    def set_tracker_aggregator(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_aggregator(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_aggregator(self)
        finally:
            self.sesslock.release()

    def set_tracker_hupmonitor(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_hupmonitor(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_hupmonitor(self)
        finally:
            self.sesslock.release()

    def set_tracker_multitracker_http_timeout(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_multitracker_http_timeout(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_multitracker_http_timeout(self)
        finally:
            self.sesslock.release()

    def set_tracker_parse_dir_interval(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_parse_dir_interval(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_parse_dir_interval(self)
        finally:
            self.sesslock.release()

    def set_tracker_show_infopage(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_show_infopage(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_show_infopage(self)
        finally:
            self.sesslock.release()

    def set_tracker_infopage_redirect(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_infopage_redirect(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_infopage_redirect(self)
        finally:
            self.sesslock.release()

    def set_tracker_show_names(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_show_names(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_show_names(self)
        finally:
            self.sesslock.release()

    def set_tracker_favicon(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_favicon(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_favicon(self)
        finally:
            self.sesslock.release()

    def set_tracker_allowed_ips(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_allowed_ips(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_allowed_ips(self)
        finally:
            self.sesslock.release()

    def set_tracker_banned_ips(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_banned_ips(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_banned_ips(self)
        finally:
            self.sesslock.release()

    def set_tracker_only_local_override_ip(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_only_local_override_ip(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_only_local_override_ip(self)
        finally:
            self.sesslock.release()

    def set_tracker_logfile(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_logfile(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_logfile(self)
        finally:
            self.sesslock.release()

    def set_tracker_allow_get(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_allow_get(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_allow_get(self)
        finally:
            self.sesslock.release()

    def set_tracker_keep_dead(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_keep_dead(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_keep_dead(self)
        finally:
            self.sesslock.release()

    def set_tracker_scrape_allowed(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_tracker_scrape_allowed(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_tracker_scrape_allowed(self)
        finally:
            self.sesslock.release()

    def set_overlay_max_message_length(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_overlay_max_message_length(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_overlay_max_message_length(self)
        finally:
            self.sesslock.release()

    def set_buddycast_collecting_solution(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_buddycast_collecting_solution(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_buddycast_collecting_solution(self)
        finally:
            self.sesslock.release()

    def set_peer_icon_path(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_peer_icon_path(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_peer_icon_path(self)
        finally:
            self.sesslock.release()

    #
    # NAT Puncturing servers information setting/retrieval
    #
    def set_puncturing_private_port(self, puncturing_private_port):
        raise OperationNotPossibleAtRuntimeException()

    #
    # Local Peer Discovery using IP Multicast
    #
    def set_multicast_local_peer_discovery(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_multicast_local_peer_discovery(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_multicast_local_peer_discovery(self)
        finally:
            self.sesslock.release()

    #
    # SWIFTPROC
    #
    def set_swift_proc(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_swift_proc(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_swift_proc(self)
        finally:
            self.sesslock.release()


    def set_swift_path(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_swift_path(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_swift_path(self)
        finally:
            self.sesslock.release()


    def set_swift_cmd_listen_port(self, port):
        raise OperationNotPossibleAtRuntimeException()

    def get_swift_cmd_listen_port(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_swift_cmd_listen_port(self)
        finally:
            self.sesslock.release()


    def set_swift_downloads_per_process(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_swift_downloads_per_process(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_swift_downloads_per_process(self)
        finally:
            self.sesslock.release()

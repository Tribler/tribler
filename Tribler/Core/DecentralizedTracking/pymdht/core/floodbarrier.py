# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

"""
Floodbarrier is a protection mechanism which protects us from
host processing too many messages from a single host.

"""

import ptime as time
import collections
import logging
import logging_conf

logger = logging.getLogger('dht')


CHECKING_PERIOD = 2  # seconds
MAX_PACKETS_PER_PERIOD = 10
BLOCKING_PERIOD = 100  # seconds


class HalfPeriodRegister(object):

    """Helper class. Not meant to be used outside this module"""

    def __init__(self):
        self.ip_dict = {}

    def get_num_packets(self, ip):
        return self.ip_dict.get(ip, 0)

    def register_ip(self, ip):
        self.ip_dict[ip] = self.ip_dict.get(ip, 0) + 1


class FloodBarrier(object):

    """
    Object which keeps track of packets received from different
    hosts. Default values are coded but users can choose their own.
    The main function is ip_blocked().

    """

    def __init__(self, checking_period=CHECKING_PERIOD,
                 max_packets_per_period=MAX_PACKETS_PER_PERIOD,
                 blocking_period=BLOCKING_PERIOD):
        self.checking_period = checking_period
        self.max_packets_per_period = max_packets_per_period
        self.blocking_period = blocking_period

        self.last_half_period_time = time.time()
        self.ip_registers = [HalfPeriodRegister(), HalfPeriodRegister()]
        self.blocked_ips = {}

    def ip_blocked(self, ip):
        """
        Register that a packet has been received from the given IP and return
        whether the host is blocked and, hence, the packet should be dropped

        """
        current_time = time.time()
        if current_time > self.last_half_period_time + self.checking_period / 2:
            self.half_period_timeout = current_time
            self.ip_registers = [self.ip_registers[1], HalfPeriodRegister()]
            if current_time > self.last_half_period_time + self.checking_period:
                self.ip_registers = [self.ip_registers[1], HalfPeriodRegister()]
        self.ip_registers[1].register_ip(ip)
        num_packets = self.ip_registers[0].get_num_packets(ip) + \
            self.ip_registers[1].get_num_packets(ip)
        if num_packets > self.max_packets_per_period:
            logger.debug('Got %d packets: blocking %r...' % (
                num_packets, ip))
            self.blocked_ips[ip] = current_time + self.blocking_period
            return True
        # At this point there are no enough packets to block ip (in current
        # period). Now, we need to check whether the ip is currently blocked
        if ip in self.blocked_ips:
            logger.debug('Ip %r (%d) currently blocked' % (ip,
                                                           num_packets))
            if current_time > self.blocked_ips[ip]:
                logger.debug(
                    'Block for %r (%d) has expired: unblocking...' %
                    (ip, num_packets))
                # Blocking period already expired
                del self.blocked_ips[ip]
                return False
            else:
                # IP is currently blocked (block hasn't expired)
                return True
        else:

            # IP is not blocked
            return False

# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import sys

import logging

import message
import identifier
import ptime as time

logger = logging.getLogger('dht')


class Query(object):

    def __init__(self, msg, dstnode, lookup_obj=None):
        self.tid = None
        self.query_ts = None
        self.msg = msg
        self.dstnode = dstnode
        self.lookup_obj = lookup_obj
        self.got_response = False
        self.got_error = False

    def on_response_received(self, response_msg):
        self.rtt = time.time() - self.query_ts
        if not self.dstnode.id:
            self.dstnode.id = response_msg.sender_id
        self.got_response = True

    def on_error_received(self, error_msg):
        self.rtt = time.time() - self.query_ts
        self.got_error = True
        
    def matching_tid(self, response_tid):
        return message.matching_tid(self.tid, response_tid)

    
class Querier(object):

    def __init__(self, my_id):
        self.my_id = my_id
        #TODO: Shouldn't pending be protected by a lock???
        self.pending = {} # collections.defaultdict(list)
        self._tid = [0, 0]

    def _next_tid(self):
        #TODO: move to message?
        current_tid_str = ''.join([chr(c) for c in self._tid])
        self._tid[0] = (self._tid[0] + 1) % 256
        if self._tid[0] == 0:
            self._tid[1] = (self._tid[1] + 1) % 256
        return current_tid_str # raul: yield created trouble

    def register_query(self, query, timeout_task):
        query.tid = self._next_tid()
        logger.debug('sending to node: %r\n%r' % (query.dstnode, query.msg))
        query.timeout_task = timeout_task
        query.query_ts = time.time()
        # if node is not in the dictionary, it will create an empty list
        self.pending.setdefault(query.dstnode.addr, []).append(query)
        bencoded_msg = query.msg.encode(query.tid)
        return bencoded_msg

    def on_response_received(self, response_msg, addr):
        # message already sanitized by IncomingMsg
        logger.debug('response received: %s' % repr(response_msg))
        try:
            addr_query_list = self.pending[addr]
        except (KeyError):
            logger.warning('No pending queries for %s', addr)
            return # Ignore response
        # There are pending queries from node (let's find the right one (TID)
        query_found = False
        for query_index, query in enumerate(addr_query_list):
            logger.debug('response node: %s, query:\n(%s, %s)' % (
                `addr`,
                `query.tid`,
                `query.msg.query`))
            if query.matching_tid(response_msg.tid):
                query_found = True
                break
        if not query_found:
            logger.warning('No query for this response\n%s\nsource: %s' % (
                response_msg, addr))
            return # ignore response 
        # This response matches query. Notify query.
        query.on_response_received(response_msg)
        return query
        # keep the query around (the timeout will delete it)

    def on_error_received(self, error_msg, addr):
        logger.warning('Error message received:\n%s\nSource: %s',
                        `error_msg`,
                        `addr`)
        # TODO2: find query (with TID)
        # and fire query.on_error_received(error_msg)

    def on_timeout(self, addr):
        addr_query_list = self.pending[addr]
        query = addr_query_list.pop(0)
        if not addr_query_list:
            # The list is empty. Remove the whole list.
            del self.pending[addr]
        if not query.got_response and not query.got_error:
            return query

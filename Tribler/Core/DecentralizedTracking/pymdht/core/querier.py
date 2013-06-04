# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

"""
The 'querier' module contains the tools necessary to keep track of sent
queries while waiting for responses.

When a MDHT node receives a response, the response does not contain
information regarding the query being responded. Instead, queries and
responses carry a transaction id (tid) field to be able to match a response
with its related query.

In order to be able to recover related queries, queries need to be stored upon
departure. Additionally, stale queries ---those which have not received a
response for a given period of time (timeout)--- need to be detected and dealt
with.

"""
import sys

import logging

import message
import identifier
import ptime as time

logger = logging.getLogger('dht')

TIMEOUT_DELAY = 2


class Querier(object):

    """
    A Querier object keeps a registry of sent queries while waiting for
    responses.

    """
    def __init__(self):  # , my_id):
#        self.my_id = my_id
        self._pending = {}
        self._timeouts = []
        self._tid = [0, 0]

    def _next_tid(self):
        # TODO: move to message?
        current_tid_str = ''.join([chr(c) for c in self._tid])
        self._tid[0] = (self._tid[0] + 1) % 256
        if self._tid[0] == 0:
            self._tid[1] = (self._tid[1] + 1) % 256
        return current_tid_str  # raul: yield created trouble

    def register_queries(self, queries):
        """
        A Querier object keeps a registry of sent queries while waiting for
        responses.

        """
        assert len(queries)
        datagrams = []
        current_ts = time.time()
        timeout_ts = current_ts + TIMEOUT_DELAY
        for i, query in enumerate(queries):
            msg = query
            tid = self._next_tid()
            logger.debug('registering query %d to node: %r\n%r' % (i,
                                                                   query.dst_node,
                                                                   msg))
            self._timeouts.append((timeout_ts, msg))
            # if node is not in the dictionary, it will create an empty list
            self._pending.setdefault(query.dst_node.addr, []).append(msg)
            datagrams.append(message.Datagram(
                msg.stamp(tid),
                query.dst_node.addr))
        return timeout_ts, datagrams

    def get_related_query(self, response_msg):
        """
        Return the message.OutgoingQueryBase object related to the
        'response\_msg' provided. Return None if no related query is found.

        """
        # message already sanitized by IncomingMsg
        if response_msg.type == message.RESPONSE:
            logger.debug('response received: %s' % repr(response_msg))
        elif response_msg.type == message.ERROR:
            logger.warning('Error message received:\n%s\nSource: %s',
                           repr(response_msg),
                           repr(response_msg.src_addr))
        else:
            raise Exception('response_msg must be response or error')
        related_query = self._find_related_query(response_msg)
        if not related_query:
            logger.warning('No query for this response\n%s\nsource: %s' % (
                response_msg, response_msg.src_addr))
        return related_query

    def get_timeout_queries(self):
        """
        Return a tupla with two items: (1) timestamp for next timeout, (2)
        list of message.OutgoingQueryBase objects of those queries that have
        timed-out.

        """
        current_ts = time.time()
        timeout_queries = []
        while self._timeouts:
            timeout_ts, query = self._timeouts[0]
            if current_ts < timeout_ts:
                next_timeout_ts = timeout_ts
                break
            self._timeouts = self._timeouts[1:]
            addr_query_list = self._pending[query.dst_node.addr]
            popped_query = addr_query_list.pop(0)
            assert query == popped_query
            if not addr_query_list:
                # The list is empty. Remove the whole list.
                del self._pending[query.dst_node.addr]
            if not query.got_response:
                timeout_queries.append(query)
        if not self._timeouts:
            next_timeout_ts = current_ts + TIMEOUT_DELAY
        return next_timeout_ts, timeout_queries

    def _find_related_query(self, msg):
        addr = msg.src_addr
        try:
            addr_query_list = self._pending[addr]
        except (KeyError):
            logger.warning('No pending queries for %s', addr)
            return  # Ignore response
        for related_query in addr_query_list:
            if related_query.match_response(msg):
                logger.debug(
                    'response node: %s, related query: (%s), delay %f s. %r' % (
                        repr(addr),
                        repr(related_query.query),
                        time.time() - related_query.sending_ts,
                        related_query.lookup_obj))
                # Do not delete this query (the timeout will delete it)
                return related_query

# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import sys

from utils import log

import message
import identifier

TIMEOUT_DELAY = 3

class Query(object):

    def __init__(self, tid, query_type, node_,
                 on_response_f, on_error_f, on_timeout_f,
                 notify_routing_m_on_response_f,
                 notify_routing_m_on_error_f,
                 notify_routing_m_on_timeout_f,
                 notify_routing_m_on_nodes_found_f):
        assert on_response_f
        assert on_error_f
        assert on_timeout_f
        #assert notify_routing_m_on_response_f
        #assert notify_routing_m_on_error_f
        #assert notify_routing_m_on_timeout_f
        #assert notify_routing_m_on_nodes_found_f
        
        self.tid = tid
        self.query = query_type
        self.node = node_
        self.on_response_f = on_response_f
        self.on_error_f = on_error_f
        self.on_timeout_f = on_timeout_f
        self.notify_routing_m_on_response_f = \
            notify_routing_m_on_response_f
        self.notify_routing_m_on_error_f = \
            notify_routing_m_on_error_f
        self.notify_routing_m_on_timeout_f = \
            notify_routing_m_on_timeout_f
        self.notify_routing_m_on_nodes_found_f = \
            notify_routing_m_on_nodes_found_f
        self.timeout_task = None

    def on_response_received(self, response_msg):
        try:
            response_msg.sanitize_response(self.query)
        except (message.MsgError):
            log.exception(
                "We don't like dirty reponses: %r|nresponse ignored"
                % response_msg)
            return # Response ignored 
        self.node.is_ns = response_msg.ns_node
        if self.node.id:
            if response_msg.sender_id != self.node.id:
                return # Ignore response
        else:
            self.node.id = response_msg.sender_id
        #TODO2: think whether late responses should be accepted
        if self.timeout_task.cancelled:
            log.warning(
                "Response recevived but it's too late!!\n%r, %r" %
                (response_msg,
                self.timeout_task))
            return # Ignore response
        self.timeout_task.cancel()
        nodes = []
        try:
            nodes.extend(response_msg.nodes)
        except (AttributeError):
            pass
        try:
            nodes.extend(response_msg.nodes2)
        except (AttributeError):
            pass
        # Notify routing manager (if nodes found).
        # Do not notify when the query was a GET_PEERS because
        # the lookup is in progress and the routing_m shouldn't
        # generate extra traffic.
        if self.query == message.FIND_NODE and \
                nodes and self.notify_routing_m_on_nodes_found_f:
            self.notify_routing_m_on_nodes_found_f(nodes)
        # Notify routing manager (response)
        self.node.is_ns = response_msg.ns_node
        if self.notify_routing_m_on_response_f:
            self.notify_routing_m_on_response_f(self.node)
        # Do callback to whomever did the query
        self.on_response_f(response_msg, self.node)
        return True # the response was fine

    def on_error_received(self, error_msg):
        self.on_error_f(error_msg, self.node)
        if self.notify_routing_m_on_error_f:
            self.notify_routing_m_on_error_f(self.node)

    def on_timeout(self):
        # Careful here. Node might not have ID.
        self.on_timeout_f(self.node)
        if self.notify_routing_m_on_timeout_f:
            self.notify_routing_m_on_timeout_f(self.node)

    def matching_tid(self, response_tid):
        return message.matching_tid(self.tid, response_tid)

class Querier(object):

    def __init__(self, rpc_m, my_id, default_timeout_delay=TIMEOUT_DELAY):
        self.rpc_m = rpc_m
        self.my_id = my_id
        self.default_timeout_delay = default_timeout_delay
        self.rpc_m.add_msg_callback(message.RESPONSE, self.on_response_received)
        self.rpc_m.add_msg_callback(message.ERROR, self.on_error_received)
        self.pending = {} # collections.defaultdict(list)
        self._tid = [0, 0]
        self.notify_routing_m_on_response = None
        self.notify_routing_m_on_error = None
        self.notify_routing_m_on_timeout = None
        self.notify_routing_m_on_nodes_found = None

    def _next_tid(self):
        current_tid_str = ''.join([chr(c) for c in self._tid])
        self._tid[0] = (self._tid[0] + 1) % 256
        if self._tid[0] == 0:
            self._tid[1] = (self._tid[1] + 1) % 256
        return current_tid_str # raul: yield created trouble

    def set_on_response_received_callback(self, callback_f):
        self.notify_routing_m_on_response = callback_f

    def set_on_error_received_callback(self, callback_f):
        self.notify_routing_m_on_error = callback_f
        
    def set_on_timeout_callback(self, callback_f):
        self.notify_routing_m_on_timeout = callback_f
    
    def set_on_nodes_found_callback(self, callback_f):
        self.notify_routing_m_on_nodes_found = callback_f
    
    def send_query(self, msg, node_, on_response_f,
                   on_timeout_f, on_error_f,
                   timeout_delay=None):
        timeout_delay = timeout_delay or self.default_timeout_delay
        tid = self._next_tid()
        log.debug('sending to node: %r\n%r' % (node_, msg))
        query = Query(tid, msg.query, node_,
                      on_response_f, on_error_f,
                      on_timeout_f,
                      self.notify_routing_m_on_response,
                      self.notify_routing_m_on_error,
                      self.notify_routing_m_on_timeout,
                      self.notify_routing_m_on_nodes_found) 
        # if node is not in the dictionary, it will create an empty list
        self.pending.setdefault(node_.addr, []).append(query)
        bencoded_msg = msg.encode(tid)
        query.timeout_task = self.rpc_m.get_timeout_task(node_.addr,
                                                    timeout_delay,
                                                    self.on_timeout)
        self.rpc_m.send_msg_to(bencoded_msg, node_.addr)
        return query

    def send_query_later(self, delay, msg, node_, on_response_f,
                         on_timeout_f, on_error_f,
                         timeout_delay=None):
        return self.rpc_m.call_later(delay, self.send_query,
                                     msg, node_,
                                     on_response_f,
                                     on_timeout_f,
                                     on_error_f,
                                     timeout_delay)
        
    def on_response_received(self, response_msg, addr):
        # TYPE and TID already sanitized by rpc_manager
        log.debug('response received: %s' % repr(response_msg))
        try:
            addr_query_list = self.pending[addr]
        except (KeyError):
            log.warning('No pending queries for %s', addr)
            return # Ignore response
        # There are pending queries from node (let's find the right one (TID)
        query_found = False
        for query_index, query in enumerate(addr_query_list):
            log.debug('response node: %s, query:\n(%s, %s)' % (
                `addr`,
                `query.tid`,
                `query.query`))
            if query.matching_tid(response_msg.tid):
                query_found = True
                break
        if not query_found:
            log.warning('No query for this response\n%s\nsource: %s' % (
                response_msg, addr))
            return # ignore response 
        # This response matches query. Trigger query's callback
        response_is_ok = query.on_response_received(response_msg)
        if response_is_ok:
            # Remove this query from pending
            if len(addr_query_list) == 1:
                # There is one item in the list. Remove the whole list.
                del self.pending[addr]
            else:
                del addr_query_list[query_index]
        else:
            log.warning('Bad response from %r\n%r' % (addr,
                                                          response_msg))

    def on_error_received(self, error_msg, addr):
        log.warning('Error message received:\n%s\nSource: %s',
                        `error_msg`,
                        `addr`)
        # TODO2: find query (with TID)
        # and fire query.on_error_received(error_msg)

    def on_timeout(self, addr):
        #try
        addr_query_list = self.pending[addr]
        #except (KeyError):
        #    log.warning('No pending queries for %s', addr)
        #    return # Ignore response
        # There are pending queries from node (oldest query)
        query = addr_query_list.pop(0)
        # Remove this query from pending
        if not addr_query_list:
            # The list is empty. Remove the whole list.
            del self.pending[addr]
        # Trigger query's on_timeout callback
        query.on_timeout()

        
    def stop(self):
        self.rpc_m.stop()


class QuerierMock(Querier):

    def __init__(self, my_id):
        import minitwisted
        import rpc_manager
        import test_const as tc
        reactor = minitwisted.ThreadedReactorMock()
        rpc_m = rpc_manager.RPCManager(reactor, 1)
        Querier.__init__(self, rpc_m, my_id)


    

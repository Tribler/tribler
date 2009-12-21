# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

from utils import log

import message


class RPCManager(object):

    def __init__(self, reactor, port):
        self.reactor = reactor
        self.reactor.listen_udp(port, self._on_datagram_received)
        self.msg_callbacks_d = {}
        self.timeout_callbacks = []

    def get_timeout_task(self, addr, timeout_delay, timeout_callback):
        timeout_callbacks = self.timeout_callbacks + [timeout_callback]
        return self.reactor.call_later(timeout_delay,
                                               timeout_callbacks, addr)
    def send_msg_to(self, bencoded_msg, addr):
        """This must be called right after get_timeout_task
        (when timeout is needed).
        """
        self.reactor.sendto(bencoded_msg, addr)
    
    def call_later(self, delay, callback_fs, *args, **kwargs):
        return self.reactor.call_later(delay, callback_fs, *args, **kwargs)
    
    def add_msg_callback(self, msg_type, callback_f):
        self.msg_callbacks_d.setdefault(msg_type, []).append(callback_f)

    def add_timeout_callback(self, callback_f):
        self.timeout_callbacks.append(callback_f)
                                
    def stop(self):
        self.reactor.stop()

    def _on_datagram_received(self, data, addr):
        # Sanitize bencode
        try:
            msg = message.IncomingMsg(data)
        except (message.MsgError):
            log.info('MsgError when decoding\n%s\nsouce: %s' % (
                data, addr))
            return # ignore message
        try:
            # callback according to message's type
            callback_fs = self.msg_callbacks_d[msg.type]
        except (KeyError):
            log.info('Key TYPE has an invalid value\n%s\nsouce: %s' % (
                data, addr))
            return #ignore message
        # Call the proper callback (selected according msg's TYPE)
        response_msg = None
        for callback_f in callback_fs:
            # if there is a response we should keep it
            response_msg = callback_f(msg, addr) or response_msg
        if response_msg:
            bencoded_response = response_msg.encode(msg.tid)
            self.send_msg_to(bencoded_response, addr)
    

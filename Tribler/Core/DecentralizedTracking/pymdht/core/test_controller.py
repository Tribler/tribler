# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import test_const as tc
import message

import controller

import routing_plugin_template as routing_m_mod
import lookup_plugin_template as lookup_m_mod

class TestController:

    def setup(self):
        self.controller = controller.Controller(tc.CLIENT_ADDR, 'test_logs',
                                                routing_m_mod,
                                                lookup_m_mod,
                                                None)

    def test_start_stop(self):
        self.controller.start()
        self.controller.stop()

    def test_load_save_state(self):
        #TODO: change state
        self.controller.save_state()
        #TODO:check file
        self.controller.load_state()
        #TODO: check state

    def test_get_peers(self):
        self.controller.start()
        self.controller.get_peers(None, tc.INFO_HASH, None, 0)
        self.controller.stop()

    def test_complete(self):
        # controller.start() starts reactor (we don't want to use reactor in
        # tests), sets _running, and calls main_loop
        self.controller._running = True
        # controller.start calls _main_loop, which does maintenance (bootstrap)
        self.controller._main_loop()
        # minitwisted informs of a response
        data = message.OutgoingPingResponse(tc.SERVER_ID).encode('\0\0')
        self.controller._on_datagram_received(data, tc.SERVER_ADDR)
        self.controller._main_loop() # maintenance (maintenance lookup)        
        
        

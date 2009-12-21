# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import test_const as tc

import controller

class TestController:

    def setup(self):
        self.controller = controller.Controller(tc.CLIENT_ADDR)

    def test_start_stop(self):
        self.controller.start()
        self.controller.stop()

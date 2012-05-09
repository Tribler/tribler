# Copyright (C) 2009-2011 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import state
import test_const as tc

class TestState:

    
    
    def test_load_save_state(self):
        filename = 'test_logs/state.dat'
        my_id = tc.CLIENT_ID
        #TODO: change state
        state.save(my_id, [], filename)
        #TODO:check file
        state.load(filename)
        #TODO: check state


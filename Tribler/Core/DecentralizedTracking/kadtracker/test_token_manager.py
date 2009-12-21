# Copyright (C) 2009 Raul Jimenez, Flutra Osmani
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

from nose.tools import *

import token_manager

token_str = '123'
invalid_token_str = ''

class TestTokenManager:

    def setup(self):
        self.token_m = token_manager.TokenManager()

    def test_get_token(self):
        eq_(self.token_m.get(), token_str)

    def test_check_token(self):
        ok_(self.token_m.check(token_str))
        ok_(not self.token_m.check(invalid_token_str))

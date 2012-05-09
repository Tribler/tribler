# Copyright (C) 2009-2010 Raul Jimenez, Flutra Osmani
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

from nose.tools import ok_, eq_

import token_manager


IPS = ['1.1.1.1', '2.2.2.2']

class TestTokenManager:

    def setup(self):
        self.token_m1 = token_manager.TokenManager()
        self.token_m2 = token_manager.TokenManager()

    def test_get_token(self):
        eq_(self.token_m1.get(IPS[0]), self.token_m1.get(IPS[0]))
        eq_(self.token_m2.get(IPS[0]), self.token_m2.get(IPS[0]))
        ok_(self.token_m1.get(IPS[0]) != self.token_m2.get(IPS[0]))
        ok_(self.token_m1.get(IPS[0]) != self.token_m1.get(IPS[1]))
        ok_(self.token_m2.get(IPS[0]) != self.token_m2.get(IPS[1]))

    def test_check_token(self):
        for ip in IPS:
            ok_(self.token_m1.check(ip, self.token_m1.get(ip)))
            ok_(self.token_m2.check(ip, self.token_m2.get(ip)))
            ok_(not self.token_m1.check(ip, self.token_m2.get(ip)))
            ok_(not self.token_m2.check(ip, self.token_m1.get(ip)))

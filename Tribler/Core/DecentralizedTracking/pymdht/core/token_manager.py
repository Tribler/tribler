# Copyright (C) 2009-2010 Raul Jimenez, Flutra Osmani
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information



class TokenManager(object):
    def __init__(self):
        #TODO: make it random and dynamic
        #TODO: make each token only valid for a single addr
        self.current_token = '123'
        
    def get(self):
        return self.current_token

    def check(self, token):
        return token == self.current_token

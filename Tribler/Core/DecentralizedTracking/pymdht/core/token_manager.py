# Copyright (C) 2009-2010 Raul Jimenez, Flutra Osmani
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import random
import hashlib

NUM_BYTES = 4

class TokenManager(object):
    def __init__(self):
        #TODO: make it random and dynamic
        #TODO: make each token only valid for a single addr
        self._secret = ''.join([chr(random.randint(0, 255)) for i in xrange(NUM_BYTES)])
        
    def get(self, ip):
        return hashlib.sha1(self._secret + ip).digest()[:NUM_BYTES]

    def check(self, ip, token):
        return token == hashlib.sha1(self._secret + ip).digest()[:NUM_BYTES]

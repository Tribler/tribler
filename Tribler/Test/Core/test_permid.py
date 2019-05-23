from __future__ import absolute_import

import os

from ipv8.keyvault.private.libnaclkey import LibNaCLSK

from twisted.internet.defer import inlineCallbacks

from Tribler.Core import permid
from Tribler.Test.Core.base_test import TriblerCoreTest


class TriblerCoreTestPermid(TriblerCoreTest):

    @inlineCallbacks
    def setUp(self):
        yield super(TriblerCoreTestPermid, self).setUp()
        # All the files are in self.session_base_dir, so they will automatically be cleaned on tearDown()
        self.pub_key_path_trustchain = os.path.join(self.session_base_dir, 'pub_key_multichain.pem')
        self.key_pair_path_trustchain = os.path.join(self.session_base_dir, 'pair_multichain.pem')

    def test_save_load_keypair_pubkey_trustchain(self):
        key = permid.generate_keypair_trustchain()

        permid.save_keypair_trustchain(key, self.key_pair_path_trustchain)
        permid.save_pub_key_trustchain(key, self.pub_key_path_trustchain)

        self.assertTrue(os.path.isfile(self.pub_key_path_trustchain))
        self.assertTrue(os.path.isfile(self.key_pair_path_trustchain))

        loaded_key = permid.read_keypair_trustchain(self.key_pair_path_trustchain)
        self.assertIsInstance(loaded_key, LibNaCLSK)
        self.assertEquals(key.key_to_bin(), loaded_key.key_to_bin())

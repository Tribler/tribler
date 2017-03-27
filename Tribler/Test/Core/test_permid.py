import os

from M2Crypto.EC import EC
from twisted.internet.defer import inlineCallbacks

from Tribler.Core import permid
from Tribler.dispersy.crypto import LibNaCLSK
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TriblerCoreTestPermid(TriblerCoreTest):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self):
        yield super(TriblerCoreTestPermid, self).setUp()
        # All the files are in self.session_base_dir, so they will automatically be cleaned on tearDown()
        self.pub_key_path = os.path.join(self.session_base_dir, 'pub_key.pem')
        self.key_pair_path = os.path.join(self.session_base_dir, 'pair.pem')
        self.pub_key_path_multichain = os.path.join(self.session_base_dir, 'pub_key_multichain.pem')
        self.key_pair_path_multichain = os.path.join(self.session_base_dir, 'pair_multichain.pem')

    def test_save_load_keypair_pubkey(self):
        permid.init()
        key = permid.generate_keypair()

        permid.save_keypair(key, self.key_pair_path)
        permid.save_pub_key(key, self.pub_key_path)

        self.assertTrue(os.path.isfile(self.pub_key_path))
        self.assertTrue(os.path.isfile(self.key_pair_path))

        loaded_key = permid.read_keypair(self.key_pair_path)
        self.assertIsInstance(loaded_key, EC)

    def test_save_load_keypair_pubkey_multichain(self):
        permid.init()
        key = permid.generate_keypair_multichain()

        permid.save_keypair_multichain(key, self.key_pair_path_multichain)
        permid.save_pub_key_multichain(key, self.pub_key_path_multichain)

        self.assertTrue(os.path.isfile(self.pub_key_path_multichain))
        self.assertTrue(os.path.isfile(self.key_pair_path_multichain))

        loaded_key = permid.read_keypair_multichain(self.key_pair_path_multichain)
        self.assertIsInstance(loaded_key, LibNaCLSK)
        self.assertEquals(key.key_to_bin(), loaded_key.key_to_bin())

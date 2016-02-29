import os
from tempfile import mkdtemp

import shutil

from M2Crypto.EC import EC

from Tribler.Core import permid
from Tribler.Test.Core.base_test import TriblerCoreTest


class TriblerCoreTestPermid(TriblerCoreTest):

    def test_save_load_keypair_pubkey(self):
        permid.init()
        key = permid.generate_keypair()

        test_base_dir = mkdtemp(suffix="_tribler_test_session")
        pub_key_path = os.path.join(test_base_dir, 'pub_key.pem')
        key_pair_path = os.path.join(test_base_dir, 'pair.pem')

        permid.save_keypair(key, key_pair_path)
        permid.save_pub_key(key, pub_key_path)

        self.assertTrue(os.path.isfile(pub_key_path))
        self.assertTrue(os.path.isfile(key_pair_path))

        loaded_key = permid.read_keypair(key_pair_path)
        self.assertIsInstance(loaded_key, EC)

        shutil.rmtree(unicode(test_base_dir), ignore_errors=True)

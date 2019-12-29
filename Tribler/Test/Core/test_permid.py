from ipv8.keyvault.private.libnaclkey import LibNaCLSK

from Tribler.Core import permid
from Tribler.Test.Core.base_test import TriblerCoreTest


class TriblerCoreTestPermid(TriblerCoreTest):

    async def setUp(self):
        await super(TriblerCoreTestPermid, self).setUp()
        # All the files are in self.session_base_dir, so they will automatically be cleaned on tearDown()
        self.pub_key_path_trustchain = self.session_base_dir / 'pub_key_multichain.pem'
        self.key_pair_path_trustchain = self.session_base_dir / 'pair_multichain.pem'

    def test_save_load_keypair_pubkey_trustchain(self):
        key = permid.generate_keypair_trustchain()

        permid.save_keypair_trustchain(key, self.key_pair_path_trustchain)
        permid.save_pub_key_trustchain(key, self.pub_key_path_trustchain)

        self.assertTrue(self.pub_key_path_trustchain.is_file())
        self.assertTrue(self.key_pair_path_trustchain.is_file())

        loaded_key = permid.read_keypair_trustchain(self.key_pair_path_trustchain)
        self.assertIsInstance(loaded_key, LibNaCLSK)
        self.assertEqual(key.key_to_bin(), loaded_key.key_to_bin())

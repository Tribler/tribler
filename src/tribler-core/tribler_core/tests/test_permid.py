from pathlib import Path

from ipv8.keyvault.private.libnaclkey import LibNaCLSK

from tribler_core.utilities import permid


def test_save_load_keypair_pubkey_trustchain(tmpdir):
    pub_key_path_trustchain = Path(tmpdir) / 'pub_key_multichain.pem'
    key_pair_path_trustchain = Path(tmpdir) / 'pair_multichain.pem'
    key = permid.generate_keypair_trustchain()

    permid.save_keypair_trustchain(key, key_pair_path_trustchain)
    permid.save_pub_key_trustchain(key, pub_key_path_trustchain)

    assert pub_key_path_trustchain.is_file()
    assert key_pair_path_trustchain.is_file()

    loaded_key = permid.read_keypair_trustchain(key_pair_path_trustchain)
    assert isinstance(loaded_key, LibNaCLSK)
    assert key.key_to_bin() == loaded_key.key_to_bin()

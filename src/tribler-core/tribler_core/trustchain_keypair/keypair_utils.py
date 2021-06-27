import tribler_core.utilities.permid as permid_module

def load_keypair(keypair_filename, trustchain_pubfilename):

    if keypair_filename.exists():
        trustchain_keypair = permid_module.read_keypair_trustchain(keypair_filename)
    else:
        trustchain_keypair = permid_module.generate_keypair_trustchain()

        # Save keypair
        permid_module.save_keypair_trustchain(trustchain_keypair, keypair_filename)
        permid_module.save_pub_key_trustchain(trustchain_keypair, trustchain_pubfilename)

    return trustchain_keypair

from hashlib import sha1

from Tribler.community.privatesocial.community import PoliSocialCommunity
from Tribler.community.privatesemantic.rsa import rsa_init

def load_community(dispersy):
    master_key = "3081a7301006072a8648ce3d020106052b81040027038192000404f10c33b03d2a09943d6d6a4b2cf4fe3129e5dce1df446a27d0ce00d48c845a4eff8102ef3becd6bc07c65953c824d227ebc110016d5ba71163bf6fb83fde7cdccf164bb007e27d07da952c47d30cf9c843034dc7a4603af3a84f8997e5d046e6a5f1ad489add6878898079a4663ade502829577c7d1e27302a3d5ea0ae06e83641a093a87465fdd4a3b43e031a9555".decode("HEX")
    master = dispersy.get_member(master_key)
    my_member = dispersy.get_new_member(u"low")

    community = PoliSocialCommunity.join_community(dispersy, master, my_member, my_member, integrate_with_tribler=False)
    community.create_text(u"abc", [])

    rsakey = rsa_init()
    keyhash = long(sha1(str(rsakey)).hexdigest(), 16)
    community._friend_db.add_friend("1", rsakey, keyhash)

    community.create_encrypted("abc", "1")

if __name__ == "__main__":
    from Tribler.dispersy.tool.mainthreadcallback import MainThreadCallback
    from Tribler.dispersy.dispersy import Dispersy
    from Tribler.dispersy.endpoint import NullEndpoint

    callback = MainThreadCallback()
    dispersy = Dispersy(callback, NullEndpoint(address=("0.0.0.0", 0)), u".", u":memory:")
    dispersy.statistics.enable_debug_statistics(True)

    dispersy.start()
    callback.register(load_community, (dispersy,))
    callback.register(callback.stop, delay=15.0)

    callback.loop()

import sys

from Tribler.dispersy.community import Community
from Tribler.community.privatesemantic.community import HForwardCommunity, \
    PForwardCommunity, PoliForwardCommunity

ENCRYPTION = True

class NoFSemanticCommunity(HForwardCommunity, Community):

    def __init__(self, dispersy, master, my_member, integrate_with_tribler=True, encryption=ENCRYPTION, max_prefs=None, max_fprefs=None, send_simi_reveal=True):
        Community.__init__(self, dispersy, master, my_member)
        HForwardCommunity.__init__(self, dispersy, integrate_with_tribler, encryption, 0, max_prefs, max_fprefs, max_taste_buddies=sys.maxint, send_simi_reveal=send_simi_reveal)

    def initiate_conversions(self):
        return HForwardCommunity.initiate_conversions(self)

    def initiate_meta_messages(self):
        return HForwardCommunity.initiate_meta_messages(self)

    def unload_community(self):
        HForwardCommunity.unload_community(self)
        Community.unload_community(self)

class HFSemanticCommunity(HForwardCommunity, Community):

    def __init__(self, dispersy, master, my_member, integrate_with_tribler=True, encryption=ENCRYPTION, max_prefs=None, max_fprefs=None, send_simi_reveal=True):
        Community.__init__(self, dispersy, master, my_member)
        HForwardCommunity.__init__(self, dispersy, integrate_with_tribler, encryption, 10, max_prefs, max_fprefs, max_taste_buddies=sys.maxint, send_simi_reveal=send_simi_reveal)

    def initiate_conversions(self):
        return HForwardCommunity.initiate_conversions(self)

    def initiate_meta_messages(self):
        return HForwardCommunity.initiate_meta_messages(self)

    def unload_community(self):
        HForwardCommunity.unload_community(self)
        Community.unload_community(self)

class PFSemanticCommunity(PForwardCommunity, Community):

    def __init__(self, dispersy, master, my_member, integrate_with_tribler=True, encryption=ENCRYPTION, max_prefs=None, max_fprefs=None, send_simi_reveal=True):
        Community.__init__(self, dispersy, master, my_member)
        PForwardCommunity.__init__(self, dispersy, integrate_with_tribler, encryption, 10, max_prefs, max_fprefs, max_taste_buddies=sys.maxint, send_simi_reveal=send_simi_reveal)

    def initiate_conversions(self):
        return PForwardCommunity.initiate_conversions(self)

    def initiate_meta_messages(self):
        return PForwardCommunity.initiate_meta_messages(self)

    def unload_community(self):
        PForwardCommunity.unload_community(self)
        Community.unload_community(self)

class PoliFSemanticCommunity(PoliForwardCommunity, Community):

    def __init__(self, dispersy, master, my_member, integrate_with_tribler=True, encryption=ENCRYPTION, max_prefs=None, max_fprefs=None, send_simi_reveal=True):
        Community.__init__(self, dispersy, master, my_member)
        PoliForwardCommunity.__init__(self, dispersy, integrate_with_tribler, encryption, 10, max_prefs, max_fprefs, max_taste_buddies=sys.maxint, send_simi_reveal=send_simi_reveal)

    def initiate_conversions(self):
        return PoliForwardCommunity.initiate_conversions(self)

    def initiate_meta_messages(self):
        return PoliForwardCommunity.initiate_meta_messages(self)

    def unload_community(self):
        PoliForwardCommunity.unload_community(self)
        Community.unload_community(self)

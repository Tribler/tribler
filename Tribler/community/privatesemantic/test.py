import sys

from Tribler.dispersy.community import Community
from Tribler.community.privatesemantic.community import HForwardCommunity, \
    PForwardCommunity, PoliForwardCommunity

ENCRYPTION = True

class NoFSemanticCommunity(HForwardCommunity, Community):

    @classmethod
    def load_community(cls, dispersy, master, my_member, integrate_with_tribler=True, encryption=ENCRYPTION, max_prefs=None, max_fprefs=None):
        dispersy_database = dispersy.database
        try:
            dispersy_database.execute(u"SELECT 1 FROM community WHERE master = ?", (master.database_id,)).next()
        except StopIteration:
            return cls.join_community(dispersy, master, my_member, my_member, integrate_with_tribler=integrate_with_tribler, encryption=encryption, max_prefs=max_prefs, max_fprefs=max_fprefs)
        else:
            return super(NoFSemanticCommunity, cls).load_community(dispersy, master, integrate_with_tribler=integrate_with_tribler, encryption=encryption, max_prefs=max_prefs, max_fprefs=max_fprefs)

    def __init__(self, dispersy, master, integrate_with_tribler=True, encryption=ENCRYPTION, max_prefs=None, max_fprefs=None):
        Community.__init__(self, dispersy, master)
        HForwardCommunity.__init__(self, dispersy, master, integrate_with_tribler, encryption, 0, max_prefs, max_fprefs, max_taste_buddies=sys.maxint, send_simi_reveal=True)

    def initiate_conversions(self):
        return HForwardCommunity.initiate_conversions(self)

    def initiate_meta_messages(self):
        return HForwardCommunity.initiate_meta_messages(self)

    def unload_community(self):
        HForwardCommunity.unload_community(self)
        Community.unload_community(self)

class HFSemanticCommunity(HForwardCommunity, Community):

    @classmethod
    def load_community(cls, dispersy, master, my_member, integrate_with_tribler=True, encryption=ENCRYPTION, max_prefs=None, max_fprefs=None):
        dispersy_database = dispersy.database
        try:
            dispersy_database.execute(u"SELECT 1 FROM community WHERE master = ?", (master.database_id,)).next()
        except StopIteration:
            return cls.join_community(dispersy, master, my_member, my_member, integrate_with_tribler=integrate_with_tribler, encryption=encryption, max_prefs=max_prefs, max_fprefs=max_fprefs)
        else:
            return super(HFSemanticCommunity, cls).load_community(dispersy, master, integrate_with_tribler=integrate_with_tribler, encryption=encryption, max_prefs=max_prefs, max_fprefs=max_fprefs)

    def __init__(self, dispersy, master, integrate_with_tribler=True, encryption=ENCRYPTION, max_prefs=None, max_fprefs=None):
        Community.__init__(self, dispersy, master)
        HForwardCommunity.__init__(self, dispersy, master, integrate_with_tribler, encryption, 10, max_prefs, max_fprefs, max_taste_buddies=sys.maxint, send_simi_reveal=True)

    def initiate_conversions(self):
        return HForwardCommunity.initiate_conversions(self)

    def initiate_meta_messages(self):
        return HForwardCommunity.initiate_meta_messages(self)

    def unload_community(self):
        HForwardCommunity.unload_community(self)
        Community.unload_community(self)

class PFSemanticCommunity(PForwardCommunity, Community):

    @classmethod
    def load_community(cls, dispersy, master, my_member, integrate_with_tribler=True, encryption=ENCRYPTION, max_prefs=None, max_fprefs=None):
        dispersy_database = dispersy.database
        try:
            dispersy_database.execute(u"SELECT 1 FROM community WHERE master = ?", (master.database_id,)).next()
        except StopIteration:
            return cls.join_community(dispersy, master, my_member, my_member, integrate_with_tribler=integrate_with_tribler, encryption=encryption, max_prefs=max_prefs, max_fprefs=max_fprefs)
        else:
            return super(PFSemanticCommunity, cls).load_community(dispersy, master, integrate_with_tribler=integrate_with_tribler, encryption=encryption, max_prefs=max_prefs, max_fprefs=max_fprefs)

    def __init__(self, dispersy, master, integrate_with_tribler=True, encryption=ENCRYPTION, max_prefs=None, max_fprefs=None):
        Community.__init__(self, dispersy, master)
        PForwardCommunity.__init__(self, dispersy, master, integrate_with_tribler, encryption, 10, max_prefs, max_fprefs, max_taste_buddies=sys.maxint, send_simi_reveal=True)

    def initiate_conversions(self):
        return PForwardCommunity.initiate_conversions(self)

    def initiate_meta_messages(self):
        return PForwardCommunity.initiate_meta_messages(self)

    def unload_community(self):
        PForwardCommunity.unload_community(self)
        Community.unload_community(self)

class PoliFSemanticCommunity(PoliForwardCommunity, Community):

    @classmethod
    def load_community(cls, dispersy, master, my_member, integrate_with_tribler=True, encryption=ENCRYPTION, max_prefs=None, max_fprefs=None):
        dispersy_database = dispersy.database
        try:
            dispersy_database.execute(u"SELECT 1 FROM community WHERE master = ?", (master.database_id,)).next()
        except StopIteration:
            return cls.join_community(dispersy, master, my_member, my_member, integrate_with_tribler=integrate_with_tribler, encryption=encryption, max_prefs=max_prefs, max_fprefs=max_fprefs)
        else:
            return super(PoliFSemanticCommunity, cls).load_community(dispersy, master, integrate_with_tribler=integrate_with_tribler, encryption=encryption, max_prefs=max_prefs, max_fprefs=max_fprefs)

    def __init__(self, dispersy, master, integrate_with_tribler=True, encryption=ENCRYPTION, max_prefs=None, max_fprefs=None):
        Community.__init__(self, dispersy, master)
        PoliForwardCommunity.__init__(self, dispersy, master, integrate_with_tribler, encryption, 10, max_prefs, max_fprefs, max_taste_buddies=sys.maxint, send_simi_reveal=True)

    def initiate_conversions(self):
        return PoliForwardCommunity.initiate_conversions(self)

    def initiate_meta_messages(self):
        return PoliForwardCommunity.initiate_meta_messages(self)

    def unload_community(self):
        PoliForwardCommunity.unload_community(self)
        Community.unload_community(self)

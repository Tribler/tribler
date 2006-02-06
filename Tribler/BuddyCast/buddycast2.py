from Tribler.CacheDB.CacheDBHandler import *
from Tribler.__init__ import GLOBAL

class BuddyCast:
    __single = None
    
    def __init__(self, db_dir=''):
        if BuddyCast.__single:
            raise RuntimeError, "BuddyCast is singleton"
        BuddyCast.__single = self 
        # --- database handlers ---
        self.mydb = MyDBHandler(db_dir=db_dir)
        self.peers = PeerDBHandler(db_dir=db_dir)
        self.torrents = TorrentDBHandler(db_dir=db_dir)
        self.myprefs = MyPreferenceDBHandler(db_dir=db_dir)
        self.prefs = PreferenceDBHandler(db_dir=db_dir)
        self.owners = OwnerDBHandler(db_dir=db_dir)
        # --- constants. they should be stored in mydb ---
        self.max_bc_len = 30     # max buddy cache length
        self.max_rc_len = 100    # max random peer cache length
        self.max_pc_len = 100    # max my preference cache length
        
        self.max_pl_len = 10     # max amount of preferences in prefxchg message
        self.max_tb_len = 10     # max amount of taste buddies in prefxchg message
        self.max_rp_len = 10     # max amount of random peers in prefxchg message
        self.max_pcq_len = 3     # max prefxchg_candidate_queue length
        
        self.buddycast_interval = GLOBAL.do_buddycast_interval
        # --- variables ---
        self.my_ip = ''
        self.my_port = 0
        self.my_name = ''
        self.my_prefxchg_msg = {}
        self.rawserver = None
        self.registered = False
                
    def getInstance(*args, **kw):
        if BuddyCast.__single is None:
            BuddyCast(*args, **kw)
        return BuddyCast.__single
    getInstance = staticmethod(getInstance)
        
    def register(self, secure_overlay, rawserver, port, errorfunc):    
        if self.registered:
            return
        self.secure_overlay = secure_overlay
        self.rawserver = rawserver
        self.errorfunc = errorfunc
        self.my_name = self.mydb.get('name')
        self.my_ip = self.mydb.get('ip')
        self.my_port = port
        self.mydb.put('port', port)
        self.mydb.sync()
        self.registered = True
        self.startup()
        
    def is_registered(self):
        return self.registered
    
    def startup(self):
        print "buddycast starts up"
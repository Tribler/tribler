# written by Fabian van der Werf, Arno Bakker
# see LICENSE.txt for license information

khashmir_imported = False
try:
    from utkhashmir import UTKhashmir
    khashmir_imported = True
except:
    pass


DEBUG = False

dht = None

def init(*args, **kws):
    global dht
    global khashmir_imported
    if khashmir_imported and dht is None:
        dht = UTKhashmir(*args, **kws)
        # Arno: no need for separate thread, it now runs on the regular network thread
        dht.addContact('router.bittorrent.com', 6881)

def control():
    import pdb
    pdb.set_trace()

def deinit():
    global dht
    if dht is not None:
        try:
            dht.rawserver.stop()
        except:
            pass

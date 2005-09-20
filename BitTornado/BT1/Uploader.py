# Written by Bram Cohen
# see LICENSE.txt for license information

from BitTornado.CurrentRateMeasure import Measure

try:
    True
except:
    True = 1
    False = 0

class Upload:
    def __init__(self, connection, ratelimiter, totalup, choker, storage,
                 picker, config):
        self.connection = connection
        self.ratelimiter = ratelimiter
        self.totalup = totalup
        self.choker = choker
        self.storage = storage
        self.picker = picker
        self.config = config
        self.max_slice_length = config['max_slice_length']
        self.choked = True
        self.cleared = True
        self.interested = False
        self.super_seeding = False
        self.buffer = []
        self.measure = Measure(config['max_rate_period'], config['upload_rate_fudge'])
        self.was_ever_interested = False
        if storage.get_amount_left() == 0:
            if choker.super_seed:
                self.super_seeding = True   # flag, and don't send bitfield
                self.seed_have_list = []    # set from piecepicker
                self.skipped_count = 0
            else:
                if config['breakup_seed_bitfield']:
                    bitfield, msgs = storage.get_have_list_cloaked()
                    connection.send_bitfield(bitfield)
                    for have in msgs:
                        connection.send_have(have)
                else:
                    connection.send_bitfield(storage.get_have_list())
        else:
            if storage.do_I_have_anything():
                connection.send_bitfield(storage.get_have_list())
        self.piecedl = None
        self.piecebuf = None

    def got_not_interested(self):
        if self.interested:
            self.interested = False
            del self.buffer[:]
            self.piecedl = None
            if self.piecebuf:
                self.piecebuf.release()
            self.piecebuf = None
            self.choker.not_interested(self.connection)

    def got_interested(self):
        if not self.interested:
            self.interested = True
            self.was_ever_interested = True
            self.choker.interested(self.connection)

    def get_upload_chunk(self):
        if self.choked or not self.buffer:
            return None
        index, begin, length = self.buffer.pop(0)
        if self.config['buffer_reads']:
            if index != self.piecedl:
                if self.piecebuf:
                    self.piecebuf.release()
                self.piecedl = index
                self.piecebuf = self.storage.get_piece(index, 0, -1)
            try:
                piece = self.piecebuf[begin:begin+length]
                assert len(piece) == length
            except:     # fails if storage.get_piece returns None or if out of range
                self.connection.close()
                return None
        else:
            if self.piecebuf:
                self.piecebuf.release()
                self.piecedl = None
            piece = self.storage.get_piece(index, begin, length)
            if piece is None:
                self.connection.close()
                return None
        self.measure.update_rate(len(piece))
        self.totalup.update_rate(len(piece))
        return (index, begin, piece)

    def got_request(self, index, begin, length):
        if ( (self.super_seeding and not index in self.seed_have_list)
                   or not self.interested or length > self.max_slice_length ):
            self.connection.close()
            return
        if not self.cleared:
            self.buffer.append((index, begin, length))
        if not self.choked and self.connection.next_upload is None:
                self.ratelimiter.queue(self.connection)


    def got_cancel(self, index, begin, length):
        try:
            self.buffer.remove((index, begin, length))
        except ValueError:
            pass

    def choke(self):
        if not self.choked:
            self.choked = True
            self.connection.send_choke()
        self.piecedl = None
        if self.piecebuf:
            self.piecebuf.release()
            self.piecebuf = None

    def choke_sent(self):
        del self.buffer[:]
        self.cleared = True

    def unchoke(self):
        if self.choked:
            self.choked = False
            self.cleared = False
            self.connection.send_unchoke()
        
    def disconnected(self):
        if self.piecebuf:
            self.piecebuf.release()
            self.piecebuf = None

    def is_choked(self):
        return self.choked
        
    def is_interested(self):
        return self.interested

    def has_queries(self):
        return not self.choked and len(self.buffer) > 0

    def get_rate(self):
        return self.measure.get_rate()
    

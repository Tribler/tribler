# Written by John Hoffman
# see LICENSE.txt for license information

from random import shuffle
try:
    True
except:
    True = 1
    False = 0


class FileSelector:
    def __init__(self, files, piece_length, bufferdir,
                 storage, storagewrapper, sched, failfunc):
        self.files = files
        self.storage = storage
        self.storagewrapper = storagewrapper
        self.sched = sched
        self.failfunc = failfunc
        self.downloader = None
        self.picker = None

        storage.set_bufferdir(bufferdir)
        
        self.numfiles = len(files)
        self.priority = [1] * self.numfiles
        self.new_priority = None
        self.new_partials = None
        self.filepieces = []
        total = 0L
        for file, length in files:
            if not length:
                self.filepieces.append(())
            else:
                pieces = range( int(total/piece_length),
                                int((total+length-1)/piece_length)+1 )
                self.filepieces.append(tuple(pieces))
                total += length
        self.numpieces = int((total+piece_length-1)/piece_length)
        self.piece_priority = [1] * self.numpieces
        


    def init_priority(self, new_priority):
        try:
            assert len(new_priority) == self.numfiles
            for v in new_priority:
                assert type(v) in (type(0), type(0L))
                assert v >= -1
                assert v <= 2
        except:
#           print_exc()
            return False
        try:
            for f in xrange(self.numfiles):
                if new_priority[f] < 0:
                    self.storage.disable_file(f)
            self.new_priority = new_priority
        except (IOError, OSError), e:
            self.failfunc("can't open partial file for "
                          + self.files[f][0] + ': ' + str(e))
            return False
        return True

    '''
    d['priority'] = [file #1 priority [,file #2 priority...] ]
                    a list of download priorities for each file.
                    Priority may be -1, 0, 1, 2.  -1 = download disabled,
                    0 = highest, 1 = normal, 2 = lowest.
    Also see Storage.pickle and StorageWrapper.pickle for additional keys.
    '''
    def unpickle(self, d):
        if d.has_key('priority'):
            if not self.init_priority(d['priority']):
                return
        pieces = self.storage.unpickle(d)
        if not pieces:  # don't bother, nothing restoreable
            return
        new_piece_priority = self._get_piece_priority_list(self.new_priority)
        self.storagewrapper.reblock([i == -1 for i in new_piece_priority])
        self.new_partials = self.storagewrapper.unpickle(d, pieces)


    def tie_in(self, picker, cancelfunc, requestmorefunc):
        self.picker = picker
        self.cancelfunc = cancelfunc
        self.requestmorefunc = requestmorefunc

        if self.new_priority:
            self.priority = self.new_priority
            self.new_priority = None
            self.new_piece_priority = self._set_piece_priority(self.priority)

        if self.new_partials:
            shuffle(self.new_partials)
            for p in self.new_partials:
                self.picker.requested(p)
        self.new_partials = None
        

    def _set_files_disabled(self, old_priority, new_priority):
        old_disabled = [p == -1 for p in old_priority]
        new_disabled = [p == -1 for p in new_priority]
        data_to_update = []
        for f in xrange(self.numfiles):
            if new_disabled[f] != old_disabled[f]:
                data_to_update.extend(self.storage.get_piece_update_list(f))
        buffer = []
        for piece, start, length in data_to_update:
            if self.storagewrapper.has_data(piece):
                data = self.storagewrapper.read_raw(piece, start, length)
                if data is None:
                    return False
                buffer.append((piece, start, data))

        files_updated = False        
        try:
            for f in xrange(self.numfiles):
                if new_disabled[f] and not old_disabled[f]:
                    self.storage.disable_file(f)
                    files_updated = True
                if old_disabled[f] and not new_disabled[f]:
                    self.storage.enable_file(f)
                    files_updated = True
        except (IOError, OSError), e:
            if new_disabled[f]:
                msg = "can't open partial file for "
            else:
                msg = 'unable to open '
            self.failfunc(msg + self.files[f][0] + ': ' + str(e))
            return False
        if files_updated:
            self.storage.reset_file_status()

        changed_pieces = {}
        for piece, start, data in buffer:
            if not self.storagewrapper.write_raw(piece, start, data):
                return False
            data.release()
            changed_pieces[piece] = 1
        if not self.storagewrapper.doublecheck_data(changed_pieces):
            return False

        return True        


    def _get_piece_priority_list(self, file_priority_list):
        l = [-1] * self.numpieces
        for f in xrange(self.numfiles):
            if file_priority_list[f] == -1:
                continue
            for i in self.filepieces[f]:
                if l[i] == -1:
                    l[i] = file_priority_list[f]
                    continue
                l[i] = min(l[i], file_priority_list[f])
        return l
        

    def _set_piece_priority(self, new_priority):
        new_piece_priority = self._get_piece_priority_list(new_priority)
        pieces = range(self.numpieces)
        shuffle(pieces)
        new_blocked = []
        new_unblocked = []
        for piece in pieces:
            self.picker.set_priority(piece, new_piece_priority[piece])
            o = self.piece_priority[piece] == -1
            n = new_piece_priority[piece] == -1
            if n and not o:
                new_blocked.append(piece)
            if o and not n:
                new_unblocked.append(piece)
        if new_blocked:
            self.cancelfunc(new_blocked)
        self.storagewrapper.reblock([i == -1 for i in new_piece_priority])
        if new_unblocked:
            self.requestmorefunc(new_unblocked)

        return new_piece_priority        


    def set_priorities_now(self, new_priority = None):
        if not new_priority:
            new_priority = self.new_priority
            self.new_priority = None    # potential race condition
            if not new_priority:
                return
        old_priority = self.priority
        self.priority = new_priority
        if not self._set_files_disabled(old_priority, new_priority):
            return
        self.piece_priority = self._set_piece_priority(new_priority)

    def set_priorities(self, new_priority):
        self.new_priority = new_priority
        def s(self=self):
            self.set_priorities_now()
        self.sched(s)
        
    def set_priority(self, f, p):
        new_priority = self.get_priorities()
        new_priority[f] = p
        self.set_priorities(new_priority)

    def get_priorities(self):
        priority = self.new_priority
        if not priority:
            priority = self.priority    # potential race condition
        return [i for i in priority]

    def __setitem__(self, index, val):
        self.set_priority(index, val)

    def __getitem__(self, index):
        try:
            return self.new_priority[index]
        except:
            return self.priority[index]


    def finish(self):
        pass
#        for f in xrange(self.numfiles):
#            if self.priority[f] == -1:
#                self.storage.delete_file(f)

    def pickle(self):
        d = {'priority': self.priority}
        try:
            s = self.storage.pickle()
            sw = self.storagewrapper.pickle()
            for k in s.keys():
                d[k] = s[k]
            for k in sw.keys():
                d[k] = sw[k]
        except (IOError, OSError):
            pass
        return d

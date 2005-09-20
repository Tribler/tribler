# Written by Bram Cohen
# see LICENSE.txt for license information

from BitTornado.piecebuffer import BufferPool
from threading import Lock
from time import time, strftime, localtime
import os
from os.path import exists, getsize, getmtime, basename
from traceback import print_exc
try:
    from os import fsync
except ImportError:
    fsync = lambda x: None
from bisect import bisect
    
try:
    True
except:
    True = 1
    False = 0

DEBUG = False

MAXREADSIZE = 32768
MAXLOCKSIZE = 1000000000L
MAXLOCKRANGE = 3999999999L   # only lock first 4 gig of file

_pool = BufferPool()
PieceBuffer = _pool.new

def dummy_status(fractionDone = None, activity = None):
    pass

class Storage:
    def __init__(self, files, piece_length, doneflag, config,
                 disabled_files = None):
        # can raise IOError and ValueError
        self.files = files
        self.piece_length = piece_length
        self.doneflag = doneflag
        self.disabled = [False] * len(files)
        self.file_ranges = []
        self.disabled_ranges = []
        self.working_ranges = []
        numfiles = 0
        total = 0l
        so_far = 0l
        self.handles = {}
        self.whandles = {}
        self.tops = {}
        self.sizes = {}
        self.mtimes = {}
        if config.get('lock_files', True):
            self.lock_file, self.unlock_file = self._lock_file, self._unlock_file
        else:
            self.lock_file, self.unlock_file = lambda x1,x2: None, lambda x1,x2: None
        self.lock_while_reading = config.get('lock_while_reading', False)
        self.lock = Lock()

        if not disabled_files:
            disabled_files = [False] * len(files)

        for i in xrange(len(files)):
            file, length = files[i]
            if doneflag.isSet():    # bail out if doneflag is set
                return
            self.disabled_ranges.append(None)
            if length == 0:
                self.file_ranges.append(None)
                self.working_ranges.append([])
            else:
                range = (total, total + length, 0, file)
                self.file_ranges.append(range)
                self.working_ranges.append([range])
                numfiles += 1
                total += length
                if disabled_files[i]:
                    l = 0
                else:
                    if exists(file):
                        l = getsize(file)
                        if l > length:
                            h = open(file, 'rb+')
                            h.truncate(length)
                            h.flush()
                            h.close()
                            l = length
                    else:
                        l = 0
                        h = open(file, 'wb+')
                        h.flush()
                        h.close()
                    self.mtimes[file] = getmtime(file)
                self.tops[file] = l
                self.sizes[file] = length
                so_far += l

        self.total_length = total
        self._reset_ranges()

        self.max_files_open = config['max_files_open']
        if self.max_files_open > 0 and numfiles > self.max_files_open:
            self.handlebuffer = []
        else:
            self.handlebuffer = None


    if os.name == 'nt':
        def _lock_file(self, name, f):
            import msvcrt
            for p in range(0, min(self.sizes[name],MAXLOCKRANGE), MAXLOCKSIZE):
                f.seek(p)
                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK,
                               min(MAXLOCKSIZE,self.sizes[name]-p))

        def _unlock_file(self, name, f):
            import msvcrt
            for p in range(0, min(self.sizes[name],MAXLOCKRANGE), MAXLOCKSIZE):
                f.seek(p)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK,
                               min(MAXLOCKSIZE,self.sizes[name]-p))

    elif os.name == 'posix':
        def _lock_file(self, name, f):
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)

        def _unlock_file(self, name, f):
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    else:
        def _lock_file(self, name, f):
            pass
        def _unlock_file(self, name, f):
            pass


    def was_preallocated(self, pos, length):
        for file, begin, end in self._intervals(pos, length):
            if self.tops.get(file, 0) < end:
                return False
        return True


    def _sync(self, file):
        self._close(file)
        if self.handlebuffer:
            self.handlebuffer.remove(file)

    def sync(self):
        # may raise IOError or OSError
        for file in self.whandles.keys():
            self._sync(file)


    def set_readonly(self, f=None):
        if f is None:
            self.sync()
            return
        file = self.files[f][0]
        if self.whandles.has_key(file):
            self._sync(file)
            

    def get_total_length(self):
        return self.total_length


    def _open(self, file, mode):
        if self.mtimes.has_key(file):
            try:
              if self.handlebuffer is not None:
                assert getsize(file) == self.tops[file]
                newmtime = getmtime(file)
                oldmtime = self.mtimes[file]
                assert newmtime <= oldmtime+1
                assert newmtime >= oldmtime-1
            except:
                if DEBUG:
                    print ( file+' modified: '
                            +strftime('(%x %X)',localtime(self.mtimes[file]))
                            +strftime(' != (%x %X) ?',localtime(getmtime(file))) )
                raise IOError('modified during download')
        try:
            return open(file, mode)
        except:
            if DEBUG:
                print_exc()
            raise


    def _close(self, file):
        f = self.handles[file]
        del self.handles[file]
        if self.whandles.has_key(file):
            del self.whandles[file]
            f.flush()
            self.unlock_file(file, f)
            f.close()
            self.tops[file] = getsize(file)
            self.mtimes[file] = getmtime(file)
        else:
            if self.lock_while_reading:
                self.unlock_file(file, f)
            f.close()


    def _close_file(self, file):
        if not self.handles.has_key(file):
            return
        self._close(file)
        if self.handlebuffer:
            self.handlebuffer.remove(file)
        

    def _get_file_handle(self, file, for_write):
        if self.handles.has_key(file):
            if for_write and not self.whandles.has_key(file):
                self._close(file)
                try:
                    f = self._open(file, 'rb+')
                    self.handles[file] = f
                    self.whandles[file] = 1
                    self.lock_file(file, f)
                except (IOError, OSError), e:
                    if DEBUG:
                        print_exc()
                    raise IOError('unable to reopen '+file+': '+str(e))

            if self.handlebuffer:
                if self.handlebuffer[-1] != file:
                    self.handlebuffer.remove(file)
                    self.handlebuffer.append(file)
            elif self.handlebuffer is not None:
                self.handlebuffer.append(file)
        else:
            try:
                if for_write:
                    f = self._open(file, 'rb+')
                    self.handles[file] = f
                    self.whandles[file] = 1
                    self.lock_file(file, f)
                else:
                    f = self._open(file, 'rb')
                    self.handles[file] = f
                    if self.lock_while_reading:
                        self.lock_file(file, f)
            except (IOError, OSError), e:
                if DEBUG:
                    print_exc()
                raise IOError('unable to open '+file+': '+str(e))
            
            if self.handlebuffer is not None:
                self.handlebuffer.append(file)
                if len(self.handlebuffer) > self.max_files_open:
                    self._close(self.handlebuffer.pop(0))

        return self.handles[file]


    def _reset_ranges(self):
        self.ranges = []
        for l in self.working_ranges:
            self.ranges.extend(l)
            self.begins = [i[0] for i in self.ranges]

    def _intervals(self, pos, amount):
        r = []
        stop = pos + amount
        p = bisect(self.begins, pos) - 1
        while p < len(self.ranges):
            begin, end, offset, file = self.ranges[p]
            if begin >= stop:
                break
            r.append(( file,
                       offset + max(pos, begin) - begin,
                       offset + min(end, stop) - begin   ))
            p += 1
        return r


    def read(self, pos, amount, flush_first = False):
        r = PieceBuffer()
        for file, pos, end in self._intervals(pos, amount):
            if DEBUG:
                print 'reading '+file+' from '+str(pos)+' to '+str(end)
            self.lock.acquire()
            h = self._get_file_handle(file, False)
            if flush_first and self.whandles.has_key(file):
                h.flush()
                fsync(h)
            h.seek(pos)
            while pos < end:
                length = min(end-pos, MAXREADSIZE)
                data = h.read(length)
                if len(data) != length:
                    raise IOError('error reading data from '+file)
                r.append(data)
                pos += length
            self.lock.release()
        return r

    def write(self, pos, s):
        # might raise an IOError
        total = 0
        for file, begin, end in self._intervals(pos, len(s)):
            if DEBUG:
                print 'writing '+file+' from '+str(pos)+' to '+str(end)
            self.lock.acquire()
            h = self._get_file_handle(file, True)
            h.seek(begin)
            h.write(s[total: total + end - begin])
            self.lock.release()
            total += end - begin

    def top_off(self):
        for begin, end, offset, file in self.ranges:
            l = offset + end - begin
            if l > self.tops.get(file, 0):
                self.lock.acquire()
                h = self._get_file_handle(file, True)
                h.seek(l-1)
                h.write(chr(0xFF))
                self.lock.release()

    def flush(self):
        # may raise IOError or OSError
        for file in self.whandles.keys():
            self.lock.acquire()
            self.handles[file].flush()
            self.lock.release()

    def close(self):
        for file, f in self.handles.items():
            try:
                self.unlock_file(file, f)
            except:
                pass
            try:
                f.close()
            except:
                pass
        self.handles = {}
        self.whandles = {}
        self.handlebuffer = None


    def _get_disabled_ranges(self, f):
        if not self.file_ranges[f]:
            return ((),(),())
        r = self.disabled_ranges[f]
        if r:
            return r
        start, end, offset, file = self.file_ranges[f]
        if DEBUG:
            print 'calculating disabled range for '+self.files[f][0]
            print 'bytes: '+str(start)+'-'+str(end)
            print 'file spans pieces '+str(int(start/self.piece_length))+'-'+str(int((end-1)/self.piece_length)+1)
        pieces = range( int(start/self.piece_length),
                        int((end-1)/self.piece_length)+1 )
        offset = 0
        disabled_files = []
        if len(pieces) == 1:
            if ( start % self.piece_length == 0
                 and end % self.piece_length == 0 ):   # happens to be a single,
                                                       # perfect piece
                working_range = [(start, end, offset, file)]
                update_pieces = []
            else:
                midfile = os.path.join(self.bufferdir,str(f))
                working_range = [(start, end, 0, midfile)]
                disabled_files.append((midfile, start, end))
                length = end - start
                self.sizes[midfile] = length
                piece = pieces[0]
                update_pieces = [(piece, start-(piece*self.piece_length), length)]
        else:
            update_pieces = []
            if start % self.piece_length != 0:  # doesn't begin on an even piece boundary
                end_b = pieces[1]*self.piece_length
                startfile = os.path.join(self.bufferdir,str(f)+'b')
                working_range_b = [ ( start, end_b, 0, startfile ) ]
                disabled_files.append((startfile, start, end_b))
                length = end_b - start
                self.sizes[startfile] = length
                offset = length
                piece = pieces.pop(0)
                update_pieces.append((piece, start-(piece*self.piece_length), length))
            else:
                working_range_b = []
            if f  != len(self.files)-1 and end % self.piece_length != 0:
                                                # doesn't end on an even piece boundary
                start_e = pieces[-1] * self.piece_length
                endfile = os.path.join(self.bufferdir,str(f)+'e')
                working_range_e = [ ( start_e, end, 0, endfile ) ]
                disabled_files.append((endfile, start_e, end))
                length = end - start_e
                self.sizes[endfile] = length
                piece = pieces.pop(-1)
                update_pieces.append((piece, 0, length))
            else:
                working_range_e = []
            if pieces:
                working_range_m = [ ( pieces[0]*self.piece_length,
                                      (pieces[-1]+1)*self.piece_length,
                                      offset, file ) ]
            else:
                working_range_m = []
            working_range = working_range_b + working_range_m + working_range_e

        if DEBUG:            
            print str(working_range)
            print str(update_pieces)
        r = (tuple(working_range), tuple(update_pieces), tuple(disabled_files))
        self.disabled_ranges[f] = r
        return r
        

    def set_bufferdir(self, dir):
        self.bufferdir = dir

    def enable_file(self, f):
        if not self.disabled[f]:
            return
        self.disabled[f] = False
        r = self.file_ranges[f]
        if not r:
            return
        file = r[3]
        if not exists(file):
            h = open(file, 'wb+')
            h.flush()
            h.close()
        if not self.tops.has_key(file):
            self.tops[file] = getsize(file)
        if not self.mtimes.has_key(file):
            self.mtimes[file] = getmtime(file)
        self.working_ranges[f] = [r]

    def disable_file(self, f):
        if self.disabled[f]:
            return
        self.disabled[f] = True
        r = self._get_disabled_ranges(f)
        if not r:
            return
        for file, begin, end in r[2]:
            if not os.path.isdir(self.bufferdir):
                os.makedirs(self.bufferdir)
            if not exists(file):
                h = open(file, 'wb+')
                h.flush()
                h.close()
            if not self.tops.has_key(file):
                self.tops[file] = getsize(file)
            if not self.mtimes.has_key(file):
                self.mtimes[file] = getmtime(file)
        self.working_ranges[f] = r[0]

    reset_file_status = _reset_ranges


    def get_piece_update_list(self, f):
        return self._get_disabled_ranges(f)[1]


    def delete_file(self, f):
        try:
            os.remove(self.files[f][0])
        except:
            pass


    '''
    Pickled data format:

    d['files'] = [ file #, size, mtime {, file #, size, mtime...} ]
                    file # in torrent, and the size and last modification
                    time for those files.  Missing files are either empty
                    or disabled.
    d['partial files'] = [ name, size, mtime... ]
                    Names, sizes and last modification times of files containing
                    partial piece data.  Filenames go by the following convention:
                    {file #, 0-based}{nothing, "b" or "e"}
                    eg: "0e" "3" "4b" "4e"
                    Where "b" specifies the partial data for the first piece in
                    the file, "e" the last piece, and no letter signifying that
                    the file is disabled but is smaller than one piece, and that
                    all the data is cached inside so adjacent files may be
                    verified.
    '''
    def pickle(self):
        files = []
        pfiles = []
        for i in xrange(len(self.files)):
            if not self.files[i][1]:    # length == 0
                continue
            if self.disabled[i]:
                for file, start, end in self._get_disabled_ranges(i)[2]:
                    pfiles.extend([basename(file),getsize(file),getmtime(file)])
                continue
            file = self.files[i][0]
            files.extend([i,getsize(file),getmtime(file)])
        return {'files': files, 'partial files': pfiles}


    def unpickle(self, data):
        # assume all previously-disabled files have already been disabled
        try:
            files = {}
            pfiles = {}
            l = data['files']
            assert len(l) % 3 == 0
            l = [l[x:x+3] for x in xrange(0,len(l),3)]
            for f, size, mtime in l:
                files[f] = (size, mtime)
            l = data.get('partial files',[])
            assert len(l) % 3 == 0
            l = [l[x:x+3] for x in xrange(0,len(l),3)]
            for file, size, mtime in l:
                pfiles[file] = (size, mtime)

            valid_pieces = {}
            for i in xrange(len(self.files)):
                if self.disabled[i]:
                    continue
                r = self.file_ranges[i]
                if not r:
                    continue
                start, end, offset, file =r
                if DEBUG:
                    print 'adding '+file
                for p in xrange( int(start/self.piece_length),
                                 int((end-1)/self.piece_length)+1 ):
                    valid_pieces[p] = 1

            if DEBUG:
                print valid_pieces.keys()
            
            def test(old, size, mtime):
                oldsize, oldmtime = old
                if size != oldsize:
                    return False
                if mtime > oldmtime+1:
                    return False
                if mtime < oldmtime-1:
                    return False
                return True

            for i in xrange(len(self.files)):
                if self.disabled[i]:
                    for file, start, end in self._get_disabled_ranges(i)[2]:
                        f1 = basename(file)
                        if ( not pfiles.has_key(f1)
                             or not test(pfiles[f1],getsize(file),getmtime(file)) ):
                            if DEBUG:
                                print 'removing '+file
                            for p in xrange( int(start/self.piece_length),
                                             int((end-1)/self.piece_length)+1 ):
                                if valid_pieces.has_key(p):
                                    del valid_pieces[p]
                    continue
                file, size = self.files[i]
                if not size:
                    continue
                if ( not files.has_key(i)
                     or not test(files[i],getsize(file),getmtime(file)) ):
                    start, end, offset, file = self.file_ranges[i]
                    if DEBUG:
                        print 'removing '+file
                    for p in xrange( int(start/self.piece_length),
                                     int((end-1)/self.piece_length)+1 ):
                        if valid_pieces.has_key(p):
                            del valid_pieces[p]
        except:
            if DEBUG:
                print_exc()
            return []

        if DEBUG:
            print valid_pieces.keys()                        
        return valid_pieces.keys()


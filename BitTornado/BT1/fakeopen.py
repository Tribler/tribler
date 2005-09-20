# Written by Bram Cohen
# see LICENSE.txt for license information

from string import join

class FakeHandle:
    def __init__(self, name, fakeopen):
        self.name = name
        self.fakeopen = fakeopen
        self.pos = 0
    
    def flush(self):
        pass
    
    def close(self):
        pass
    
    def seek(self, pos):
        self.pos = pos
    
    def read(self, amount = None):
        old = self.pos
        f = self.fakeopen.files[self.name]
        if self.pos >= len(f):
            return ''
        if amount is None:
            self.pos = len(f)
            return join(f[old:], '')
        else:
            self.pos = min(len(f), old + amount)
            return join(f[old:self.pos], '')
    
    def write(self, s):
        f = self.fakeopen.files[self.name]
        while len(f) < self.pos:
            f.append(chr(0))
        self.fakeopen.files[self.name][self.pos : self.pos + len(s)] = list(s)
        self.pos += len(s)

class FakeOpen:
    def __init__(self, initial = {}):
        self.files = {}
        for key, value in initial.items():
            self.files[key] = list(value)
    
    def open(self, filename, mode):
        """currently treats everything as rw - doesn't support append"""
        self.files.setdefault(filename, [])
        return FakeHandle(filename, self)

    def exists(self, file):
        return self.files.has_key(file)

    def getsize(self, file):
        return len(self.files[file])

def test_normal():
    f = FakeOpen({'f1': 'abcde'})
    assert f.exists('f1')
    assert not f.exists('f2')
    assert f.getsize('f1') == 5
    h = f.open('f1', 'rw')
    assert h.read(3) == 'abc'
    assert h.read(1) == 'd'
    assert h.read() == 'e'
    assert h.read(2) == ''
    h.write('fpq')
    h.seek(4)
    assert h.read(2) == 'ef'
    h.write('ghij')
    h.seek(0)
    assert h.read() == 'abcdefghij'
    h.seek(2)
    h.write('p')
    h.write('q')
    assert h.read(1) == 'e'
    h.seek(1)
    assert h.read(5) == 'bpqef'

    h2 = f.open('f2', 'rw')
    assert h2.read() == ''
    h2.write('mnop')
    h2.seek(1)
    assert h2.read() == 'nop'
    
    assert f.exists('f1')
    assert f.exists('f2')
    assert f.getsize('f1') == 10
    assert f.getsize('f2') == 4

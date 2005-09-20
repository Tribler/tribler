# Written by John Hoffman
# see LICENSE.txt for license information

'''
reads/writes a Windows-style INI file
format:

  aa = "bb"
  cc = 11

  [eee]
  ff = "gg"

decodes to:
d = { '': {'aa':'bb','cc':'11'}, 'eee': {'ff':'gg'} }

the encoder can also take this as input:

d = { 'aa': 'bb, 'cc': 11, 'eee': {'ff':'gg'} }

though it will only decode in the above format.  Keywords must be strings.
Values that are strings are written surrounded by quotes, and the decoding
routine automatically strips any.
Booleans are written as integers.  Anything else aside from string/int/float
may have unpredictable results.
'''

from cStringIO import StringIO
from traceback import print_exc
from types import DictType, StringType
try:
    from types import BooleanType
except ImportError:
    BooleanType = None

try:
    True
except:
    True = 1
    False = 0

DEBUG = False

def ini_write(f, d, comment=''):
    try:
        a = {'':{}}
        for k,v in d.items():
            assert type(k) == StringType
            k = k.lower()
            if type(v) == DictType:
                if DEBUG:
                    print 'new section:' +k
                if k:
                    assert not a.has_key(k)
                    a[k] = {}
                aa = a[k]
                for kk,vv in v:
                    assert type(kk) == StringType
                    kk = kk.lower()
                    assert not aa.has_key(kk)
                    if type(vv) == BooleanType:
                        vv = int(vv)
                    if type(vv) == StringType:
                        vv = '"'+vv+'"'
                    aa[kk] = str(vv)
                    if DEBUG:
                        print 'a['+k+']['+kk+'] = '+str(vv)
            else:
                aa = a['']
                assert not aa.has_key(k)
                if type(v) == BooleanType:
                    v = int(v)
                if type(v) == StringType:
                    v = '"'+v+'"'
                aa[k] = str(v)
                if DEBUG:
                    print 'a[\'\']['+k+'] = '+str(v)
        r = open(f,'w')
        if comment:
            for c in comment.split('\n'):
                r.write('# '+c+'\n')
            r.write('\n')
        l = a.keys()
        l.sort()
        for k in l:
            if k:
                r.write('\n['+k+']\n')
            aa = a[k]
            ll = aa.keys()
            ll.sort()
            for kk in ll:
                r.write(kk+' = '+aa[kk]+'\n')
        success = True
    except:
        if DEBUG:
            print_exc()
        success = False
    try:
        r.close()
    except:
        pass
    return success


if DEBUG:
    def errfunc(lineno, line, err):
        print '('+str(lineno)+') '+err+': '+line
else:
    errfunc = lambda lineno, line, err: None

def ini_read(f, errfunc = errfunc):
    try:
        r = open(f,'r')
        ll = r.readlines()
        d = {}
        dd = {'':d}
        for i in xrange(len(ll)):
            l = ll[i]
            l = l.strip()
            if not l:
                continue
            if l[0] == '#':
                continue
            if l[0] == '[':
                if l[-1] != ']':
                    errfunc(i,l,'syntax error')
                    continue
                l1 = l[1:-1].strip().lower()
                if not l1:
                    errfunc(i,l,'syntax error')
                    continue
                if dd.has_key(l1):
                    errfunc(i,l,'duplicate section')
                    d = dd[l1]
                    continue
                d = {}
                dd[l1] = d
                continue
            try:
                k,v = l.split('=',1)
            except:
                try:
                    k,v = l.split(':',1)
                except:
                    errfunc(i,l,'syntax error')
                    continue
            k = k.strip().lower()
            v = v.strip()
            if len(v) > 1 and ( (v[0] == '"' and v[-1] == '"') or
                                (v[0] == "'" and v[-1] == "'") ):
                v = v[1:-1]
            if not k:
                errfunc(i,l,'syntax error')
                continue
            if d.has_key(k):
                errfunc(i,l,'duplicate entry')
                continue
            d[k] = v
        if DEBUG:
            print dd
    except:
        if DEBUG:
            print_exc()
        dd = None
    try:
        r.close()
    except:
        pass
    return dd

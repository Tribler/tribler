# Written by Petru Paler, Uoti Urpala, Ross Cohen and John Hoffman
# see LICENSE.txt for license information

from types import IntType, LongType, StringType, ListType, TupleType, DictType
try:
    from types import BooleanType
except ImportError:
    BooleanType = None
try:
    from types import UnicodeType
except ImportError:
    UnicodeType = None

from traceback import print_exc, print_stack
import logging

logger = logging.getLogger(__name__)


def decode_int(x, f):
    f += 1
    newf = x.index('e', f)
    try:
        n = int(x[f:newf])
    except:
        n = long(x[f:newf])
    if x[f] == '-':
        if x[f + 1] == '0':
            raise ValueError
    elif x[f] == '0' and newf != f + 1:
        raise ValueError
    return (n, newf + 1)


def decode_string(x, f):
    colon = x.index(':', f)
    try:
        n = int(x[f:colon])
    except (OverflowError, ValueError):
        n = long(x[f:colon])
    if x[f] == '0' and colon != f + 1:
        raise ValueError
    colon += 1
    return (x[colon:colon + n], colon + n)


def decode_unicode(x, f):
    s, f = decode_string(x, f + 1)
    return (s.decode('UTF-8'), f)


def decode_list(x, f):
    r, f = [], f + 1
    while x[f] != 'e':
        v, f = decode_func[x[f]](x, f)
        r.append(v)
    return (r, f + 1)


def decode_dict(x, f):
    r, f = {}, f + 1
    lastkey = None
    while x[f] != 'e':
        k, f = decode_string(x, f)
        # Arno, 2008-09-12: uTorrent 1.8 violates the bencoding spec, its keys
        # in an EXTEND handshake message are not sorted. Be liberal in what we
        # receive:
        # if lastkey >= k:
        # raise ValueError
        lastkey = k
        r[k], f = decode_func[x[f]](x, f)
    return (r, f + 1)

decode_func = {}
decode_func['l'] = decode_list
decode_func['d'] = decode_dict
decode_func['i'] = decode_int
decode_func['0'] = decode_string
decode_func['1'] = decode_string
decode_func['2'] = decode_string
decode_func['3'] = decode_string
decode_func['4'] = decode_string
decode_func['5'] = decode_string
decode_func['6'] = decode_string
decode_func['7'] = decode_string
decode_func['8'] = decode_string
decode_func['9'] = decode_string
# decode_func['u'] = decode_unicode


def bdecode(x, sloppy=0):
    r, l = sloppy_bdecode(x)
    if not sloppy and l != len(x):
        raise ValueError("bad bencoded data")
    return r


def sloppy_bdecode(x):
    """
    Same as bdecode, except that it returns the decoded data AND the number of bytes read from X.
    """
    try:
        r, l = decode_func[x[0]](x, 0)
#    except (IndexError, KeyError):
    except (IndexError, KeyError, ValueError):
        # print_exc()
        raise ValueError("bad bencoded data")
    return r, l


def test_bdecode():
    try:
        bdecode('0:0:')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('ie')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('i341foo382e')
        assert 0
    except ValueError:
        pass
    assert bdecode('i4e') == 4
    assert bdecode('i0e') == 0
    assert bdecode('i123456789e') == 123456789
    assert bdecode('i-10e') == -10
    try:
        bdecode('i-0e')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('i123')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('i6easd')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('35208734823ljdahflajhdf')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('2:abfdjslhfld')
        assert 0
    except ValueError:
        pass
    assert bdecode('0:') == ''
    assert bdecode('3:abc') == 'abc'
    assert bdecode('10:1234567890') == '1234567890'
    try:
        bdecode('02:xy')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('l')
        assert 0
    except ValueError:
        pass
    assert bdecode('le') == []
    try:
        bdecode('leanfdldjfh')
        assert 0
    except ValueError:
        pass
    assert bdecode('l0:0:0:e') == ['', '', '']
    try:
        bdecode('relwjhrlewjh')
        assert 0
    except ValueError:
        pass
    assert bdecode('li1ei2ei3ee') == [1, 2, 3]
    assert bdecode('l3:asd2:xye') == ['asd', 'xy']
    assert bdecode('ll5:Alice3:Bobeli2ei3eee') == [['Alice', 'Bob'], [2, 3]]
    try:
        bdecode('d')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('defoobar')
        assert 0
    except ValueError:
        pass
    assert bdecode('de') == {}
    assert bdecode('d3:agei25e4:eyes4:bluee') == {'age': 25, 'eyes': 'blue'}
    assert bdecode('d8:spam.mp3d6:author5:Alice6:lengthi100000eee') == {
        'spam.mp3': {'author': 'Alice', 'length': 100000}}
    try:
        bdecode('d3:fooe')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('di1e0:e')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('d1:b0:1:a0:e')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('d1:a0:1:a0:e')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('i03e')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('l01:ae')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('9999:x')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('l0:')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('d0:0:')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('d0:')
        assert 0
    except ValueError:
        pass

bencached_marker = []


class Bencached:

    def __init__(self, s):
        self.marker = bencached_marker
        self.bencoded = s

BencachedType = type(Bencached(''))  # insufficient, but good as a filter


def encode_bencached(x, r):
    assert x.marker == bencached_marker
    r.append(x.bencoded)


def encode_int(x, r):
    r.extend(('i', str(x), 'e'))


def encode_bool(x, r):
    encode_int(int(x), r)


def encode_string(x, r):
    r.extend((str(len(x)), ':', x))


def encode_unicode(x, r):
    # r.append('u')
    encode_string(x.encode('UTF-8'), r)


def encode_list(x, r):
    r.append('l')
    for e in x:
        encode_func[type(e)](e, r)
    r.append('e')


def encode_dict(x, r):
    r.append('d')
    ilist = x.items()
    ilist.sort()
    for k, v in ilist:
        # logger.debug("bencode: Encoding %s %s", k, v)

        try:
            r.extend((str(len(k)), ':', k))
        except:
            logger.error("k: %s", k)
            raise

        encode_func[type(v)](v, r)
    r.append('e')

encode_func = {}
encode_func[BencachedType] = encode_bencached
encode_func[IntType] = encode_int
encode_func[LongType] = encode_int
encode_func[StringType] = encode_string
encode_func[ListType] = encode_list
encode_func[TupleType] = encode_list
encode_func[DictType] = encode_dict
if BooleanType:
    encode_func[BooleanType] = encode_bool
# Arno, 2010-01-27: No more implicit Unicode support.
# We should disable this now and then to see if the higher layers properly
# UTF-8 encode their fields before calling bencode
if UnicodeType:
    encode_func[UnicodeType] = encode_unicode


def bencode(x):
    r = []
    try:
        encode_func[type(x)](x, r)
    except:
        logger.error("bencode: *** error *** could not encode type %s (value: %s)", type(x), x)
        print_stack()

        print_exc()
        assert 0
    try:
        return ''.join(r)
    except:
        logger.debug("bencode: join error %s", x)
        for elem in r:
            logger.debug("elem %s has type %s", elem, type(elem))
        print_exc()
        return ''


def test_bencode():
    assert bencode(4) == 'i4e'
    assert bencode(0) == 'i0e'
    assert bencode(-10) == 'i-10e'
    assert bencode(12345678901234567890) == 'i12345678901234567890e'
    assert bencode('') == '0:'
    assert bencode('abc') == '3:abc'
    assert bencode('1234567890') == '10:1234567890'
    assert bencode([]) == 'le'
    assert bencode([1, 2, 3]) == 'li1ei2ei3ee'
    assert bencode([['Alice', 'Bob'], [2, 3]]) == 'll5:Alice3:Bobeli2ei3eee'
    assert bencode({}) == 'de'
    assert bencode({'age': 25, 'eyes': 'blue'}) == 'd3:agei25e4:eyes4:bluee'
    assert bencode({'spam.mp3': {'author': 'Alice', 'length': 100000}}
                   ) == 'd8:spam.mp3d6:author5:Alice6:lengthi100000eee'
    try:
        bencode({1: 'foo'})
        assert 0
    except AssertionError:
        pass


try:
    import psyco
    psyco.bind(bdecode)
    psyco.bind(bencode)
except ImportError:
    pass

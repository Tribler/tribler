from tribler.core.utilities.limited_ordered_dict import LimitedOrderedDict


def test_order():
    d = LimitedOrderedDict()
    d['first'] = '1'
    d['second'] = '2'
    d['third'] = '3'

    assert list(d.keys()) == ['first', 'second', 'third']


def test_limit():
    d = LimitedOrderedDict(limit=2)
    d['first'] = '1'
    d['second'] = '2'
    d['third'] = '3'

    assert list(d.keys()) == ['second', 'third']


def test_merge():
    d1 = {'first': 1, 'second': 2}
    d2 = {'third': 3, 'fourth': 4}

    d = LimitedOrderedDict({**d1, **d2}, limit=2)
    assert len(d) == 2

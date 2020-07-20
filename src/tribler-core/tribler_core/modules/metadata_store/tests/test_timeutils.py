import datetime

from tribler_core.modules.metadata_store.serialization import EPOCH, int2time, time2int


def test_time_convert():
    """
    Test converting various datetime objects to float
    """
    test_time_list = [
        datetime.datetime(2005, 7, 14, 12, 30, 12),
        datetime.datetime(2039, 7, 14, 12, 30, 12),
        datetime.datetime.utcnow().replace(second=0, microsecond=0),
    ]
    for test_time in test_time_list:
        assert test_time == int2time(time2int(test_time))


def test_zero_time():
    """
    Test whether a time of zero converts to the epoch time
    """
    assert int2time(0.0) == EPOCH


def test_negative_time():
    """
    Test whether we are able to deal with time below the epoch time
    """
    negative_time = EPOCH - datetime.timedelta(1)
    assert negative_time == int2time(time2int(negative_time))

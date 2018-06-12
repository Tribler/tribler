from __future__ import division
from datetime import datetime, timedelta

def time2float(dt, epoch=datetime(1970,1,1)):
    # WARNING: TZ-aware timestamps are madhouse...
    # For Python3 we could use a simpler method:
    # timestamp = (dt - datetime(1970,1,1, tzinfo=timezone.utc)) / timedelta(seconds=1)

    td = dt - epoch
    # return td.total_seconds()
    return float((td.microseconds + (td.seconds + td.days * 86400) * 10**6) / 10**6)

def float2time(ts, epoch=datetime(1970,1,1)):
    microseconds_total = int(ts * 10**6)
    microseconds = microseconds_total % 10**6
    seconds_total = (microseconds_total - microseconds)/10**6
    seconds = seconds_total % 86400
    days = (seconds_total - seconds)/86400
    dt = epoch + timedelta(days=days, seconds=seconds, microseconds=microseconds)
    return dt

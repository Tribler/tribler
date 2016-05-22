from datetime import datetime
from random import randint


def format_size(num, suffix='B'):
    for unit in ['','k','M','G','T','P','E','Z']:
        if abs(num) < 1024.0:
            return "%3.1f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f %s%s" % (num, 'Yi', suffix)


def format_speed(num):
    return "%s/s" % format_size(num)


def seconds_to_string(seconds):
    minutes = seconds / 60
    seconds_left = seconds % 60
    return "%d:%02d" % (minutes, seconds_left)


def timestamp_to_time(timestamp):
    today = datetime.today()
    discovered = datetime.fromtimestamp(timestamp)

    diff = today - discovered
    if diff.days > 0 or today.day != discovered.day:
        return discovered.strftime('%d-%m-%Y')
    return discovered.strftime('Today %H:%M')


def get_random_color():
    red = randint(127, 255)
    green = randint(127, 255)
    blue = randint(127, 255)
    return '#%02x%02x%02x' % (red, green, blue)

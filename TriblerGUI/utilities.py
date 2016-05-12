def format_size(num, suffix='B'):
    for unit in ['','K','M','G','T','P','E','Z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def seconds_to_string(seconds):
    minutes = seconds / 60
    seconds_left = seconds % 60
    return "%d:%02d" % (minutes, seconds_left)

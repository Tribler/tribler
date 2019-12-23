import random


def get_random_hex_string(length):
    return ''.join([random.choice('0123456789abcdef') for _ in range(length)])


def get_random_unicode_string(length):
    # Update this to include code point ranges to be sampled
    include_ranges = [
        (0x0021, 0x0021),
        (0x0023, 0x0026),
        (0x0028, 0x007E),
        (0x00A1, 0x00AC),
        (0x00AE, 0x00FF),
        (0x0100, 0x017F),
        (0x0180, 0x024F),
        (0x2C60, 0x2C7F),
        (0x16A0, 0x16F0),
        (0x0370, 0x0377),
        (0x037A, 0x037E),
        (0x0384, 0x038A),
        (0x038C, 0x038C),
    ]

    alphabet = [chr(code_point) for current_range in include_ranges
                for code_point in range(current_range[0], current_range[1] + 1)]
    return ''.join(random.choice(alphabet) for _ in range(length))


def get_random_filename():
    filename = get_random_unicode_string(random.randint(1, 30))
    extensions = ['.exe', '.avi', '.docx', '.xls', '.dmg', '.mp3', '.sh', '.txt', '.info']
    return filename + random.choice(extensions)

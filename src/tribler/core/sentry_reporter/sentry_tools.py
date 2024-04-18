""" This a collection of tools for SentryReporter and SentryScrubber aimed to
simplify work with several data structures.
"""
import re
from dataclasses import dataclass
from typing import Optional

from faker import Faker

LONG_TEXT_DELIMITER = '--LONG TEXT--'
CONTEXT_DELIMITER = '--CONTEXT--'

# Find an exception in the string like: "OverflowError: bind(): port must be 0-65535"
_re_search_exception = re.compile(r'^([A-Za-z0-9_.]+):\s+(.+)')
_re_search_exception_exclusions = re.compile(r'(?:warning)', re.RegexFlag.IGNORECASE)

# Remove the substring like "Sentry is attempting to send 1 pending error messages"
_re_remove_sentry = re.compile(r'Sentry is attempting.*')


def parse_os_environ(array):
    """Parse os.environ field.

    Args:
        array: strings that represents tuples delimited by `:`
            Example: ["KEY:VALUE", "PATH:~/"]

    Returns:
        Dictionary that made from given array.
            Example: {"KEY": "VALUE", "PATH": "~/"}

    """
    result = {}

    if not array:
        return result

    for line in array:
        items = line.split(':', 1)
        if len(items) < 2:
            continue
        result[items[0]] = items[1]

    return result


def parse_stacktrace(stacktrace, delimiters=None):
    """Parse stacktrace field.

    Example of stacktrace:
        Traceback (most recent call last):,
              File "src\run_tribler.py", line 179, in <module>,
            RuntimeError: ('\'utf-8\' codec can\'t decode byte 0xcd in position 0: invalid continuation byte,
        --LONG TEXT--,
            Traceback (most recent call last):,
              File "<user>\\asyncio\\events.py", line 81, in _run,
            UnicodeDecodeError: \'utf-8\' codec can\'t decode byte 0xcd in position 0: invalid continuation byte,
        --CONTEXT--,
            {\'message\': "Exception in callback'
    Args:
        stacktrace: the string that represents stacktrace.

        delimiters: hi-level delimiters of the stacktrace.
            ['--LONG TEXT--', '--CONTEXT--'] by default.

    Returns:
        The generator of stacktrace parts.
    """
    if not stacktrace:
        return

    delimiters = delimiters or [LONG_TEXT_DELIMITER, CONTEXT_DELIMITER]

    for part in re.split('|'.join(delimiters), stacktrace):
        yield [line for line in re.split(r'\\n|\n', part) if line]


@dataclass
class LastCoreException:
    type: str
    message: str


def parse_last_core_output(text: str) -> Optional[LastCoreException]:
    """ This function tries to find an Exception type and the Exception message in the raw core output
    """

    def _clean_up(s: str):
        return _re_remove_sentry.sub('', s).strip()

    for line in reversed(text.split('\n')):
        if m := _re_search_exception.match(line):
            exception_type = m.group(1)
            if _re_search_exception_exclusions.search(exception_type):
                continue  # find an exclusion

            return LastCoreException(type=_clean_up(exception_type),
                                     message=_clean_up(m.group(2)))
    return None


def get_first_item(items, default=None):
    return items[0] if items else default


def get_last_item(items, default=None):
    return items[-1] if items else default


def delete_item(d, key):
    if not d:
        return d

    if key in d:
        del d[key]
    return d


def get_value(d, key, default=None):
    return d.get(key, default) if d else default


def extract_dict(d, regex_key_pattern):
    if not d or not regex_key_pattern:
        return dict()

    matched_keys = [key for key in d if re.match(regex_key_pattern, key)]
    return {key: d[key] for key in matched_keys}


def modify_value(d, key, function):
    if not d or not key or not function:
        return d

    if key in d:
        d[key] = function(d[key])

    return d


def distinct_by(list_of_dict, key):
    """This function removes all duplicates from a list of dictionaries. A duplicate
    here is a dictionary that have the same value of the given key.

    If no key field is presented in the item, then the item will not be considered
    as a duplicate.

    Args:
        list_of_dict: list of dictionaries
        key: a field key that will be used for items comparison

    Returns:
        Array of distinct items
    """

    if not list_of_dict or not key:
        return list_of_dict

    values_viewed = set()
    result = []

    for item in list_of_dict:
        value = get_value(item, key, None)
        if value is None:
            result.append(item)
            continue

        if value not in values_viewed:
            result.append(item)

        values_viewed.add(value)

    return result


def format_version(version: Optional[str]) -> Optional[str]:
    if not version:
        return version

    # For the release version let's ignore all "developers" versions
    # to keep the meaning of the `latest` keyword:
    # See Also:https://docs.sentry.io/product/sentry-basics/search/
    if 'GIT' in version:
        return 'dev'

    parts = version.split('-', maxsplit=2)
    if len(parts) < 2:
        return version

    # if version has been produced by deployment tester, then
    if parts[1].isdigit():
        return parts[0]

    # for all other cases keep <version>-<first_part>
    return f"{parts[0]}-{parts[1]}"


def obfuscate_string(s: str, part_of_speech: str = 'noun') -> str:
    """Obfuscate string by replacing it with random word.

    The same random words will be generated for the same given strings.
    """
    faker = Faker(locale='en_US')
    faker.seed_instance(s)
    return faker.word(part_of_speech=part_of_speech)

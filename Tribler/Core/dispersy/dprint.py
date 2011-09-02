"""
Easily print a message to the console or a remote application

It is important to note that this module must be as independent from
other user made modules as possible since dprint is often used to
report bugs in other modules.
"""

# todo: maybe add a feature that does not redisplay a msg that repeats itself again and again

# from pickle import dumps
from os.path import dirname, basename, expanduser, isfile, join
from sys import stdout, stderr, exc_info
# from threading import current_thread, Thread, Lock
from time import time, strftime
from traceback import extract_stack, print_exception, print_stack, format_list
import inspect
import re
# import socket
# from os import getcwd
from pprint import pformat

# maxsize is introduced in Python 2.6
try:
    from sys import maxsize
except ImportError:
    from sys import maxint as maxsize

LEVEL_DEBUG = 0
LEVEL_NORMAL = 128
LEVEL_LOG = 142
LEVEL_NOTICE = 167
LEVEL_WARNING = 192
LEVEL_ERROR = 224
LEVEL_FORCE = 1024
level_map = {"debug":LEVEL_DEBUG,       # informative only to a developer
             "normal":LEVEL_NORMAL,     # informative to a user running from console
             "log":LEVEL_LOG,           # a message that is logged
             "notice":LEVEL_NOTICE,     # something is wrong but we can recover (external failure, we are not the cause nor can we fix this)
             "warning":LEVEL_WARNING,   # something is wrong but we can recover (internal failure, we are the cause and should fix this)
             "error":LEVEL_ERROR,       # something is wrong and recovering is impossible
             "force":LEVEL_FORCE}       # explicitly force this print to pass through the filter
level_tag_map = {LEVEL_DEBUG:"D",
                 LEVEL_NORMAL:" ",
                 LEVEL_LOG:"L",
                 LEVEL_NOTICE:"N",
                 LEVEL_WARNING:"W",
                 LEVEL_ERROR:"E",
                 LEVEL_FORCE:"F"}

# allows us to determine that the last dprint call was an error, and hence, that the message 'see
# stderr...' has already been printed to stdout
_last_dprint_see_stderr = False

_dprint_settings = {
    "binary":False,                     # print a binary representation of the arguments
    "box":False,                        # add a single line above and below the message
    "box_char":"-",                     # when a box is added to the message use this character to generate the line
    "box_width":80,                     # when a box is added to the message make the lines this long
    "callback":None,                    # optional callback. the callback is only performed if the filters accept the message. the callback result is added to the displayed message
    "exception":False,                  # add the last occured exception, including its stacktrace, to the message
    "force":False,                      # ignore all filters, equivalent to level="force"
    "glue":"",                          # use this string to join() *args together
    "level":LEVEL_NORMAL,               # either "debug", "normal", "warning", "error", or a number in the range [0, 255]
    "line":False,                       # add a single line above the message
    "line_char":"-",                    # when a line is added to the message use this character to generate the line
    "line_width":80,                    # when a line is added to the message make the line this long
    "lines":False,                      # write each value on a seperate line
    "meta":False,                       # write each value on a seperate line including metadata
    "pprint":False,                     # pretty print arg[0] if there is only one argument, otherwize pretty print arg
    "remote":False,                     # write message to remote logging application
    "remote_host":"localhost",          # when remote logging is enabled this hostname is used
    "remote_port":12345,                # when remote logging is enabled this port is used
    "source_file":None,                 # force a source filename. otherwise the filename is retrieved from the callstack
    "source_function":None,             # force a source function. otherwise the function is retrieved from the callstack
    "source_line":None,                 # force a source line. otherwise the line number is retrieved from the callstack
    "stack":False,                      # add a stacktrace to the message. optionally this can be a list optained through extract_stack()
    "stack_ident":None,                 # when stack is printed use this ident to determine the thread name
    "stack_origin_modifier":-1,         # modify the length of the callstack that is displayed and used to retrieve the source-filename, -function, and -line
    "stderr":False,                     # write message to sys.stderr
    "stdout":True,                      # write message to sys.stdout
    "style":"column",                   # output style. either "short" or "column"
    "time":False,                       # include a timestamp at the start of each line
    "time_format":"%H:%M:%S"}           # the timestamp format (see strftime)

# We allow message filtering in a 'iptables like' fashion. Each
# messages is passed to the ENTRY chain in _dprint_filters, when a
# filter in the chain matches its target is used (accept, drop,
# continue, or jump). If no filters in a chain match the default chain
# policy (accept/True, drop/False, or return/None) is used. An
# exception to this is the ENTRY chain which may only use accept and
# drop its default.
#
# _dprint_filters contains chain-name:[policy, chain-list]
# pairs. Where policy can be accept/True, drop/False, or return/None.
#
# chain-list contains lists in the form: [function, target]. Where
# target can be accept/True, drop/False, continue/None, or
# jump/callable.
_filters = {"ENTRY":[True, []]}
_filter_entry = _filters["ENTRY"]
_filter_policy_map = {"accept":True, "drop":False, "return":None}
_filter_reverse_policy_map = {True:"accept", False:"drop", None:"return"}
_filter_reverse_target_map = {True:"accept", False:"drop", None:"continue"}
_filter_target_map = {"accept":True, "drop":False, "continue":None}

def _filter_reverse_dictionary_lookup(dic, value):
    """Returns key associated with the first value that matches VALUE"""
    for key, value_ in dic.items():
        if value is value_:
            return key
    return None

def filter_chains_get():
    """
    Return a list of (chain-name, default-policy) tuples.

    Where chain-name is the name of the chain. And where
    default-policy is either accept, drop, or return.
    """
    return [(chain, _filter_reverse_policy_map[policy]) for chain, (policy, rules) in _filters.items()]

def filter_get(chain):
    """
    Return a list of (check, target, jump) tuples.

    Where check is the name of the function used to check the
    rule. Where target is either accept, drop, continue, or jump. And
    where jump is either None or the name of the target chain.
    """
    assert chain in _filters, chain
    return [(function.__name__,
             target in (True, False, None) and _filter_reverse_target_map[target] or "jump",
             not target in (True, False, None) and _filter_reverse_dictionary_lookup(_filters, target) or None)
            for function, target
            in _filters[chain][1]]

def filter_chain_create(chain, policy):
    """
    Create a new chain

    CHAIN must indicate a non-existing chain ("ENTRY" always exists)
    POLICY must be either accept, drop, or return
    """
    assert not chain in _filters, "Chain \"%s\" already exists" % chain
    assert policy in _filter_policy_map, "Invalid policy \"%s\"" % policy
    _filters[chain] = [_filter_policy_map[policy], []]

def filter_chain_policy(chain, policy):
    """
    Set the policy of an exiting chain

    CHAIN must indicate an existing chain ("ENTRY" always exists)
    POLICY must be either accept, drop, or return
    """
    assert chain in _filters, "Unknown chain \"%s\"" % chain
    assert policy in _filter_policy_map, "Invalid policy \"%s\"" % policy
    _filters[chain][0] = _filter_policy_map[policy]

def filter_chain_remove(chain):
    """
    Remove an existing chain
    """
    assert chain in _filters, chain
    # todo: also remove jumps to this chain
    del _filters[chain]

def filter_add(chain, function, target, jump=None, position=maxsize):
    """
    Add a filter entry to an existing chain.

    CHAIN must indicate an existing chain ("ENTRY" always exists)
    FUNCTION must be a callable function that returns True or False
    TARGET must be either accept, drop, continue, or jump
    JUMP must be an existing chain name when TARGET is jump
    POSITION indicates the position in the chain to insert the rule. The default is the end of the chain
    """
    assert chain in _filters, chain
    assert hasattr(function, "__call__"), function
    assert target == "jump" or target in _filter_target_map, "Invalid target [%s]" % target
    assert target != "jump" or jump in _filters, jump
    assert type(position) is int, position
    if target in _filter_target_map:
        target = _filter_target_map[target]
    else:
        target =_filters[jump]
    _filters[chain][1].insert(position, [function, target])

def filter_remove(chain, position):
    """
    Remove the n'th rule from an existing chain

    CHAIN must indicate an existing chain ("ENTRY" always exists)
    POSITION indicates the n'th rule in the chain. The first rule has number 0
    """
    assert chain in _filters, chain
    assert -len(_filters[chain][1]) < position < len(_filters[chain][1]), position
    del _filters[chain][1][position]

def filter_add_by_source(chain, target, file=None, function=None, path=None, jump=None, position=maxsize):
    """
    Helper function for filter_add to add a filter on the message source

    CHAIN must indicate an existing chain ("ENTRY" always exists)
    TARGET must be either accept, drop, continue, or jump
    FILE indicates an optional file path. matches if: source_file.endswith(FILE)
    FUNCTION indicates an optional function. matches if: source_function == FUNCTION
    PATH indicates an optional path. directory seperators should be '.' and not OS dependend '/', or '\', etc. matches if: PATH in source_file
    JUMP must be an existing chain name when TARGET is jump
    POSITION indicates the position in the chain to insert the rule. The default is the end of the chain

    At least one of FILE, FUNCTION, or PATH must be given. When more
    then one are given the source message will match if all given
    filters match.
    """
    # assert for CHAIN is done in filter_add
    # assert for TARGET is done in filter_add
    # assert for POSITION is done in filter_add
    # assert for JUMP is done in filter_add
    assert file or function or path, "At least one of FILE, FUNCTION, or PATH must be given"
    assert file is None or type(file) is str, file
    assert function is None or type(function) is str, function
    assert path is None or type(path) is str, path
    def match(args, settings):
        result = True
        if file: result = result and settings["source_file"].endswith(file)
        if path: result = result and path in settings["source_file"]
        if function: result = result and function == settings["source_function"]
        return result
    if not path is None:
        path = join(*path.split("."))
    match.__name__ = "by_source(%s, %s, %s)" % (file, function, path)
    filter_add(chain, match, target, jump=jump, position=position)

def filter_add_by_level(chain, target, exact=None, min=None, max=None, jump=None, position=maxsize):
    """
    Helper function for filter_add to add a filter on the message level

    CHAIN must indicate an existing chain ("ENTRY" always exists)
    TARGET must be either accept, drop, continue, or jump
    EXACT indicates an exact message level. matches if: level == EXACT
    MIN indicates a minimal message level. matches if: MIN <= level <= MAX
    MAX indicates a maximum message level. matches if: MIN <= level <= MAX
    JUMP must be an existing chain name when TARGET is jump
    POSITION indicates the position in the chain to insert the rule. The default is the end of the chain

    It is not allowed to give MIN without MAX or vise-versa.

    Either EXACT or (MIN and MAX) must be given. When both EXACT and
    (MIN and MAX) are given only EXACT is used.
    """
    # assert for CHAIN is done in filter_add
    # assert for TARGET is done in filter_add
    # assert for POSITION is done in filter_add
    # assert for JUMP is done in filter_add
    assert exact is None or exact in level_map or type(exact) is int, exact
    assert min is None or min in level_map or type(min) is int, min
    assert max is None or max in level_map or type(max) is int, max
    assert (min is None and max is None) or (not min is None and not max is None), (min, max)
    if exact in level_map: exact = level_map[exact]
    if min in level_map: min = level_map[min]
    if max in level_map: max = level_map[max]
    if exact is None:
        def match(args, settings):
            return min <= settings["level"] <= max
    else:
        def match(args, settings):
            print "match", exact, "==", settings["level"]
            return exact == settings["level"]
    match.__name__ = "by_level(%s, %s, %s)" % (exact, min, max)
    filter_add(chain, match, target, jump=jump, position=position)

def filter_add_by_pattern(chain, target, pattern, jump=None, position=maxsize):
    """
    Helper function for filter_add to add a regular expression filter on the message

    CHAIN must indicate an existing chain ("ENTRY" always exists)
    TARGET must be either accept, drop, continue, or jump
    PATTERN is a regular expression. matches if any: re.match(PATTERN, str(arg)) where arg is any argument to dprint
    JUMP must be an existing chain name when TARGET is jump
    POSITION indicates the position in the chain to insert the rule. The default is the end of the chain
    """
    # assert for CHAIN is done in filter_add
    # assert for TARGET is done in filter_add
    # assert for POSITION is done in filter_add
    # assert for JUMP is done in filter_add
    assert type(pattern) is str, "Pattern must be a string [%s]" % pattern
    pattern = re.compile(pattern)
    def match(args, settings):
        for arg in args:
            if pattern.match(str(arg)):
                return True
        return False
    match.__name__ = "by_pattern(%s)" % pattern.pattern
    filter_add(chain, match, target, jump=jump, position=position)

def filter_print():
    """
    Print the filter-chains and filter-rules to the stdout.
    """
    for chain, policy in filter_chains_get():
        print("Chain %s (policy %s)" % (chain, policy))

        for check, target, jump in filter_get(chain):
            if not jump: jump = ""
            print("%-6s %-15s %s" % (target, jump, check))

        print()

def filter_check(args, settings):
    """
    Check if a message passes a specific chain

    ARGS is a tuple containing the message
    SETTINGS is a dictionaty in in the format of _dprint_settings

    returns True when all filters pass. Otherwise returns False
    """
    return _filter_check(args, settings, _filter_entry)

def _filter_check(args, settings, chain_info):
    """
    Check if a message passes a specific chain

    ARGS is a tuple containing the message
    SETTINGS is a dictionaty in in the format of _dprint_settings
    CHAIN_INFO is a list at _filters[chain-name]

    returns True when all filters pass. Otherwise returns False
    """
    for filter_info in chain_info[1]:
        if filter_info[0](args, settings):
            if filter_info[1] is True:
                return True
            elif filter_info[1] is False:
                return False
            elif filter_info[1] is None:
                continue
            else: # should be callable jump
                result = _filter_check(args, settings, filter_info[1])
                if result is None:
                    continue
                else:
                    return result
    return chain_info[0]

def _config_read():
    """
    Read dprint.conf configuration files

    Note: while we use 'normal' ini file structure we do not use the
    ConfigParser that python supplies. Unfortunately ConfigParser uses
    dictionaries to store the options making it unusable to us (the
    filter rules are order dependend.)
    """
    def get_arguments(string, conversions, glue):
        """
        get_arguments("filename, function, 42", (strip, strip, int), ",")
        --> ["filename", "function", 42]

        get_arguments("filename", (strip, strip, int), ",")
        --> ["filename", None, None]
        """
        def helper(index, func):
            if len(args) > index:
                return func(args[index])
            return None
        args = string.split(glue)
        return [helper(index, func) for index, func in zip(xrange(len(conversions)), conversions)]

    def strip(string):
        return string.strip()

    re_section = re.compile("^\s*\[\s*(.+?)\s*\]\s*$")
    re_option = re.compile("^\s*([^#].+?)\s*=\s*(.+?)\s*$")
    re_true = re.compile("^true|t|1$")

    options = []
    sections = {"default":options}
    for file_ in ['dprint.conf', expanduser('~/dprint.conf')]:
        if isfile(file_):
            line_number = 0
            for line in open(file_, "r"):
                line_number += 1
                match = re_option.match(line)
                if match:
                    options.append((line_number, line[:-1], match.group(1), match.group(2)))
                    continue

                match = re_section.match(line)
                if match:
                    section = match.group(1)
                    if section in sections:
                        options = sections[section]
                    else:
                        options = []
                        sections[section] = options
                    continue

    string = ["box_char", "glue", "line_char", "remote_host", "source_file", "source_function", "style", "time_format"]
    int_ = ["box_width", "line_width", "remote_port", "source_line", "stack_origin_modifier"]
    boolean = ["box", "binary", "exception", "force", "line", "lines", "meta", "pprint", "remote", "stack", "stderr", "stdout", "time"]
    for line_number, line, before, after in sections["default"]:
        try:
            if before in string:
                _dprint_settings[before] = after
            elif before in int_:
                if after.isdigit():
                    _dprint_settings[before] = int(after)
                else:
                    raise ValueError("Not a number")
            elif before in boolean:
                _dprint_settings[before] = bool(re_true.match(after))
            elif before == "level":
                _dprint_settings["level"] = int(level_map.get(after, after))
        except Exception, e:
            raise Exception("Error parsing line %s \"%s\"\n%s %s" % (line_number, line, type(e), str(e)))

    chains = []
    for section in sections:
        if section.startswith("filter "):
            chain = section.split(" ", 1)[1]
            filter_chain_create(chain, "return")
            chains.append((section, chain))
    if "filter" in sections:
        chains.append(("filter", "ENTRY"))

    for section, chain in chains:
        for line_number, line, before, after in sections[section]:
            try:
                if before == "policy":
                    filter_chain_policy(chain, after)
                else:
                    type_, before = before.split(" ", 1)
                    after, jump = get_arguments(after, (strip, strip), " ")
                    if type_ == "source":
                        file_, function, path = get_arguments(before, (strip, strip, strip), ",")
                        filter_add_by_source(chain, after, file=file_, function=function, path=path, jump=jump)
                    elif type_ == "level":
                        def conv(x):
                            if x.isdigit(): return int(x)
                            x = x.strip()
                            if x: return x
                            return None
                        exact, min_, max_ = get_arguments(before, (conv, conv, conv), ",")
                        filter_add_by_level(chain, after, exact=exact, min=min_, max=max_, jump=jump)
                    elif type_ == "pattern":
                        filter_add_by_pattern(chain, after, before, jump=jump)
            except Exception, e:
                raise Exception("Error parsing line %s \"%s\"\n%s %s" % (line_number, line, type(e), str(e)))

_config_read()

# class RemoteProtocol:
#     @staticmethod
#     def encode(key, value):
#         """
#         1 byte (reserved)
#         1 byte with len(key)
#         2 bytes with len(value)
#         n bytes with the key where n=len(key)
#         m bytes with the value where m=len(value)
#         """
#         assert type(key) is str
#         assert len(key) < 2**8
#         assert type(value) is str
#         assert len(value) < 2**16
#         m = len(value)
#         return "".join((chr(0),
#                         chr(len(key)),
#                         chr((m >> 8) & 0xFF), chr(m & 0xFF),
#                         key,
#                         value))

#     @staticmethod
#     def decode(data):
#         """
#         decode raw data.

#         returns (data, messages) where data contains the remaining raw
#         data and messages is a list containing (key, message) tuples.
#         """
#         assert type(data) is str
#         size = len(data)
#         messages = []
#         while size >= 4:
#             n = ord(data[1])
#             m = ord(data[2]) << 8 | ord(data[3])

#             # check if the entire message is available
#             if size - 4 >= n + m:
#                 messages.append((data[4:4+n], (data[4+n:4+n+m], )))
#                 data = data[4+n+m:]
#                 size -= (4+n+m)
#             else:
#                 break

#         return data, messages

# class RemoteConnection(RemoteProtocol):
#     __singleton = None
#     __lock = Lock()

#     @classmethod
#     def get_instance(cls, *args, **kargs):
#         if not cls.__singleton:
#             cls.__lock.acquire()
#             try:
#                 if not cls.__singleton:
#                     cls.__singleton = cls(*args, **kargs)
#             finally:
#                 cls.__lock.release()
#         return cls.__singleton

#     @classmethod
#     def send(cls, args, settings):
#         remote = cls.get_instance(settings["remote_host"], settings["remote_port"])
#         remote._queue.put(("dprint", (args, settings)))

#     def __init__(self, host, port):
#         # thread protected write buffer
#         self._queue = Queue(0)
#         self._address = (host, port)

#         # start a thread to handle async socket communication
#         thread = Thread(target=self._loop)
#         thread.start()

#     def _loop(self):
#         # connect
#         connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#         connection.setblocking(1)
#         try:
#             connection.connect(self._address)
#         except:
#             print >>stderr, "Could not connect to Dremote at", self._address
#             raise

#         # handshake
#         connection.send(self.encode("protocol", "remote-dprint-1.0"))

#         # send data from the queue
#         while True:
#             key, value = self._queue.get()
#             connection.send(self.encode(key, dumps(value)))

def dprint_wrap(func):
    source_file = inspect.getsourcefile(func)
    source_line = inspect.getsourcelines(func)[1]
    source_function = func.__name__
    def wrapper(*args, **kargs):
        dprint("PRE ", args, kargs, source_file=source_file, source_line=source_line, source_function=source_function)
        try:
            result = func(*args, **kargs)
        except Exception, e:
            dprint("POST", e, source_file=source_file, source_line=source_line, source_function=source_function)
            raise
        else:
            dprint("POST", result, source_file=source_file, source_line=source_line, source_function=source_function)
            return result
    return wrapper

def dprint_pre(func):
    source_file = inspect.getsourcefile(func)
    source_line = inspect.getsourcelines(func)[1]
    source_function = func.__name__
    def wrapper(*args, **kargs):
        dprint("PRE ", args, kargs, source_file=source_file, source_line=source_line, source_function=source_function)
        return func(*args, **kargs)
    return wrapper

def dprint_post(func):
    source_file = inspect.getsourcefile(func)
    source_line = inspect.getsourcelines(func)[1]
    source_function = func.__name__
    def wrapper(*args, **kargs):
        try:
            result = func(*args, **kargs)
            return result
        finally:
            dprint("POST", result, source_file=source_file, source_line=source_line, source_function=source_function)
    return wrapper

def dprint_wrap_object(object_, pattern="^(?!__)"):
    """
    Experimental feature: add a dprint before and after each method
    call to object.
    """
    re_pattern = re.compile(pattern)
    for name, member in inspect.getmembers(object_):
        if hasattr(member, "__call__") and re_pattern.match(name):
            try:
                setattr(object_, member.__name__, dprint_wrap(member))
            except:
                dprint("Failed wrapping", member, "in object", object_)

def dprint(*args, **kargs):
    """
    Create a message from ARGS and output it somewhere.

    The message can be send to:
    - stdout
    - stderr (default)
    - remote (send message and context to external program)

    The message can contain a stacktrace and thread-id when kargs
    contains "stack" which evaluates to True. The callstack can
    be shortened (leaving of the call to extract_stack() or event
    dprint()) my supplying "stack_origin_modifier" to kargs. The
    default is -1 which removes the last call to extract_stack().

    Each ARGS will be presented on a seperate line with meta data when
    kargs contains "meta" which evaluates to True.

    Each ARGS will be presented in binary format when kargs contains
    "binary" which evaluates to True.

    A string representation is derived from anything in ARGS using
    str(). Therefore, no objects should be supplied that define a
    __str__ method which causes secondary effects. Furthermore, to
    reduce screen clutter, only the first 1000 characters returned by
    str() are used. (an exception to this is the remote output where
    everything is transfered).

    Usage:
    from Tribler.Debug.Dprint import dprint

    (Display a message "foo bar")
    | if __debug__: dprint("foo", "bar")
    filename:1 <module> foo bar
    ---

    (Display a message in a function)
    | def my_function():
    |     if __debug__: dprint("foo")
    |     pass
    | my_function()
    filename:2 my_function foo
    ---

    (Display a value types)
    | if __debug__: dprint("foo", 123, 1.5, meta=1)
    filename:1 <module> (StringType, len 3)    foo
    filename:1 <module> (IntType)              123
    filename:1 <module> (FloatType)            1.5
    ---

    (Display a message with a callstack)
    | def my_function():
    |     if __debug__: dprint("foo", stack=1)
    |     pass
    | my_function()
    filename:2 my_function foo
    filename:2 my_function ---
    filename:2 my_function Stacktrace on thread: "MainThread"
    filename:2 my_function                 Dprint.py:470 <module>
    filename:2 my_function               filename.py:4   <module>
    filename:2 my_function               filename.py:2   my_function
    ---

    (Display an exception)
    | try:
    |     raise RuntimeError("Wrong")
    | except:
    |     if __debug__: dprint("An exception occured", exception=1)
    |     pass
    filename:4 <module> An exception occured
    filename:4 <module> ---
    filename:4 <module> --- Exception: <type 'exceptions.RuntimeError'> ---
    filename:4 <module> Wrong
    filename:4 <module> Traceback where the exception originated:
    filename:4 <module>               filename.py:2
    ---

    (Display a cpu-intensive message)
    | if __debug__:
    |     def expensive_calculation():
    |         import time
    |         time.sleep(1)
    |         return "moo-milk"
    |     dprint("foo-bar", callback=expensive_calculation)
    filename:6    <module>                  | foo-bar moo-milk
    ---
    """
    # ensure that kargs contains only known options
    for key in kargs:
        if not key in _dprint_settings:
            raise ValueError("Unknown options: %s" % key)

    # merge default dprint settings with kargs
    # todo: it might be faster to clone _dprint_settings and call update(kargs) on it
    for key, value in _dprint_settings.items():
        if not key in kargs:
            kargs[key] = value

    # type check all kargs
    # TODO

    # fetch the callstack
    callstack = extract_stack()[:kargs["stack_origin_modifier"]]

    if callstack:
        # use the callstack to determine where the call came from
        if kargs["source_file"] is None: kargs["source_file"] = callstack[-1][0]
        if kargs["source_line"] is None: kargs["source_line"] = callstack[-1][1]
        if kargs["source_function"] is None: kargs["source_function"] = callstack[-1][2]
    else:
        if kargs["source_file"] is None: kargs["source_file"] = "unknown"
        if kargs["source_line"] is None: kargs["source_line"] = 0
        if kargs["source_function"] is None: kargs["source_function"] = "unknown"

    # exlicitly force the message
    if kargs["force"]:
        kargs["level"] = "force"

    # when level is below ERROR, apply filters on the message
    if kargs["level"] in level_map: kargs["level"] = level_map[kargs["level"]]
    if kargs["level"] < LEVEL_ERROR and not _filter_check(args, kargs, _filter_entry):
        return

    if kargs["source_file"].endswith(".py"):
        short_source_file = join(basename(dirname(kargs["source_file"])), basename(kargs["source_file"][:-3]))
    else:
        short_source_file = join(basename(dirname(kargs["source_file"])), basename(kargs["source_file"]))
    prefix = [level_tag_map.get(kargs["level"], "U")]
    if kargs["time"]:
        prefix.append(strftime(kargs["time_format"]))
    if kargs["style"] == "short":
        prefix.append("%s:%s %s " % (short_source_file, kargs["source_line"], kargs["source_function"]))
    elif kargs["style"] == "column":
        prefix.append("%25s:%-4s %-25s | " % (short_source_file[-25:], kargs["source_line"], kargs["source_function"]))
    else:
        raise ValueError("Invalid/unknown style: \"%s\"" % kargs["style"])
    prefix = " ".join(prefix)
    messages = []

    if kargs["callback"]:
        args = args + (kargs["callback"](),)

    # print each variable in args
    if kargs["binary"]:
        string = kargs["glue"].join([str(v) for v in args])
        messages.append(" ".join(["%08d" % int(bin(ord(char))[2:]) for char in string]))
        # for index, char in zip(xrange(len(string)), string):
        #     messages.append("{0:3d} {1:08d} \\x{2}".format(index, int(bin(ord(char))[2:]), char.encode("HEX")))
    elif kargs["meta"]:
        messages.extend([dprint_format_variable(v) for v in args])
    elif kargs["lines"] and len(args) == 1 and type(args[0]) in (list, tuple):
        messages.extend([str(v) for v in args[0]])
    elif kargs["lines"] and len(args) == 1 and type(args[0]) is dict:
        messages.extend(["%s: %s" % (str(k), str(v)) for k, v in args[0].items()])
    elif kargs["lines"]:
        messages.extend([str(v) for v in args])
    elif kargs["pprint"] and len(args) == 1:
        messages.extend(pformat(args[0]).split("\n"))
    elif kargs["pprint"]:
        messages.extend(pformat(args).split("\n"))
    else:
        messages.append(kargs["glue"].join([str(v) for v in args]))

    # add a line of characters at the top to seperate messages
    if kargs["line"]:
        messages.insert(0, "".join(kargs["line_char"] * kargs["line_width"]))

    # add a line of characters above and below to seperate messages
    if kargs["box"]:
        messages.insert(0, "".join(kargs["box_char"] * kargs["box_width"]))
        messages.append("".join(kargs["box_char"] * kargs["box_width"]))

    # always add stderr to output if level is error or exception is set
    global _last_dprint_see_stderr
    if kargs["level"] == LEVEL_ERROR or kargs["exception"]:
        kargs["stderr"] = True
        kargs["stdout"] = False

        # do not outpuy 'see stderr' on consecutive dprint calls
        if not _last_dprint_see_stderr:
            _last_dprint_see_stderr = True
            print >> stdout, prefix + "See stderr for exception"
    else:
        _last_dprint_see_stderr = False

    if kargs["stdout"]:
        print >> stdout, prefix + ("\n"+prefix).join([msg[:10000] for msg in messages])
        if kargs["stack"]:
            for line in format_list(callstack):
                print >> stdout, line, 
            # if isinstance(kargs["stack"], bool):
            #     for line in format_list(callstack):
            #         print >> stdout, line, 
            # else:
            #     for line in format_list(kargs["stack"][:kargs["stack_origin_modifier"]]):
            #         print >> stdout, line,
        if kargs["exception"]:
            print_exception(*exc_info(), **{"file":stdout})
        stdout.flush()
    if kargs["stderr"]:
        print >> stderr, prefix + ("\n"+prefix).join([msg[:10000] for msg in messages])
        if kargs["stack"]:
            print_stack(file=stderr)
        if kargs["exception"]:
            print_exception(*exc_info(), **{"file":stderr})
        stderr.flush()
    if kargs["remote"]:
        # todo: the remote_host and remote_port are values that may change
        # for each message. when this happens different connections should
        # be created!
        kargs["timestamp"] = time()
        kargs["callstack"] = callstack
        kargs["prefix"] = prefix
        kargs["thread_name"] = current_thread().name
        RemoteConnection.send(args, kargs)

def dprint_format_variable(v):
    return "%22s %s" % (type(v), str(v))

    # t = type(v)
    # if t is BooleanType:                return "(BooleanType)          {!s}".format(v)
    # if t is BufferType:                 return "(BufferType)           {!s}".format(v)
    # if t is BuiltinFunctionType:        return "(BuiltinFunctionType)  {!s}".format(v)
    # if t is BuiltinMethodType:          return "(BuiltinMethodType)    {!s}".format(v)
    # if t is ClassType:                  return "(ClassType)            {!s}".format(v)
    # if t is CodeType:                   return "(CodeType)             {!s}".format(v)
    # if t is ComplexType:                return "(ComplexType)          {!s}".format(v)
    # if t is DictProxyType:              return "(DictProxyType)        {!s}".format(v)
    # if t in (DictType, DictionaryType): return "(DictType, len {8} {!s}".format(len(v), str(v))
    # if t is EllipsisType:               return "(EllipsisType)         {!s}".format(v)
    # if t is FileType:                   return "(FileType)             {!s}".format(v)
    # if t is FloatType:                  return "(FloatType)            {!s}".format(v)
    # if t is FrameType:                  return "(FrameType)            {!s}".format(v)
    # if t is FunctionType:               return "(FunctionType)         {!s}".format(v)
    # if t is GeneratorType:              return "(GeneratorType)        {!s}".format(v)
    # if t is GetSetDescriptorType:       return "(GetSetDescriptorType) {!s}".format(v)
    # if t is InstanceType:               return "(InstanceType)         {!s}".format(v)
    # if t is int:                    return "(IntType)              {!s}".format(v)
    # if t is LambdaType:                 return "(LambdaType)           {!s}".format(v)
    # if t is ListType:                   return "(ListType, len {8} {!s}".format(len(v), str(v))
    # if t is LongType:                   return "(LongType)             {!s}".format(v)
    # if t is MemberDescriptorType:       return "(MemberDescriptorType) {!s}".format(v)
    # if t is MethodType:                 return "(MethodType)           {!s}".format(v)
    # if t is ModuleType:                 return "(ModuleType)           {!s}".format(v)
    # if t is NoneType:                   return "(NoneType)             {!s}".format(v)
    # if t is NotImplementedType:         return "(NotImplementedType)   {!s}".format(v)
    # if t is ObjectType:                 return "(ObjectType)           {!s}".format(v)
    # if t is SliceType:                  return "(SliceType)            {!s}".format(v)
    # if t is str:                 return "(StringType, len {6} {!s}".format(len(v), str(v))
    # if t is TracebackType:              return "(TracebackType)        {!s}".format(v)
    # if t is TupleType:                  return "(TupleType, len {7} {!s}".format(len(v), str(v))
    # if t is TypeType:                   return "(TypeType)             {!s}".format(v)
    # if t is UnboundMethodType:          return "(UnboundMethodType)    {!s}".format(v)
    # if t is UnicodeType:                return "(UnicodeType)          {!s}".format(v)
    # if t is XRangeType:                 return "(XRangeType)           {!s}".format(v)

    # # default return
    # return "({22!s}) {!s}".format(t, v)

def strip_prefix(prefix, string):
    if string.startswith(prefix):
        return string[len(prefix):]
    else:
        return string

if __debug__:
    if __name__ == "__main__":
        dprint(1, level="error")
        dprint(2, level="error")
        dprint(3, level="error")
        dprint("---", force=1)
        dprint(1, level="error")
        dprint(2, level="error")
        dprint(3, level="error")

# if __name__ == "__main__":

#     def examples():
#         examples = [('Display a message "foo bar"', """if __debug__: dprint("foo", "bar")"""),
#                     ('Display a message in a function', """def my_function():
#     if __debug__: dprint("foo")
#     pass
# my_function()"""),
#                     ('Display a value types', """if __debug__: dprint("foo", 123, 1.5, meta=1)"""),
#                     ('Display a message with a callstack', """def my_function():
#     if __debug__: dprint("foo", stack=1)
#     pass
# my_function()"""),
#                     ('Display an exception', """try:
#     raise RuntimeError("Wrong")
# except:
#     if __debug__: dprint("An exception occured", exception=1)
#     pass"""),
#                     ('Display a cpu-intensive message', """if __debug__:
#     def expensive_calculation():
#         import time
#         time.sleep(0.1)
#         return "moo-milk"
#     dprint("foo-bar", callback=expensive_calculation)""")
#     ]

#         for title, code in examples:
#             print("({})".format(title))
#             print("| " + "\n| ".join(code.split("\n")))
#             eval(compile(code, "filename.py", "exec"))
#             print("---")
#             print()

#         for title, code in examples:
#             print("{{{")
#             print("#!python")
#             print("# {}".format(title))
#             print(code)
#             eval(compile(code, "filename.py", "exec"))
#             print("}}}")
#             print()

#     def filter_():
#         filter_chain_policy("ENTRY", "drop")
#         filter_add_by_level("ENTRY", "accept", level=LEVEL_ERROR)
#         filter_add_by_level("ENTRY", "accept", min=LEVEL_WARNING, max=LEVEL_ERROR)
#         filter_add_by_pattern("ENTRY", "accept", "foo")
#         filter_add_by_source("ENTRY", "accept", line=644)
#         filter_add_by_source("ENTRY", "accept", function="filter_")
#         filter_add_by_source("ENTRY", "accept", "print.py")
#         dprint("foo-bar", level=LEVEL_ERROR)
#         dprint("foo-bar", level=LEVEL_WARNING)
#         dprint("foo-bar")
#         filter_print()


from __future__ import annotations

import argparse
import os
import pathlib
import platform
import sys
import time
import unittest
from concurrent.futures import ProcessPoolExecutor

sys.path.append(str(pathlib.Path("../pyipv8").absolute()))

from run_all_tests import (
    DEFAULT_PROCESS_COUNT,
    ProgrammerDistractor,
    find_all_test_class_names,
    install_libsodium,
    task_test,
    windows_missing_libsodium,
)

if platform.system() == "Darwin":
    """
    The unit tests on Mac lock up on multiprocess getaddrinfo calls. We establish the lan addresses once here before
    spawning any children.

    File "/Users/runner/hostedtoolcache/Python/3.9.20/x64/lib/python3.9/socket.py", line 966, in getaddrinfo
|       for res in _socket.getaddrinfo(host, port, family, type, proto, flags):
    """
    from ipv8.messaging.interfaces.lan_addresses.interfaces import get_lan_addresses
    get_lan_addresses()


def task_tribler_test(*test_names: str) -> tuple[bool, int, float, list[tuple[str, str, str]], str]:
    """
    Same as task_test but corrects the libsodium dll location.
    """
    if platform.system() == "Windows":
        os.add_dll_directory(str(pathlib.Path("libsodium.dll").absolute().parent))
    return task_test(*test_names)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Tribler tests.")
    parser.add_argument("-p", "--processes", type=int, default=DEFAULT_PROCESS_COUNT, required=False,
                        help="The amount of processes to spawn.")
    parser.add_argument("-q", "--quiet", action="store_true", required=False,
                        help="Don't show succeeded tests.")
    parser.add_argument("-a", "--noanimation", action="store_true", required=False,
                        help="Don't animate the terminal output.")
    parser.add_argument("-d", "--nodownload", action="store_true", required=False,
                        help="Don't attempt to download missing dependencies.")
    parser.add_argument("-k", "--pattern", type=str, default="tribler/test_unit", required=False,
                        help="The unit test directory.")
    args = parser.parse_args()

    if platform.system() == "Windows" and windows_missing_libsodium() and not args.nodownload:
        print("Failed to locate libsodium (libnacl requirement), downloading latest dll!")  # noqa: T201
        install_libsodium()
        os.add_dll_directory(str(pathlib.Path("libsodium.dll").absolute().parent))

    process_count = args.processes
    test_class_names = find_all_test_class_names(pathlib.Path(args.pattern))

    total_start_time = time.time()
    total_end_time = time.time()
    global_event_log = []
    total_time_taken = 0
    total_tests_run = 0
    total_fail = False
    print_output = ""

    print(f"Launching in {process_count} processes ... awaiting results ... \033[s", end="", flush=True)  # noqa: T201

    with ProgrammerDistractor(not args.noanimation) as programmer_distractor:
        with ProcessPoolExecutor(max_workers=process_count) as executor:
            result = executor.map(task_tribler_test, test_class_names,
                                  chunksize=len(test_class_names) // process_count + 1)
            for process_output_handle in result:
                failed, tests_run, time_taken, event_log, print_output = process_output_handle
                total_fail |= failed
                total_tests_run += tests_run
                total_time_taken += time_taken
                if failed:
                    global_event_log = event_log
                    break
                global_event_log.extend(event_log)
        total_end_time = time.time()
    total_fail |= programmer_distractor.crashed  # This is not a unit test failure but we still fail the test suite.

    if programmer_distractor.crashed:
        # The printed test results won't show any errors. We need to give some more info.
        print("\033[u\033[Ktest suite process crash! Segfault?", end="\r\n\r\n", flush=True)  # noqa: T201
    else:
        print("\033[u\033[Kdone!", end="\r\n\r\n", flush=True)  # noqa: T201

    if total_fail or not args.quiet:
        print(unittest.TextTestResult.separator1)  # noqa: T201
        global_event_log.sort(key=lambda x: x[0])
        for event in global_event_log:
            print(("\033[91m" if event[1] == "ERR" else ("\033[94m" if event[1] == "LOG" else "\033[0m"))  # noqa: T201
                  + event[2] + "\033[0m",
                  end="")
        print("\r\n" + unittest.TextTestResult.separator1)  # noqa: T201

    print("Summary:")  # noqa: T201
    if total_fail:
        print("[\033[91mFAILED\033[0m", end="")  # noqa: T201
    else:
        print("[\033[32mSUCCESS\033[0m", end="")  # noqa: T201
    print(f"] Ran {total_tests_run} tests "  # noqa: T201
          f"in {round(total_end_time-total_start_time, 2)} seconds "
          f"({round(total_time_taken, 2)} seconds total in tests).")

    if total_fail:
        sys.exit(1)

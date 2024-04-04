from __future__ import annotations

import argparse
import contextlib
import importlib
import inspect
import io
import multiprocessing
import os
import pathlib
import platform
import sys
import threading
import time
import unittest
from concurrent.futures import ProcessPoolExecutor
from typing import TYPE_CHECKING, Generator, TextIO, cast
from unittest import TestCase

if TYPE_CHECKING:
    import types

    from typing_extensions import Self

sys.path.append(str(pathlib.Path("../pyipv8").absolute()))

DEFAULT_PROCESS_COUNT = multiprocessing.cpu_count() * 2
if platform.system() == 'Windows':
    # Workaround for https://github.com/Tribler/py-ipv8/issues/1120
    DEFAULT_PROCESS_COUNT = min(60, DEFAULT_PROCESS_COUNT)

    # Workaround to enable ANSI codes in Windows, taken from https://stackoverflow.com/a/60194390
    from ctypes import windll
    windll.kernel32.SetConsoleMode(windll.kernel32.GetStdHandle(-11), 7)


class ProgrammerDistractor(contextlib.AbstractContextManager):
    """
    Rotating + sign while waiting for the test results.
    """

    def __init__(self, enabled: bool) -> None:
        """
        Create our distractor, without starting rotation.
        """
        self.enabled = enabled
        self.starttime = time.time()
        self.timer = None
        self.crashed = False

    def programmer_distractor(self) -> None:
        """
        Start rotating.
        """
        distraction = str(int(time.time() - self.starttime))
        print('\033[u\033[K' + distraction + " seconds and counting "  # noqa: T201
              + ("x" if int(time.time() * 10) % 2 else "+"), end="", flush=True)
        self.timer = threading.Timer(0.1, self.programmer_distractor)
        self.timer.start()

    def __enter__(self) -> Self:
        """
        Start rotating if we are enabled, otherwise do nothing.
        """
        if self.enabled:
            self.timer = threading.Timer(0.1, self.programmer_distractor)
            self.timer.start()
        return self

    def __exit__(self,
                 exc_type: type[BaseException] | None,
                 exc: BaseException | None,
                 exc_tb: types.TracebackType | None) -> bool:
        """
        Exit our context manager. We consume exceptions.
        """
        if self.timer:
            self.timer.cancel()
        if exc_type is not None or exc is not None:
            self.crashed = True
            return True  # Consume the exception: we'll tell the user later.
        return False


class CustomTestResult(unittest.TextTestResult):
    """
    Custom test results that include the running time of each unit test.
    """

    def __init__(self, stream: TextIO, descriptions: bool, verbosity: int) -> None:
        """
        Create a new text test result and reset our timers for the next unit.
        """
        super().__init__(stream, descriptions, verbosity)
        self.start_time = 0
        self.end_time = 0
        self.last_test = 0

    def getDescription(self, test: TestCase) -> str:  # noqa: N802
        """
        Get the textual representation of a given test case.
        """
        return str(test)

    def startTestRun(self) -> None:  # noqa: N802
        """
        Start up the test case.
        """
        super().startTestRun()
        self.start_time = time.time()
        self.end_time = self.start_time

    def startTest(self, test: TestCase) -> None:  # noqa: N802
        """
        Start a unit test.
        """
        super().startTest(test)
        self.last_test = time.time()

    def addSuccess(self, test: TestCase) -> None:  # noqa: N802
        """
        We finished a unit without failing!
        """
        super(unittest.TextTestResult, self).addSuccess(test)
        if self.showAll:
            self.stream.write(f"ok [{round((time.time() - self.last_test) * 1000, 2)} ms]{os.linesep}")
        elif self.dots:
            self.stream.write('.')
            self.stream.flush()

    def stopTestRun(self) -> None:  # noqa: N802
        """
        Stop the entire test run.
        """
        super().stopTestRun()
        self.end_time = time.time()


class CustomLinePrint(io.StringIO):
    """
    Interceptor for all prints and logging that stores the calls in a list with timestamps.
    """

    def __init__(self, delegated: TextIO, prefix: str) -> None:
        """
        Forward calls to a given ``TextIO`` and tag each line with a given prefix.
        """
        super().__init__()
        self.prefix = prefix
        self.delegated = delegated
        self.raw_lines = []

    def write(self, __text: str) -> int:
        """
        Write text that is not necessarily newline terminated.
        """
        wtime = time.time()
        if self.raw_lines and not self.raw_lines[-1][2].endswith('\n'):
            self.raw_lines[-1] = (self.raw_lines[-1][0], self.raw_lines[-1][1], self.raw_lines[-1][2] + __text)
        else:
            self.raw_lines.append((wtime, self.prefix, __text))
        return self.delegated.write(__text)


def task_test(*test_names: str) -> tuple[bool, int, float, list[tuple[str, str, str]], str]:
    """
    We're a subprocess that has been assigned some test names to execute.
    """
    import logging

    try:
        # If we made it here, there is only one option if the import fails and that is a local path dll.
        import libnacl  # noqa: F401
    except:
        os.add_dll_directory(os.path.dirname(__file__) or os.path.abspath('.'))

    print_stream = io.StringIO()
    output_stream = CustomLinePrint(print_stream, "OUT")
    stdio_replacement = CustomLinePrint(print_stream, "OUT")
    stderr_replacement = CustomLinePrint(print_stream, "ERR")
    logging_replacement = CustomLinePrint(print_stream, "LOG")
    sys.stdio = stdio_replacement
    sys.stderr = stderr_replacement
    logging.basicConfig(level="DEBUG", stream=logging_replacement,
                        format="%(levelname)-7s %(created).2f %(module)18s:%(lineno)-4d (%(name)s)  %(message)s")

    suite = unittest.TestSuite()
    for test_name in test_names:
        suite.addTest(unittest.defaultTestLoader.loadTestsFromName(test_name))
    reporter = unittest.TextTestRunner(stream=output_stream, failfast=True, verbosity=2, resultclass=CustomTestResult)
    test_result = None

    start_time = time.time()
    end_time = start_time
    last_test = start_time
    tests_run_count = 0
    tests_failed = False
    combined_event_log = []
    try:
        test_result = reporter.run(suite)
        tests_failed = len(test_result.errors) > 0 or len(test_result.failures) > 0
        real_result = cast(CustomTestResult, test_result)
        start_time = real_result.start_time
        end_time = real_result.end_time
        last_test = real_result.last_test
        tests_run_count = real_result.testsRun
    except BaseException:
        tests_failed = True
        end_time = time.time()
    finally:
        combined_event_log.extend(output_stream.raw_lines if tests_failed
                                  else output_stream.raw_lines[:tests_run_count])
        combined_event_log.extend(stdio_replacement.raw_lines)
        combined_event_log.extend(stderr_replacement.raw_lines)
        if tests_failed and logging_replacement.raw_lines:
            relevant_log = [line for line in logging_replacement.raw_lines if line[0] >= last_test]
            combined_event_log.append((relevant_log[0][0], "LOG", "\n"))
            combined_event_log.extend(relevant_log)

    return tests_failed, tests_run_count, end_time - start_time, combined_event_log, print_stream.getvalue()


def scan_for_test_files(directory: pathlib.Path | str) -> Generator[pathlib.Path, None, None]:
    """
    Find Python files starting with ``test_`` in a given directory.
    """
    if not isinstance(directory, pathlib.Path):
        directory = pathlib.Path(directory)
    return directory.glob('**/test_*.py')


def derive_test_class_names(test_file_path: pathlib.Path) -> list[str]:
    """
    Derive the module names from the given test file path.
    """
    module_name = '.'.join(test_file_path.relative_to(pathlib.Path('.')).parts)[:-3]
    module_instance = importlib.import_module(module_name)
    test_class_names = []
    for obj_name, obj in inspect.getmembers(module_instance):
        if inspect.isclass(obj) and issubclass(obj, unittest.TestCase) and obj.__module__ == module_name:
            test_class_names.append(f"{module_name}.{obj_name}")
    return test_class_names


def find_all_test_class_names(directory: pathlib.Path | str = pathlib.Path('tribler/test_unit')) -> list[str]:
    """
    Get all the modules for all the files that look like test files in a given path.
    """
    if not isinstance(directory, pathlib.Path):
        directory = pathlib.Path(directory)
    test_class_names = []
    for found_test in scan_for_test_files(directory):
        test_class_names.extend(derive_test_class_names(found_test))
    return test_class_names


def install_libsodium() -> None:
    """
    Attempt to install the latest libsodium backend.
    """
    # Ensure a libsodium.zip
    if not pathlib.Path("libsodium.zip").exists():
        import re
        from http.client import HTTPSConnection
        connection = HTTPSConnection("download.libsodium.org")

        connection.request("GET", "/libsodium/releases/", headers={})
        web_response = connection.getresponse().read().decode()

        # Extract the latest version
        result = sorted(re.findall(r"libsodium-[0-9]*\.[0-9]*\.[0-9]*-stable-msvc.zip\"",
                                    web_response))[-1][:-1]

        connection.request("GET", f"/libsodium/releases/{result}", headers={})
        pathlib.Path("libsodium.zip").write_bytes(connection.getresponse().read())

        connection.close()

    # Unpack just the libsodium.dll
    if not pathlib.Path("libsodium.dll").exists():
        import zipfile
        fr = zipfile.Path("libsodium.zip", "libsodium/x64/Release/")
        fr = sorted((d for d in fr.iterdir()), key=lambda x: str(x))[-1] / "dynamic" / "libsodium.dll"
        with open("libsodium.dll", "wb") as fw:
            fw.write(fr.read_bytes())


def windows_missing_libsodium() -> bool:
    """
    Check if we can NOT find the libsodium backend.
    """
    with contextlib.suppress(OSError):
        import libnacl
        return False

    # Try to find it in the local directory. This is where we'll download it anyway.
    os.add_dll_directory(os.path.dirname(__file__) or os.path.abspath('.'))
    try:
        import libnacl  # noqa: F401, F811
        return False
    except OSError:
        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run the Tribler tests.')
    parser.add_argument('-p', '--processes', type=int, default=DEFAULT_PROCESS_COUNT, required=False,
                        help="The amount of processes to spawn.")
    parser.add_argument('-q', '--quiet', action='store_true', required=False,
                        help="Don't show succeeded tests.")
    parser.add_argument('-a', '--noanimation', action='store_true', required=False,
                        help="Don't animate the terminal output.")
    parser.add_argument('-d', '--nodownload', action='store_true', required=False,
                        help="Don't attempt to download missing dependencies.")
    args = parser.parse_args()

    if platform.system() == 'Windows' and windows_missing_libsodium() and not args.nodownload:
        print("Failed to locate libsodium (libnacl requirement), downloading latest dll!")  # noqa: T201
        install_libsodium()

    process_count = args.processes
    test_class_names = find_all_test_class_names()

    total_start_time = time.time()
    total_end_time = time.time()
    global_event_log = []
    total_time_taken = 0
    total_tests_run = 0
    total_fail = False
    print_output = ''

    print(f"Launching in {process_count} processes ... awaiting results ... \033[s", end="", flush=True)  # noqa: T201

    with ProgrammerDistractor(not args.noanimation) as programmer_distractor:
        with ProcessPoolExecutor(max_workers=process_count) as executor:
            result = executor.map(task_test, test_class_names, chunksize=len(test_class_names) // process_count + 1)
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
            print(('\033[91m' if event[1] == "ERR" else ('\033[94m' if event[1] == "LOG" else '\033[0m'))  # noqa: T201
                  + event[2] + '\033[0m',
                  end='')
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

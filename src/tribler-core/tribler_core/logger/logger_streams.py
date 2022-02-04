import sys
from typing import TextIO


class StreamWrapper:
    """
    Used by logger to wrap stderr & stdout streams. Handles UnicodeDecodeError if console encoding is not utf-8.
    """

    def __init__(self, stream: TextIO):
        self.stream = stream

    def flush(self):
        self.stream.flush()

    def write(self, s: str):
        try:
            self.stream.write(s)
        except UnicodeEncodeError:
            encoding = self.stream.encoding
            s2 = s.encode(encoding, errors='backslashreplace').decode(encoding)
            self.stream.write(s2)

    def close(self):
        self.stream.close()


stdout_wrapper = StreamWrapper(sys.stdout)  # specified in logger.yaml for `console` handler
stderr_wrapper = StreamWrapper(sys.stderr)  # specified in logger.yaml for `error_console` handler

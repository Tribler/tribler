import dataclasses
import json
import os
import time
from dataclasses import dataclass, field
from json import JSONDecodeError
from typing import Optional

from tribler.core.utilities.osutils import get_root_state_directory

CRASH_ERROR_DIR = get_root_state_directory() / 'crashlogs'


@dataclass
class ReportedError:
    type: str
    text: str
    event: dict = field(repr=False)
    additional_information: dict = field(default_factory=lambda: {}, repr=False)
    created_at: int = field(default_factory=lambda: int(time.time() * 1000), repr=False)

    long_text: str = field(default='', repr=False)
    context: str = field(default='', repr=False)
    last_core_output: str = field(default='', repr=False)
    should_stop: Optional[bool] = field(default=None)

    @classmethod
    def get_or_create_log_dir(cls):
        if not CRASH_ERROR_DIR.exists():
            CRASH_ERROR_DIR.mkdir(exist_ok=True)
        return CRASH_ERROR_DIR

    def get_file_path(self):
        return self.get_or_create_log_dir() / f"{self.type}-{self.created_at}.json"

    def save_to_file(self):
        # While saving to file, set should_stop=False.
        # This is because this file will be read on restart of the core, and
        # we don't want to crash the core for the error from the last run.
        self_copy = dataclasses.replace(self)
        self_copy.should_stop = False

        serialized_error = json.dumps(dataclasses.asdict(self_copy), indent=True)
        with open(self.get_file_path(), 'w') as exc_file:
            exc_file.write(serialized_error)

    def delete_saved_file(self):
        self.get_file_path().unlink(missing_ok=True)

    @classmethod
    def get_saved_errors(cls):
        if not CRASH_ERROR_DIR.exists():
            return []

        saved_errors = []
        for error_filename in os.listdir(CRASH_ERROR_DIR):
            if not error_filename.endswith('.json'):
                continue

            error_file_path = CRASH_ERROR_DIR / error_filename
            with open(error_file_path, 'r') as file_handle:
                try:
                    saved_errors.append(ReportedError(**json.loads(file_handle.read())))
                except JSONDecodeError:
                    error_file_path.unlink()

        return saved_errors

import dataclasses
import json
import logging
import time
from dataclasses import dataclass, field
from json import JSONDecodeError
from pathlib import Path
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)


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

    def get_filename(self) -> str:
        """
        Returns the filename for the error report if it is saved to the file.
        """
        return f"{self.created_at}-{self.type}.json"

    def get_file_path_in_dir(self, parent_dir: Path) -> Path:
        """
        Returns the path to the file where the error will be saved in given directory.
        """
        return parent_dir / self.get_filename()

    def copy(self, **changes) -> 'ReportedError':
        """
        Returns a copy of the error report with the given changes.
        """
        return dataclasses.replace(self, **changes)

    def serialized_copy(self) -> 'ReportedError':
        """
        Returns a copy of the error report with the `should_stop` flag set to False.
        This is useful when the error report is saved to the file so that the deserialized
        error report doesn't stop the core.
        """
        return self.copy(should_stop=False)

    def serialize(self, **changes) -> str:
        """
        Serializes the error report to a string.
        """
        serialized_error = json.dumps(dataclasses.asdict(self.copy(**changes)), indent=True)
        return serialized_error

    @classmethod
    def deserialize(cls, serialized_error: str) -> Optional['ReportedError']:
        """
        Deserializes the given error report.
        """
        try:
            return cls(**json.loads(serialized_error))
        except JSONDecodeError as e:
            logger.error(f"Failed to deserialize error: {e}")
            return None

    def save_to_dir(self, dir_path: Path) -> None:
        """
        Saves the error report to the given directory.
        """
        file_path = dir_path / self.get_filename()
        file_path.write_text(self.serialize(should_stop=False))

    @classmethod
    def load_from_file(cls, file_path: Path) -> Optional['ReportedError']:
        """
        Loads the error report from the given file path.
        """
        try:
            return cls.deserialize(file_path.read_text())
        except Exception as e:
            logger.error(f"Failed to load error from file: {e}")
            return None

    @classmethod
    def load_errors_from_dir(cls, dir_path: Path) -> List[Tuple[Path, 'ReportedError']]:
        """
        Loads all the error reports from the given directory.
        """
        if not dir_path or not dir_path.exists():
            return []

        return [(file_path, cls.load_from_file(file_path)) for file_path in dir_path.glob("*.json")]

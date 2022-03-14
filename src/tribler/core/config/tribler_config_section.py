from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseSettings, Extra, root_validator


class TriblerConfigSection(BaseSettings):
    """Base Class that defines Tribler Config Section

    We are waiting https://github.com/samuelcolvin/pydantic/pull/2625
    for proper and native manipulations with relative and absolute paths.
    """
    class Config:
        extra = Extra.ignore

    def put_path_as_relative(self, property_name: str, value: Path = None, state_dir: str = None):
        """Save a relative path if 'value' is relative to state_dir.
        Save an absolute path overwise.
        """
        if value is not None:
            # try to put a relative path (if it possible)
            try:
                value = Path(value).relative_to(state_dir)
            except ValueError:  # `path` is not in the subpath of `self.state_dir`
                pass

            value = str(value)

        self.__setattr__(property_name, value)

    def get_path_as_absolute(self, property_name: str, state_dir: Path = None) -> Optional[Path]:
        """ Get path as absolute. If stored value already in absolute form, then it will be returned in "as is".
           `state_dir / path` will be returned overwise.
        """
        value = self.__getattribute__(property_name)
        if value is None:
            return None

        path = Path(value)
        if path.is_absolute():
            return path

        return state_dir / path

    @root_validator(pre=True)
    def convert_from_none_string_to_none_type(cls, values):  # pylint: disable=no-self-argument
        """After a convert operation from "ini" to "pydantic", None values
        becomes 'None' string values.

        So, we have to convert them from `None` to None which is what happens
        in this function
        """
        for key, value in values.items():
            if value == 'None':
                values[key] = None
        return values

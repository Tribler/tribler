from dataclasses import dataclass
from pathlib import Path
from typing import Dict


win_error_codes_filename = Path(__file__).parent / 'win_error_codes.txt'


@dataclass
class ExitCode:
    code: int
    name: str
    description: str


def parse_win_error_codes() -> Dict[int, ExitCode]:
    error_codes = {}

    with open(win_error_codes_filename, 'r', encoding='utf-8') as file:
        for line in file.readlines():
            code, name, description = line.split(' ', 2)
            code = int(code)
            error_codes[code] = ExitCode(code, name, description.strip())

    return error_codes


win_errors = parse_win_error_codes()

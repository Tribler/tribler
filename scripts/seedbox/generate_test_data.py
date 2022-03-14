"""
This scripts generates data for testing purposes.
It generates given amount of folders which contains given amount of files.

For available parameters see "parse_args" function below.
"""
import argparse
from pathlib import Path
from random import Random

# fmt: off
# flake8: noqa

_folder_count = 1024
_file_count_per_folder = 8
_file_size = 128 * 1024


def parse_args():
    parser = argparse.ArgumentParser(description='Generate test data')

    parser.add_argument('-d', '--destination', type=str, help='path to data folder', default='.')
    return parser.parse_args()


def generate(destination):
    destination = Path(destination)
    destination.mkdir(exist_ok=True)

    for folder_index in range(_folder_count):
        folder = Path(destination / f'{folder_index}')
        folder.mkdir(exist_ok=True)

        for file_index in range(_file_count_per_folder):
            file = Path(folder / f'{file_index}.txt')
            file.write_bytes(Random().randbytes(_file_size))

        print(folder)


if __name__ == "__main__":
    arguments = parse_args()
    print(arguments)

    generate(arguments.destination)

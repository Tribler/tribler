"""
This scripts generates data for testing purposes.
It generates given amount of folders which contains given amount of files.

For available parameters see "parse_args" function below.
"""
import argparse
import os
from pathlib import Path

_file_count_per_folder = 8
_file_size = 128 * 1024


def parse_args():
    parser = argparse.ArgumentParser(description='Generate test data')

    parser.add_argument('-d', '--destination', type=str, help='path to data folder', default='.')
    parser.add_argument('-c', '--count', type=int, help='folders count', default=1024)

    return parser.parse_args()


def generate(arguments):
    print(arguments)
    destination = Path(arguments.destination)
    destination.mkdir(exist_ok=True)

    for folder_index in range(arguments.count):
        folder = Path(destination / f'{folder_index}')
        folder.mkdir(exist_ok=True)

        for file_index in range(_file_count_per_folder):
            f = Path(folder) / f'{file_index}.txt'
            content = os.urandom(_file_size)
            f.write_bytes(content)

        print(folder)


if __name__ == "__main__":
    args = parse_args()
    generate(args)

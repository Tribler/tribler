import logging
from argparse import ArgumentParser
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def parse_arguments():
    parser = ArgumentParser(description='Update Tribler NSI')
    parser.add_argument('-r', '--repo', type=str, help='path to a repository folder', default='.')
    parser.add_argument('-a', '--architecture', type=str, help='architecture (x86 or x64)', default='x86')
    return parser.parse_args()


if __name__ == '__main__':
    arguments = parse_arguments()

    version = Path('.TriblerVersion').read_text().lstrip('v').rstrip('\n')
    tribler_nsi = Path(arguments.repo) / 'build/win/resources/tribler.nsi'
    content = tribler_nsi.read_text()

    content = content.replace('__GIT__', version)
    if arguments.architecture == 'x64':
        content = content.replace('x86', 'x64')
        content = content.replace('"32"', '"64"')
        content = content.replace('$PROGRAMFILES', '$PROGRAMFILES64')

    tribler_nsi.write_text(content)

    logger.info(f'Content of tribler.nsi: {content}')

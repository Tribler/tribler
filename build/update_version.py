import logging
import os
from argparse import ArgumentParser
from pathlib import Path
from time import ctime

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def parse_arguments():
    parser = ArgumentParser(description='Update Tribler Version')
    parser.add_argument('-r', '--repo', type=str, help='path to a repository folder', default='.')
    return parser.parse_args()


if __name__ == '__main__':
    arguments = parse_arguments()
    logger.info(f'Arguments: {arguments}')

    ref_name = Path('.TriblerVersion').read_text().rstrip('\n')
    logger.info(f'Tribler tag: {ref_name}')

    commit = Path('.TriblerCommit').read_text().rstrip('\n')
    logger.info(f'Git Commit: {commit}')

    build_time = ctime()
    logger.info(f'Build time: {build_time}')

    sentry_url = os.environ.get('SENTRY_URL', None)
    logger.info(f'Sentry URL (hash): {hash(sentry_url)}')
    if sentry_url is None:
        logger.critical('Sentry url is not defined. To define sentry url use:'
                        'EXPORT SENTRY_URL=<sentry_url>\n'
                        'If you want to disable sentry, then define the following:'
                        'EXPORT SENTRY_URL=')
        exit(1)

    version_py = Path(arguments.repo) / 'src/tribler/core/version.py'
    logger.info(f'Write info to: {version_py}')
    version_py.write_text(
        f'version_id = "{ref_name}"\n'
        f'build_date = "{build_time}"\n'
        f'commit_id = "{commit}"\n'
        f'sentry_url = "{sentry_url}"\n'
    )

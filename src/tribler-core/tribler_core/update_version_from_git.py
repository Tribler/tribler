#!/usr/bin/env python

import logging
import sys
from os import linesep, path
from subprocess import PIPE, Popen
from time import ctime

logger = logging.getLogger(__name__)

# We aren't using python-git because we don't want to install the dependency on all the builders.


def run_command(cmd):
    p = Popen(cmd, stdout=PIPE, stderr=PIPE)
    p.wait()
    assert(p.returncode == 0)
    stdout = p.communicate()[0]
    return str(stdout.strip())


if __name__ == '__main__':
    cmd = ['git', 'describe', '--tags', 'HEAD']
    version_id = run_command(cmd).strip()[1:].replace("'", "")
    version_id = version_id[1:] if version_id.startswith('v') else version_id
    logger.info("Version: %s", version_id)
    cmd = ['git', 'rev-parse', 'HEAD']
    commit_id = run_command(cmd).strip()[1:].replace("'", "")
    logger.info("Commit: %s", commit_id)

    build_date = ctime()
    logger.info("Build date: %s", build_date)

    logger.info('Writing runtime version info.')
    with open(path.join('Tribler', 'Core', 'version.py'), 'w') as f:
        f.write('version_id = "%s"%sbuild_date = "%s"%scommit_id = "%s"%s' %
                (version_id, linesep, build_date, linesep, commit_id, linesep))

    with open('.TriblerVersion', 'w') as f:
        f.write(version_id)

    if sys.platform == 'linux2':
        run_command(f'dch -v {version_id} New upstream release.'.split())
    elif sys.platform == 'win32':
        logger.info('Replacing NSI string.')
        with open(path.join('Tribler', 'Main', 'Build', 'Win', 'tribler.nsi'), 'r+') as f:
            content = f.read()

            # Replace the __GIT__ string with the version id.
            content = content.replace('__GIT__', version_id)

            # Check if we are building 64 bit, replace the install dir and bit version accordingly.
            if len(sys.argv) > 1 and sys.argv[1] == "64":
                content = content.replace('x86', 'x64')
                content = content.replace('"32"', '"64"')
                content = content.replace('$PROGRAMFILES', '$PROGRAMFILES64')

            f.seek(0)
            f.write(content)

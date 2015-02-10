#!/usr/bin/env python

from subprocess import Popen, PIPE
from time import ctime
from os import path, linesep
from sys import platform
import logging

logger = logging.getLogger(__name__)

# We aren't using python-git because we don't want to install the dependency on all the builders.


def runCommand(cmd):
    p = Popen(cmd, stdout=PIPE, stderr=PIPE)
    p.wait()
    assert(p.returncode == 0)
    stdout = p.communicate()[0]
    return stdout.strip()

if __name__ == '__main__':
    cmd = ['git', 'describe', '--tags', 'HEAD']
    version_id = runCommand(cmd).strip()[1:]
    logger.info("Version: %s", version_id)
    cmd = ['git', 'rev-parse', 'HEAD']
    commit_id = runCommand(cmd).strip()[1:]
    logger.info("Commit: %s", commit_id)

    build_date = ctime()
    logger.info("Build date: %s", build_date)

    logger.info('Writing runtime version info.')
    f = open(path.join('Tribler', 'Core', 'version.py'), 'w')
    f.write('version_id = "%s"%sbuild_date = "%s"%scommit_id = "%s"%s' %
            (version_id, linesep, build_date, linesep, commit_id, linesep))
    f.close()

    f = open('.TriblerVersion', 'w')
    f.write(version_id)
    f.close()

    if platform == 'linux2':
        runCommand('dch -v {} New upstream release.'.format(version_id).split())
    elif platform == 'win32':
        logger.info('Replacing NSI string.')
        f = open(path.join('Tribler', 'Main', 'Build', 'Win32', 'tribler.nsi'), 'r+')
        content = f.read().replace('__GIT__', version_id)
        f.seek(0)
        f.write(content)
        f.close()

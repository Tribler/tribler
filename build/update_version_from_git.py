#!/usr/bin/env python

import logging
import os
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

    sentry_url = os.environ.get('SENTRY_URL', None)
    logger.info(f'Sentry url: {sentry_url}')
    if sentry_url is None:
        logger.critical('Sentry url is not defined. To define sentry url use:'
                        'EXPORT SENTRY_URL=<sentry_url>\n'
                        'If you want to disable sentry, then define the following:'
                        'EXPORT SENTRY_URL=')
        sys.exit(1)

    build_date = ctime()
    logger.info("Build date: %s", build_date)

    logger.info('Writing runtime version info.')
    with open(path.join('src', 'tribler-core', 'tribler_core', 'version.py'), 'w') as f:
        f.write(
            f'version_id = "{version_id}"{linesep}'
            f'build_date = "{build_date}"{linesep}'
            f'commit_id = "{commit_id}"{linesep}'
            f'sentry_url = "{sentry_url}"{linesep}'
        )

    with open('.TriblerVersion', 'w') as f:
        f.write(version_id)

    if sys.platform == 'linux2' or sys.platform == 'linux':
        logger.info('Writing AppStream version info.')
        import time
        import xml.etree.ElementTree as xml
        import defusedxml.ElementTree as defxml

        releaseDate = time.strftime("%Y-%m-%d", time.localtime())
        attrib = {'version': f'{version_id}', 'date':f'{releaseDate}'}

        tree = defxml.parse(path.join('build', 'debian', 'tribler', 'usr', 'share', 'metainfo',
                            'org.tribler.Tribler.metainfo.xml'))
        xmlRoot = tree.getroot()
        releases = xmlRoot.find('releases')
        release = xml.SubElement(releases, 'release', attrib)
        tree.write(path.join('build', 'debian', 'tribler', 'usr', 'share', 'metainfo',
                            'org.tribler.Tribler.metainfo.xml'))

    elif sys.platform == 'win32':
        logger.info('Replacing NSI string.')
        with open(path.join('build', 'win', 'resources', 'tribler.nsi'), 'r+') as f:
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

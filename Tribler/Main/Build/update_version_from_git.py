#!/usr/bin/env python

from subprocess import Popen, PIPE
from time import ctime
from os import path, linesep
from sys import platform

#We aren't using python-git because we don't want to install the dependency on all the builders.

def runCommand(cmd):
    p = Popen(cmd, stdout=PIPE, stderr=PIPE)
    p.wait()
    assert(p.returncode == 0)
    stdout = p.communicate()[0]
    return stdout.strip()

if __name__ == '__main__':
    cmd = ['git', 'describe', '--tags', 'HEAD']
    version_id = runCommand(cmd).strip()[1:]
    print "Version:", version_id

    build_date = ctime()
    print "Build date:", build_date

    print 'Writing runtime version info.'
    f = open(path.join('Tribler', 'Core', 'version.py'), 'w')
    f.write('version_id = "%s"%sbuild_date = "%s"' % (version_id, linesep, build_date))
    f.close()

    f = open('.TriblerVersion', 'w')
    f.write(version_id)
    f.close()

    if platform == 'linux2':
        runCommand('dch -v {} New upstream release.'.format(version_id).split())
    elif platform == 'win32':
        print 'Replacing NSI string.'
        f = open(path.join('Tribler', 'Main', 'Build', 'Win32', 'tribler.nsi'), 'r+')
        content = f.read().replace('__GIT__', version_id)
        f.seek(0)
        f.write(content)
        f.close()

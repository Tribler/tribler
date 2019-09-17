"""
This file lists the python dependencies for Tribler.

Note that this file should not depend on any external modules itself other than builtin ones.
"""
from __future__ import absolute_import, print_function

import importlib
import sys

dependencies = [
    {'module': 'PyQt5', 'pip_install': 'pip3 install PyQt5', 'optional': False, 'scope': 'gui'},
    {'module': 'twisted', 'pip_install': 'pip3 install Twisted', 'optional': False, 'scope': 'core'},
    {'module': 'libtorrent', 'pip_install': 'apt install python-libtorrent', 'optional': False, 'scope': 'core'},
    {'module': 'cryptography', 'pip_install': 'pip3 install cryptograpy>=2.3', 'optional': False, 'scope': 'core'},
    {'module': 'libnacl', 'pip_install': 'pip3 install libnacl', 'optional': False, 'scope': 'core'},
    {'module': 'pony', 'pip_install': 'pip3 install pony', 'optional': False, 'scope': 'core'},
    {'module': 'lz4', 'pip_install': 'pip3 install lz4', 'optional': False, 'scope': 'core'},
    {'module': 'psutil', 'pip_install': 'pip3 install psutil', 'optional': False, 'scope': 'both'},
    {'module': 'networkx', 'pip_install': 'pip3 install networkx', 'optional': False, 'scope': 'both'},
    {'module': 'pyqtgraph', 'pip_install': 'pip3 install pyqtgraph', 'optional': False, 'scope': 'gui'},
    {'module': 'matplotlib', 'pip_install': 'pip3 install matplotlib', 'optional': False, 'scope': 'gui'},
    {'module': 'chardet', 'pip_install': 'pip3 install chardet', 'optional': False, 'scope': 'core'},
    {'module': 'cherrypy', 'pip_install': 'pip3 install cherrypy', 'optional': False, 'scope': 'core'},
    {'module': 'configobj', 'pip_install': 'pip3 install configobj', 'optional': False, 'scope': 'both'},
    {'module': 'netifaces', 'pip_install': 'pip install netifaces', 'optional': False, 'scope': 'core'},
    {'module': 'six', 'pip_install': 'pip install six', 'optional': False, 'scope': 'both'},
    {'module': 'bitcoinlib', 'pip_install': 'pip install bitcoinlib', 'optional': True, 'scope': 'core'},
]


def show_system_popup(title, text):
    """
    Create a native pop-up without any third party dependency.

    :param title: the pop-up title
    :param text: the pop-up body
    """
    try:
        import win32api
        win32api.MessageBox(0, text, title)
    except ImportError:
        import subprocess
        subprocess.Popen(['xmessage', '-center', text], shell=False)
    sep = "*" * 80
    print('\n'.join([sep, title, sep, text, sep]), file=sys.stderr)


def check_for_missing_dependencies(scope='both'):
    """
    Checks modules installed with pip, especially via linux post installation script.
    Program exits with a dialog if there are any missing dependencies.

    :param scope: Defines the scope of the dependencies. Can have three values: core, gui, both. Default value is both.
    """
    missing_deps = []
    for dep in dependencies:
        if scope == 'both' or dep['scope'] == 'both' or dep['scope'] == scope:
            try:
                importlib.import_module(dep['module'])
            except ImportError:
                if not dep['optional']:
                    missing_deps.append(dep)

    if missing_deps:
        formatted_message = "\n ".join([miss_dep['pip_install'] for miss_dep in missing_deps])
        show_system_popup("Dependencies missing!",
                          "Tribler -  found missing dependencies in %s!\n"
                          "Please install the following dependencies to continue:"
                          "\n\n %s \n\n" % (scope, formatted_message)
                          )
        exit(1)

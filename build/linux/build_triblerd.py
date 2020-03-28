#!/usr/bin/env python3
'''
Created on 29 Mar 2020

@author: boogie
'''
import os
import shutil

dockers = ["boogiepy/tribler-manylinux1-x86:latest"]
root_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
cwd = os.path.abspath(os.getcwd())

os.system("cd %s" % root_dir)
for container in dockers:
    shutil.rmtree(os.path.join(root_dir, "build", "triblerd"), True)
    cname = container.replace("/", "_").replace(":", "_")
    cmd = "docker run -ti -v %s:/work -w /work %s python3.6 -m PyInstaller triblerd.spec -y --onefile --distpath dist/%s" % (root_dir,
                                                                                                          container,
                                                                                                          cname)
    os.system(cmd)
os.system("cd %s" % cwd)
import os
import sys

from traceback import print_exc
from shutil import copy as copyFile, move
from Tribler.Test.test_as_server import FILES_DIR


def init_bak_tribler_sdb(backup='bak_tribler.sdb', destination='tribler.sdb', destination_path=FILES_DIR, overwrite=False):
    backup_path = os.path.join(FILES_DIR, backup)
    destination_path = os.path.join(destination_path, destination)

    if not os.path.isfile(backup_path) or overwrite:
        got = extract_db_files(FILES_DIR, backup_path + ".tar.gz", overwrite)
        if not got:
            print >> sys.stderr, "Missing", backup_path + ".tar.gz"
            sys.exit(1)

    for f in os.listdir(FILES_DIR):
        if f.startswith(destination):
            os.remove(os.path.join(FILES_DIR, f))

    if os.path.isfile(backup_path):
        copyFile(backup_path, destination_path)

    return destination_path


def extract_db_files(file_dir, file_name, overwrite=False):
    try:
        import tarfile
        tar = tarfile.open(file_name, 'r|gz')
        for member in tar:
            print "extract file", member
            tar.extract(member)
            dest = os.path.join(file_dir, member.name)
            dest_dir = os.path.dirname(dest)
            if not os.path.isdir(dest_dir):
                os.makedirs(dest_dir)

            if overwrite and os.path.exists(dest):
                os.remove(dest)

            move(member.name, dest)
        tar.close()
        return True
    except:
        print_exc()
        return False

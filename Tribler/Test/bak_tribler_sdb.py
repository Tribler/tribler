import sys
import os
from traceback import print_exc
from shutil import copy as copyFile, move

DB_FILE_NAME = 'tribler.sdb'
DB_DIR_NAME = None

FILES_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'extend_db_dir'))
TRIBLER_DB_PATH = os.path.join(FILES_DIR, 'tribler.sdb')
TRIBLER_DB_PATH_BACKUP = os.path.join(FILES_DIR, 'bak_tribler.sdb')
STATE_FILE_NAME_PATH = os.path.join(FILES_DIR, 'tribler.sdb-journal')

def init_bak_tribler_sdb():
    if not os.path.isfile(TRIBLER_DB_PATH_BACKUP):
        got = extract_db_files(FILES_DIR, 'bak_tribler.tar.gz')
        if not got:
            print >> sys.stderr, "Missing bak_tribler.tar.gz"
            sys.exit(1)

    if os.path.isfile(TRIBLER_DB_PATH_BACKUP):
        copyFile(TRIBLER_DB_PATH_BACKUP, TRIBLER_DB_PATH)
        # print "refresh sqlite db", TRIBLER_DB_PATH

    if os.path.exists(STATE_FILE_NAME_PATH):
        os.remove(STATE_FILE_NAME_PATH)
        print "remove journal file"

def extract_db_files(file_dir, file_name):
    try:
        import tarfile
        tar = tarfile.open(os.path.join(file_dir, file_name), 'r|gz')
        for member in tar:
            print "extract file", member
            tar.extract(member)
            dest = os.path.join(file_dir, member.name)
            dest_dir = os.path.dirname(dest)
            if not os.path.isdir(dest_dir):
                os.makedirs(dest_dir)
            move(member.name, dest)
        tar.close()
        return True
    except:
        print_exc()
        return False

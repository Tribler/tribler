from __future__ import absolute_import

from Tribler.Core.TorrentDef import TorrentDef


def create_dummy_sql_dumb(file_name):
    """
    Create a TorrentDef with a dummy sql dumb file
    :param file_name: full path to the file
    :return: tdef
    """
    with open(file_name, 'w') as fp:
        fp.write("BEGIN TRANSACTION;")
        fp.write("CREATE TABLE IF NOT EXISTS option(key TEXT PRIMARY KEY, value BLOB);")
        fp.write("INSERT OR REPLACE INTO option(key, value) VALUES('database_version', '0');")
        fp.write("COMMIT;")
    tdef = TorrentDef()
    tdef.add_content(file_name)
    tdef.set_piece_length(2 ** 16)
    tdef.save()
    return tdef

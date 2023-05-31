from pathlib import Path
from typing import Union

from pony.orm import Database, db_session

from tribler.core.components.metadata_store.db.orm_bindings import misc
from tribler.core.components.popularity.rendezvous.db.orm_bindings import certificate
from tribler.core.utilities.utilities import MEMORY_DB


class RendezvousDatabase:
    DB_VERSION = 0

    def __init__(self, db_path: Union[Path, type(MEMORY_DB)]):

        self.database = Database()

        self.MiscData = misc.define_binding(self.database)
        self.Certificate = certificate.define_binding(self.database)

        if db_path is MEMORY_DB:
            create_db = True
            db_path_string = ":memory:"
        else:
            create_db = not db_path.is_file()
            db_path_string = str(db_path)

        self.database.bind(provider='sqlite', filename=db_path_string, create_db=create_db, timeout=120.0)
        self.database.generate_mapping(create_tables=create_db)

        if create_db:
            with db_session:
                self.MiscData(name="db_version", value=str(self.DB_VERSION))

    def shutdown(self) -> None:
        self.database.disconnect()
